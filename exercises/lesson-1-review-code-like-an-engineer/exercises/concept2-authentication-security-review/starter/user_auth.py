"""
User authentication: credential verification and session management.

This is the post-review version of the Lesson 1 / Concept 2 exercise file.
The original combined production auth logic with an in-memory fixture
database seeded with known credentials; that fixture now lives in
conftest.py and this module talks only to an injected connection.

Fixes applied (see review notes for the S-numbers):
  S1  session tokens come from `secrets`, not `random`
  S2  no fixture database and no hardcoded credentials in this module
  S3  sessions are persisted with an expiry and can be revoked
  S4  unknown usernames cost the same as known ones (no timing oracle)
  S5  per-username rate limiting with temporary lockout
  S6  input is type- and length-checked; login() never raises on bad input
  S7  malformed stored hashes fail closed instead of raising
  S8  username is NOT NULL UNIQUE; password_hash is NOT NULL
  S10 usernames are normalised when they are stored, not only when they
      are read, so an unusable name cannot be registered
  S11 failed attempts are counted against the case-folded name, matching
      how the lookup collates, so case variants share one budget
  S12 an unreadable session expiry fails closed, like a malformed hash

Threading: a sqlite3 connection may only be used from the thread that
created it. Give each thread its own connection (and its own UserAuth),
or front this with a connection pool.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

import bcrypt

logger = logging.getLogger(__name__)


class UsernameTakenError(ValueError):
    """Raised by register_user when the username is already registered.

    A ValueError subclass so callers that only care that registration was
    refused can keep catching ValueError.
    """


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

BCRYPT_ROUNDS = 12

# bcrypt >= 4 raises above 72 bytes (older versions silently truncated,
# which made every password a 72-byte prefix match). Pin bcrypt>=4.
MAX_PASSWORD_BYTES = 72

# Enforced at registration only. Applying a minimum at login would lock
# out any account created before the policy existed.
MIN_PASSWORD_BYTES = 12

MAX_USERNAME_LENGTH = 254

TOKEN_BYTES = 32                          # 256 bits from the system CSPRNG
SESSION_TTL = timedelta(hours=12)

MAX_FAILED_ATTEMPTS = 5
ATTEMPT_WINDOW = timedelta(minutes=15)
LOCKOUT_DURATION = timedelta(minutes=15)

# S4: verifying against this when the username does not exist keeps the
# unknown-user path as expensive as the known-user path, closing the
# enumeration oracle. Built at import so its cost factor always matches
# BCRYPT_ROUNDS; this costs one bcrypt hash (~250 ms) at import time.
_DUMMY_HASH = bcrypt.hashpw(
    secrets.token_hex(16).encode("utf-8"),
    bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
)


# --------------------------------------------------------------------------
# Schema and connections
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    -- S8: UNIQUE stops duplicate registrations; COLLATE NOCASE makes both
    -- the constraint and the login lookup case-insensitive (ASCII only --
    -- SQLite's NOCASE does not fold non-ASCII characters).
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash BLOB NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- S3: a session is server-side state. Only the token's digest is stored,
-- so a database read does not hand over usable live sessions.
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user    ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
"""


def create_connection(database_path: str) -> sqlite3.Connection:
    """Open a connection configured the way UserAuth expects.

    `database_path` comes from configuration -- never hardcode it here.
    In a larger project the schema below belongs in versioned migrations
    rather than in application code.
    """
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    """Create the users and sessions tables if they do not exist."""
    conn.executescript(SCHEMA)
    conn.commit()


def hash_password(password: str) -> bytes:
    """Hash a new password for storage, enforcing the length policy.

    Raises ValueError so that registration fails loudly; login, by
    contrast, must never raise on bad input (see UserAuth.login).
    """
    if not isinstance(password, str):
        raise ValueError("password must be a string")
    encoded = password.encode("utf-8")
    if len(encoded) < MIN_PASSWORD_BYTES:
        raise ValueError(f"password must be at least {MIN_PASSWORD_BYTES} bytes")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=BCRYPT_ROUNDS))


def normalize_username(username) -> str | None:
    """Trim and validate a username, or None if it is unusable (S6, S10).

    Applied on the write path as well as the read path: a name that could
    never match at login -- blank, whitespace-only, over-long, or padded
    with spaces -- must not be storable in the first place.
    """
    if not isinstance(username, str):
        return None
    name = username.strip()
    if not name or len(name) > MAX_USERNAME_LENGTH:
        return None
    return name


def _rate_limit_key(name: str) -> str:
    """Canonical form that failed attempts are counted against (S11).

    This has to match how the lookup matches. `users.username` collates
    NOCASE, so 'admin' and 'ADMIN' are one account and must share one
    attempt budget -- counting them separately hands an attacker a fresh
    budget per case variant. casefold() folds more than SQLite's ASCII-only
    NOCASE, so two distinct non-ASCII accounts may share a budget: that
    errs towards locking too much, never too little.
    """
    return name.casefold()


def _hash_token(token: str) -> str:
    """Digest a session token for storage and lookup.

    Plain SHA-256 is correct here: the token already carries 256 bits of
    CSPRNG entropy, so there is nothing to brute-force and no need for a
    slow password KDF.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------

class RateLimiter:
    """Sliding-window failure counter with temporary lockout (S5).

    State is per-process. A multi-worker deployment needs shared state
    (Redis or similar) or an attacker simply spreads attempts across
    workers; treat this as the single-process implementation of an
    interface, not as the final answer.
    """

    _MAX_TRACKED_KEYS = 10_000

    def __init__(
        self,
        max_attempts: int = MAX_FAILED_ATTEMPTS,
        window: timedelta = ATTEMPT_WINDOW,
        lockout: timedelta = LOCKOUT_DURATION,
    ) -> None:
        self._max_attempts = max_attempts
        self._window = window.total_seconds()
        self._lockout = lockout.total_seconds()
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """True if `key` may attempt a login right now."""
        now = time.monotonic()
        with self._lock:
            until = self._locked_until.get(key)
            if until is None:
                return True
            if now < until:
                return False
            # Lockout expired -- clear it and give the caller a fresh window.
            del self._locked_until[key]
            self._failures.pop(key, None)
            return True

    def record_failure(self, key: str) -> bool:
        """Record a failed attempt. Returns True if `key` is now locked out."""
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            attempts = [t for t in self._failures.get(key, []) if now - t < self._window]
            attempts.append(now)
            self._failures[key] = attempts
            if len(attempts) >= self._max_attempts:
                self._locked_until[key] = now + self._lockout
                return True
            return False

    def reset(self, key: str) -> None:
        """Clear all state for `key` (called after a successful login)."""
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)

    def _prune(self, now: float) -> None:
        """Drop stale entries so that attempts against random usernames
        cannot grow these dicts without bound. Caller holds the lock."""
        if len(self._failures) < self._MAX_TRACKED_KEYS:
            return
        self._failures = {
            key: times
            for key, times in self._failures.items()
            if any(now - t < self._window for t in times)
        }
        self._locked_until = {
            key: until for key, until in self._locked_until.items() if now < until
        }


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------

class UserAuth:
    """Verifies credentials and issues, validates and revokes sessions."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        if connection is None:
            raise ValueError("connection is required")
        # Fail fast rather than silently mutating a connection the caller
        # may be sharing with other code.
        if connection.row_factory is not sqlite3.Row:
            raise TypeError(
                "connection.row_factory must be sqlite3.Row "
                "(use create_connection)"
            )
        # S9: private, so holding a UserAuth does not grant arbitrary
        # access to the user table.
        self._db = connection
        self._rate_limiter = rate_limiter or RateLimiter()

    # -- public API --------------------------------------------------------

    def register_user(self, username, password) -> int:
        """Create a user and return its id.

        Raises ValueError (UsernameTakenError for a duplicate) so that
        registration fails loudly and the caller learns why. login(), by
        contrast, must never raise -- the asymmetry is deliberate: the
        person registering is entitled to the reason, an unauthenticated
        caller is not.
        """
        name = normalize_username(username)
        if name is None:
            raise ValueError(
                "username must be a non-blank string of at most "
                f"{MAX_USERNAME_LENGTH} characters"
            )
        # Hashed before the INSERT so that a password failing the policy
        # never reaches the database.
        password_hash = hash_password(password)
        try:
            cursor = self._db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (name, password_hash),
            )
            self._db.commit()
        except sqlite3.IntegrityError as exc:
            raise UsernameTakenError("username is already registered") from exc
        logger.info("user registered user=%r", name)
        return cursor.lastrowid

    def login(self, username, password) -> str | None:
        """Verify credentials and return an opaque session token.

        Returns None for every failure -- unknown user, wrong password,
        rate-limited, malformed input, or database error -- and never
        raises, so callers cannot distinguish the causes and neither can
        an attacker. Reasons are logged, not returned.
        """
        name = normalize_username(username)
        if name is None:
            logger.info("login rejected: invalid username input")
            return None
        # S11: counted against the account, not against this spelling of it.
        key = _rate_limit_key(name)

        encoded = self._encode_password(password)
        if encoded is None:
            logger.info("login rejected: invalid password input user=%r", name)
            return None

        # S5: checked before the expensive bcrypt call, so a locked-out
        # username also stops being a CPU amplifier.
        if not self._rate_limiter.allow(key):
            logger.warning("login throttled user=%r", name)
            return None

        try:
            row = self._db.execute(
                # Named columns: no positional coupling to schema order.
                "SELECT id, password_hash FROM users WHERE username = ?",
                (name,),
            ).fetchone()
        except sqlite3.Error:
            logger.exception("login failed: database error user=%r", name)
            return None

        stored_hash = row["password_hash"] if row is not None else None

        # S4: always run one bcrypt verification, against the real hash if
        # there is one and the dummy otherwise, so both paths cost the same.
        try:
            matched = bcrypt.checkpw(encoded, stored_hash or _DUMMY_HASH)
        except (TypeError, ValueError):
            # S7: a NULL or non-bcrypt hash is a data problem, not an
            # authentication success. Fail closed and make it visible.
            logger.exception("login failed: malformed stored hash user=%r", name)
            matched = False

        if row is None or not matched:
            if self._rate_limiter.record_failure(key):
                logger.warning("account locked after repeated failures user=%r", name)
            logger.info("login failed user=%r", name)
            return None

        try:
            token = self._create_session(row["id"])
        except sqlite3.Error:
            logger.exception("login failed: could not persist session user=%r", name)
            return None

        self._rate_limiter.reset(key)
        logger.info("login succeeded user=%r", name)
        return token

    def validate_token(self, token) -> int | None:
        """Return the user id for a live session token, else None (S3)."""
        if not isinstance(token, str) or not token:
            return None

        digest = _hash_token(token)
        try:
            row = self._db.execute(
                "SELECT token_hash, user_id, expires_at FROM sessions "
                "WHERE token_hash = ?",
                (digest,),
            ).fetchone()
        except sqlite3.Error:
            logger.exception("token validation failed: database error")
            return None

        if row is None:
            return None
        if not hmac.compare_digest(row["token_hash"], digest):
            return None

        try:
            expires_at = self._parse_timestamp(row["expires_at"])
        except (TypeError, ValueError):
            # S12: an unreadable expiry is a data problem, not a live
            # session. Fail closed the way a malformed password hash does
            # (S7), and drop the row so it cannot be retried.
            logger.exception(
                "session has an unreadable expiry user_id=%s", row["user_id"]
            )
            self.logout(token)
            return None

        if expires_at <= datetime.now(timezone.utc):
            self.logout(token)
            logger.info("session expired user_id=%s", row["user_id"])
            return None

        return row["user_id"]

    def logout(self, token) -> bool:
        """Revoke a single session. True if a session was removed (S3)."""
        if not isinstance(token, str) or not token:
            return False
        try:
            cursor = self._db.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),)
            )
            self._db.commit()
        except sqlite3.Error:
            logger.exception("logout failed: database error")
            return False
        return cursor.rowcount > 0

    def logout_all_sessions(self, user_id: int) -> int:
        """Revoke every session for a user. Returns the number removed.

        Call this on password change and on suspected compromise.
        """
        try:
            cursor = self._db.execute(
                "DELETE FROM sessions WHERE user_id = ?", (user_id,)
            )
            self._db.commit()
        except sqlite3.Error:
            logger.exception("bulk logout failed user_id=%s", user_id)
            return 0
        logger.info("revoked %d session(s) user_id=%s", cursor.rowcount, user_id)
        return cursor.rowcount

    def purge_expired_sessions(self) -> int:
        """Delete sessions past their expiry. Run periodically."""
        try:
            cursor = self._db.execute(
                "DELETE FROM sessions WHERE expires_at <= ?",
                (datetime.now(timezone.utc).isoformat(),),
            )
            self._db.commit()
        except sqlite3.Error:
            logger.exception("session purge failed")
            return 0
        return cursor.rowcount

    # -- internals ---------------------------------------------------------

    def _create_session(self, user_id: int) -> str:
        """Mint a session token and persist only its digest (S1, S3)."""
        token = secrets.token_urlsafe(TOKEN_BYTES)
        now = datetime.now(timezone.utc)
        self._db.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (
                _hash_token(token),
                user_id,
                now.isoformat(),
                (now + SESSION_TTL).isoformat(),
            ),
        )
        self._db.commit()
        return token

    @staticmethod
    def _encode_password(password) -> bytes | None:
        """UTF-8 encode a submitted password, or None if unusable (S6).

        Only the maximum is enforced here: bcrypt cannot hash more than
        MAX_PASSWORD_BYTES, and passing more raises. The minimum is a
        registration-time policy (see hash_password).
        """
        if not isinstance(password, str):
            return None
        encoded = password.encode("utf-8")
        if len(encoded) > MAX_PASSWORD_BYTES:
            return None
        return encoded

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        """Read a stored ISO timestamp, assuming UTC if it is naive."""
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
