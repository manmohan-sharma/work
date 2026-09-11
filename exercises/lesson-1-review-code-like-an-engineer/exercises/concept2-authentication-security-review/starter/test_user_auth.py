"""Behavioural tests for the reviewed user_auth module.

Organised so that each class maps onto a claim the module's header makes
(the S-numbers), plus the ordinary happy-path and error-path behaviour.
The pre-review suite in test_security_vulnerabilities.py asserts the
*opposite* of most of this -- it documents the vulnerabilities that this
file now proves are gone -- and is expected to fail against this module.

Known gaps that the module does not yet handle live in TestKnownGaps as
strict xfails, so they are recorded without turning the suite red and will
start failing the moment they are fixed.
"""

import hashlib
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest

import user_auth
from user_auth import (
    BCRYPT_ROUNDS,
    MAX_FAILED_ATTEMPTS,
    MAX_PASSWORD_BYTES,
    MAX_USERNAME_LENGTH,
    MIN_PASSWORD_BYTES,
    SESSION_TTL,
    RateLimiter,
    UserAuth,
    UsernameTakenError,
    create_connection,
    hash_password,
    initialize_schema,
)

# Test data only. Real deployments create users through registration;
# nothing in the application reads these.
FIXTURE_USERS = [
    ("admin", "password123"),
    ("user1", "secret"),
]

GOOD_USER = "admin"
GOOD_PASSWORD = "password123"


# --------------------------------------------------------------------------
# Fixtures
#
# The seeded database that used to live inside user_auth.connect_to_database()
# lives here. Keeping it in the test suite is the S2 fix: the application
# module no longer ships a fixture database or credentials.
# --------------------------------------------------------------------------

@pytest.fixture(scope="session")
def hash_for():
    """Return a bcrypt hash for a password, memoized for the whole session.

    A cost-12 hash takes ~250 ms. Re-hashing the same fixture passwords for
    every test would dominate the suite's runtime without testing anything,
    so the hashes are computed once. Tests that care about hashing itself
    call bcrypt (or hash_password) directly instead of using this.
    """
    cache = {}

    def _hash_for(password: str) -> bytes:
        if password not in cache:
            cache[password] = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
            )
        return cache[password]

    return _hash_for


@pytest.fixture
def add_user(hash_for):
    """Insert a user directly, bypassing the registration password policy.

    Hashed directly rather than through hash_password(): the fixture
    passwords are shorter than MIN_PASSWORD_BYTES, and they stand in for
    accounts predating the policy. login() deliberately does not enforce a
    minimum, so such accounts still work.
    """

    def _add_user(conn, username, password):
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_for(password)),
        )
        conn.commit()

    return _add_user


@pytest.fixture
def connection():
    """An empty, schema-initialized in-memory database."""
    conn = create_connection(":memory:")
    initialize_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def seeded_connection(connection, add_user):
    """The same database with the fixture users inserted."""
    for username, password in FIXTURE_USERS:
        add_user(connection, username, password)
    return connection


@pytest.fixture
def auth(seeded_connection):
    """A UserAuth wired to the seeded database."""
    return UserAuth(seeded_connection)


@pytest.fixture
def permissive_auth(seeded_connection):
    """A UserAuth whose rate limiter will not interfere with the test."""
    return UserAuth(seeded_connection, rate_limiter=RateLimiter(max_attempts=10_000))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def sessions_of(conn, user_id=None):
    """Every session row, or only those belonging to `user_id`."""
    if user_id is None:
        return conn.execute("SELECT * FROM sessions").fetchall()
    return conn.execute(
        "SELECT * FROM sessions WHERE user_id = ?", (user_id,)
    ).fetchall()


def user_id_of(conn, username):
    return conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()["id"]


def expire_session(conn, token):
    """Backdate a live session so it is past its expiry."""
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    conn.execute(
        "UPDATE sessions SET expires_at = ? WHERE token_hash = ?",
        (past, user_auth._hash_token(token)),
    )
    conn.commit()


class CountingCheckpw:
    """bcrypt.checkpw wrapper that records how many times it was called.

    Holds the real function, since the name it is installed under is the
    one being replaced.
    """

    def __init__(self, real):
        self._real = real
        self.calls = 0

    def __call__(self, password, hashed):
        self.calls += 1
        return self._real(password, hashed)


@pytest.fixture
def count_checkpw(monkeypatch):
    counter = CountingCheckpw(bcrypt.checkpw)
    monkeypatch.setattr(user_auth.bcrypt, "checkpw", counter)
    return counter


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------

class TestPasswordHashing:

    def test_hash_verifies_against_its_password(self):
        hashed = hash_password("correct horse battery")
        assert bcrypt.checkpw(b"correct horse battery", hashed)

    def test_hash_does_not_verify_against_another_password(self):
        hashed = hash_password("correct horse battery")
        assert not bcrypt.checkpw(b"correct horse batterz", hashed)

    def test_hash_is_not_the_plaintext(self):
        hashed = hash_password("correct horse battery")
        assert b"correct horse battery" not in hashed
        assert hashed.startswith(b"$2b$")

    def test_same_password_hashes_differently_each_time(self):
        """A per-hash salt: identical passwords must not share a digest."""
        assert hash_password("correct horse battery") != hash_password(
            "correct horse battery"
        )

    def test_rejects_non_string(self):
        for value in (None, 12345, b"bytes-not-str", ["list"]):
            with pytest.raises(ValueError):
                hash_password(value)

    def test_rejects_password_below_minimum(self):
        with pytest.raises(ValueError):
            hash_password("a" * (MIN_PASSWORD_BYTES - 1))

    def test_accepts_password_at_minimum(self):
        assert hash_password("a" * MIN_PASSWORD_BYTES)

    def test_rejects_password_above_maximum(self):
        with pytest.raises(ValueError):
            hash_password("a" * (MAX_PASSWORD_BYTES + 1))

    def test_accepts_password_at_maximum(self):
        assert hash_password("a" * MAX_PASSWORD_BYTES)

    def test_length_limit_counts_bytes_not_characters(self):
        """Length is a bcrypt constraint, so it must be measured in bytes."""
        # 40 two-byte characters = 80 bytes, over the limit despite being
        # only 40 characters long.
        with pytest.raises(ValueError):
            hash_password("é" * 40)


# --------------------------------------------------------------------------
# S8 -- schema constraints
# --------------------------------------------------------------------------

class TestSchemaConstraints:

    def test_username_is_unique(self, seeded_connection, hash_for):
        with pytest.raises(sqlite3.IntegrityError):
            seeded_connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (GOOD_USER, hash_for(GOOD_PASSWORD)),
            )

    def test_username_uniqueness_is_case_insensitive(
        self, seeded_connection, hash_for
    ):
        """Otherwise 'admin' and 'Admin' are two accounts that log in
        interchangeably, because the lookup collates NOCASE."""
        with pytest.raises(sqlite3.IntegrityError):
            seeded_connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("ADMIN", hash_for(GOOD_PASSWORD)),
            )

    def test_username_is_not_null(self, connection, hash_for):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (None, hash_for(GOOD_PASSWORD)),
            )

    def test_password_hash_is_not_null(self, connection):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("newuser", None),
            )

    def test_session_requires_an_existing_user(self, connection):
        """Foreign keys are enforced, so orphan sessions cannot be written."""
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, "
                "expires_at) VALUES (?, ?, ?, ?)",
                ("deadbeef", 999, "2026-01-01", "2099-01-01"),
            )

    def test_deleting_a_user_cascades_to_their_sessions(self, auth, seeded_connection):
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        assert token is not None
        seeded_connection.execute(
            "DELETE FROM users WHERE username = ?", (GOOD_USER,)
        )
        seeded_connection.commit()
        assert sessions_of(seeded_connection) == []

    def test_schema_initialization_is_idempotent(self, seeded_connection):
        initialize_schema(seeded_connection)
        assert seeded_connection.execute("SELECT COUNT(*) c FROM users").fetchone()[
            "c"
        ] == 2


class TestConnectionFactory:

    def test_rows_are_mappings(self, connection):
        assert connection.row_factory is sqlite3.Row

    def test_foreign_keys_are_enabled(self, connection):
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# --------------------------------------------------------------------------
# Construction (S2, S9)
# --------------------------------------------------------------------------

class TestConstruction:

    def test_connection_is_required(self):
        with pytest.raises(ValueError):
            UserAuth(None)

    def test_rejects_a_connection_without_row_factory(self):
        """Fails fast rather than silently mutating a shared connection."""
        raw = sqlite3.connect(":memory:")
        try:
            with pytest.raises(TypeError):
                UserAuth(raw)
        finally:
            raw.close()

    def test_module_ships_no_fixture_database_or_credentials(self):
        """S2: the pre-review module built its own seeded database."""
        assert not hasattr(user_auth, "connect_to_database")
        source = open(user_auth.__file__, encoding="utf-8").read()
        assert GOOD_PASSWORD not in source

    def test_connection_is_not_public_attribute(self, auth):
        """S9: the old `db_connection` attribute handed callers the table."""
        assert not hasattr(auth, "db_connection")


# --------------------------------------------------------------------------
# Login -- success path (S1)
# --------------------------------------------------------------------------

class TestLoginSuccess:

    def test_valid_credentials_return_a_token(self, auth):
        assert isinstance(auth.login(GOOD_USER, GOOD_PASSWORD), str)

    def test_token_carries_full_entropy(self, auth):
        """32 CSPRNG bytes base64url-encoded, not the old 32-char string."""
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        assert len(token) >= 43

    def test_each_login_mints_a_distinct_token(self, auth):
        tokens = {auth.login(GOOD_USER, GOOD_PASSWORD) for _ in range(3)}
        assert len(tokens) == 3

    def test_username_is_matched_case_insensitively(self, auth):
        assert auth.login("ADMIN", GOOD_PASSWORD) is not None

    def test_surrounding_whitespace_is_trimmed(self, auth):
        assert auth.login("  admin  ", GOOD_PASSWORD) is not None

    def test_password_is_not_trimmed(self, auth):
        """Trimming the password would silently widen the accepted set."""
        assert auth.login(GOOD_USER, "  password123  ") is None

    def test_second_fixture_user_can_log_in(self, auth):
        assert auth.login("user1", "secret") is not None

    def test_login_does_not_accept_another_users_password(self, auth):
        assert auth.login("user1", GOOD_PASSWORD) is None


# --------------------------------------------------------------------------
# Login -- failure path, including injection
# --------------------------------------------------------------------------

class TestLoginFailure:

    def test_wrong_password_is_rejected(self, auth):
        assert auth.login(GOOD_USER, "wrongpassword") is None

    def test_unknown_username_is_rejected(self, auth):
        assert auth.login("nonexistent", GOOD_PASSWORD) is None

    def test_no_session_is_created_for_a_failed_login(self, auth, seeded_connection):
        auth.login(GOOD_USER, "wrongpassword")
        assert sessions_of(seeded_connection) == []

    @pytest.mark.parametrize(
        "payload",
        [
            "admin' OR '1'='1",
            "admin'--",
            "admin' OR 1=1--",
            "' OR ''='",
            "admin'/*",
        ],
    )
    def test_sql_injection_cannot_bypass_authentication(self, permissive_auth, payload):
        """The headline pre-review vulnerability: these used to return a
        token. The query is parameterised, so they are now just usernames
        that do not exist."""
        assert permissive_auth.login(payload, "any_password") is None

    def test_sql_injection_cannot_destroy_the_users_table(
        self, permissive_auth, seeded_connection
    ):
        permissive_auth.login("admin'; DROP TABLE users; --", "any_password")
        assert seeded_connection.execute("SELECT COUNT(*) c FROM users").fetchone()[
            "c"
        ] == 2

    def test_injection_in_the_password_is_inert(self, permissive_auth):
        assert permissive_auth.login(GOOD_USER, "' OR '1'='1") is None


# --------------------------------------------------------------------------
# S6 -- input validation, and the promise that login never raises
# --------------------------------------------------------------------------

class TestInputValidation:

    @pytest.mark.parametrize("username", [None, 123, b"admin", ["admin"], {"a": 1}])
    def test_non_string_username_returns_none(self, permissive_auth, username):
        assert permissive_auth.login(username, GOOD_PASSWORD) is None

    @pytest.mark.parametrize("password", [None, 123, b"password123", ["pw"]])
    def test_non_string_password_returns_none(self, permissive_auth, password):
        assert permissive_auth.login(GOOD_USER, password) is None

    @pytest.mark.parametrize("username", ["", "   ", "\t\n"])
    def test_empty_username_returns_none(self, permissive_auth, username):
        assert permissive_auth.login(username, GOOD_PASSWORD) is None

    def test_overlong_username_returns_none(self, permissive_auth):
        assert permissive_auth.login("a" * (MAX_USERNAME_LENGTH + 1), "pw") is None

    def test_username_at_the_length_limit_can_log_in(
        self, seeded_connection, add_user
    ):
        name = "u" * MAX_USERNAME_LENGTH
        add_user(seeded_connection, name, GOOD_PASSWORD)
        assert UserAuth(seeded_connection).login(name, GOOD_PASSWORD) is not None

    def test_overlong_password_returns_none_instead_of_raising(self, permissive_auth):
        """bcrypt >= 4 raises above 72 bytes; login must absorb that."""
        assert permissive_auth.login(GOOD_USER, "b" * (MAX_PASSWORD_BYTES + 1)) is None

    def test_huge_inputs_do_not_crash(self, permissive_auth):
        assert permissive_auth.login("a" * 10_000, "b" * 10_000) is None

    def test_null_bytes_and_control_characters_do_not_crash(self, permissive_auth):
        assert permissive_auth.login("admin\x00", "pw\x00\r\n") is None

    def test_unicode_username_does_not_crash(self, permissive_auth):
        assert permissive_auth.login("ådmin🙂", GOOD_PASSWORD) is None

    def test_bad_input_is_rejected_before_any_hashing(
        self, permissive_auth, count_checkpw
    ):
        """Malformed input must not be allowed to buy an attacker a bcrypt
        round; validation happens first."""
        permissive_auth.login(None, GOOD_PASSWORD)
        permissive_auth.login(GOOD_USER, None)
        permissive_auth.login("", "")
        assert count_checkpw.calls == 0


# --------------------------------------------------------------------------
# S4 -- no user-enumeration oracle
# --------------------------------------------------------------------------

class TestUserEnumeration:

    def test_unknown_user_still_costs_one_verification(
        self, permissive_auth, count_checkpw
    ):
        """Skipping bcrypt for unknown usernames is what makes the timing
        oracle observable, so the unknown path must hash too."""
        permissive_auth.login("nonexistent", GOOD_PASSWORD)
        assert count_checkpw.calls == 1

    def test_known_user_costs_the_same_one_verification(
        self, permissive_auth, count_checkpw
    ):
        permissive_auth.login(GOOD_USER, "wrongpassword")
        assert count_checkpw.calls == 1

    def test_both_paths_return_the_same_answer(self, permissive_auth):
        assert permissive_auth.login("nonexistent", "x" * 20) is None
        assert permissive_auth.login(GOOD_USER, "x" * 20) is None

    def test_dummy_hash_matches_the_configured_cost(self):
        """A cheaper dummy hash would reopen the oracle by cost, not by
        code path."""
        assert user_auth._DUMMY_HASH.startswith(
            b"$2b$%02d$" % user_auth.BCRYPT_ROUNDS
        )


# --------------------------------------------------------------------------
# S7 -- malformed stored hashes fail closed
# --------------------------------------------------------------------------

class TestMalformedStoredHash:

    @pytest.mark.parametrize(
        "stored", [b"", b"not-a-bcrypt-hash", b"$2b$12$tooshort", b"\x00\x01\x02"]
    )
    def test_corrupt_hash_denies_login_without_raising(
        self, permissive_auth, seeded_connection, stored
    ):
        seeded_connection.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (stored, GOOD_USER),
        )
        seeded_connection.commit()
        assert permissive_auth.login(GOOD_USER, GOOD_PASSWORD) is None

    def test_corrupt_hash_does_not_let_an_empty_password_in(
        self, permissive_auth, seeded_connection
    ):
        seeded_connection.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (b"garbage", GOOD_USER),
        )
        seeded_connection.commit()
        assert permissive_auth.login(GOOD_USER, "") is None

    def test_other_accounts_are_unaffected(self, permissive_auth, seeded_connection):
        seeded_connection.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (b"garbage", GOOD_USER),
        )
        seeded_connection.commit()
        assert permissive_auth.login("user1", "secret") is not None


# --------------------------------------------------------------------------
# S5 -- rate limiting through the login path
# --------------------------------------------------------------------------

class TestLoginRateLimiting:

    def test_repeated_failures_lock_the_account(self, auth):
        for _ in range(MAX_FAILED_ATTEMPTS):
            assert auth.login(GOOD_USER, "wrongpassword") is None
        assert auth.login(GOOD_USER, GOOD_PASSWORD) is None

    def test_lockout_is_per_username(self, auth):
        for _ in range(MAX_FAILED_ATTEMPTS):
            auth.login(GOOD_USER, "wrongpassword")
        assert auth.login("user1", "secret") is not None

    def test_a_locked_account_costs_no_hashing(self, auth, count_checkpw):
        """Checked before bcrypt, so a locked username stops being a CPU
        amplifier."""
        for _ in range(MAX_FAILED_ATTEMPTS):
            auth.login(GOOD_USER, "wrongpassword")
        before = count_checkpw.calls
        auth.login(GOOD_USER, "wrongpassword")
        assert count_checkpw.calls == before

    def test_a_successful_login_clears_the_counter(self, auth):
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            auth.login(GOOD_USER, "wrongpassword")
        assert auth.login(GOOD_USER, GOOD_PASSWORD) is not None
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            auth.login(GOOD_USER, "wrongpassword")
        assert auth.login(GOOD_USER, GOOD_PASSWORD) is not None

    def test_lockout_cannot_be_bypassed_by_changing_case(self, auth):
        """The lookup collates NOCASE, so every spelling of the name is the
        same account and must draw on the same attempt budget."""
        for _ in range(MAX_FAILED_ATTEMPTS):
            auth.login(GOOD_USER, "wrongpassword")
        assert auth.login(GOOD_USER, GOOD_PASSWORD) is None
        assert auth.login("ADMIN", GOOD_PASSWORD) is None
        assert auth.login("AdMiN", GOOD_PASSWORD) is None

    def test_case_variants_share_one_attempt_budget(self, auth):
        """Spreading the failures across spellings must still lock."""
        for spelling in ["admin", "ADMIN", "Admin", "aDmIn", "admiN"]:
            assert auth.login(spelling, "wrongpassword") is None
        assert auth.login(GOOD_USER, GOOD_PASSWORD) is None

    def test_lockout_survives_surrounding_whitespace(self, auth):
        for _ in range(MAX_FAILED_ATTEMPTS):
            auth.login(GOOD_USER, "wrongpassword")
        assert auth.login("  admin  ", GOOD_PASSWORD) is None

    def test_unknown_usernames_are_rate_limited_too(
        self, seeded_connection, count_checkpw
    ):
        """Otherwise the enumeration-proof unknown path is a free bcrypt
        oracle for anyone spraying one username."""
        auth = UserAuth(seeded_connection)
        for _ in range(MAX_FAILED_ATTEMPTS):
            auth.login("nonexistent", "whatever")
        before = count_checkpw.calls
        auth.login("nonexistent", "whatever")
        assert count_checkpw.calls == before


# --------------------------------------------------------------------------
# RateLimiter in isolation
# --------------------------------------------------------------------------

class TestRateLimiter:

    def test_a_fresh_key_is_allowed(self):
        assert RateLimiter().allow("someone")

    def test_locks_after_the_configured_number_of_failures(self):
        limiter = RateLimiter(max_attempts=3)
        assert limiter.record_failure("k") is False
        assert limiter.record_failure("k") is False
        assert limiter.record_failure("k") is True
        assert limiter.allow("k") is False

    def test_lockout_expires(self):
        limiter = RateLimiter(max_attempts=2, lockout=timedelta(seconds=0.05))
        limiter.record_failure("k")
        limiter.record_failure("k")
        assert limiter.allow("k") is False
        time.sleep(0.06)
        assert limiter.allow("k") is True

    def test_failures_outside_the_window_do_not_accumulate(self):
        limiter = RateLimiter(max_attempts=3, window=timedelta(seconds=0.05))
        limiter.record_failure("k")
        limiter.record_failure("k")
        time.sleep(0.06)
        # The two stale failures must not combine with this one to lock.
        assert limiter.record_failure("k") is False
        assert limiter.allow("k") is True

    def test_expired_lockout_starts_a_fresh_window(self):
        limiter = RateLimiter(
            max_attempts=2, window=timedelta(minutes=15), lockout=timedelta(seconds=0.05)
        )
        limiter.record_failure("k")
        limiter.record_failure("k")
        time.sleep(0.06)
        assert limiter.allow("k") is True
        # One failure after the lockout must not immediately re-lock.
        assert limiter.record_failure("k") is False

    def test_reset_clears_failures_and_lockout(self):
        limiter = RateLimiter(max_attempts=2)
        limiter.record_failure("k")
        limiter.record_failure("k")
        limiter.reset("k")
        assert limiter.allow("k") is True
        assert limiter.record_failure("k") is False

    def test_keys_are_independent(self):
        limiter = RateLimiter(max_attempts=2)
        limiter.record_failure("a")
        limiter.record_failure("a")
        assert limiter.allow("a") is False
        assert limiter.allow("b") is True

    def test_tracked_keys_are_pruned(self):
        """Attempts against endless random usernames must not grow the
        failure map without bound."""
        limiter = RateLimiter(window=timedelta(seconds=0.01))
        stale = time.monotonic() - 3600
        limiter._failures = {f"k{i}": [stale] for i in range(limiter._MAX_TRACKED_KEYS)}
        limiter.record_failure("fresh")
        assert len(limiter._failures) < limiter._MAX_TRACKED_KEYS


# --------------------------------------------------------------------------
# S3 -- session lifecycle
# --------------------------------------------------------------------------

class TestSessions:

    def test_a_fresh_token_validates_to_its_user(self, auth, seeded_connection):
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        assert auth.validate_token(token) == user_id_of(seeded_connection, GOOD_USER)

    def test_login_persists_exactly_one_session(self, auth, seeded_connection):
        auth.login(GOOD_USER, GOOD_PASSWORD)
        assert len(sessions_of(seeded_connection)) == 1

    def test_only_the_digest_is_stored(self, auth, seeded_connection):
        """A database read must not hand over usable live sessions."""
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        rows = sessions_of(seeded_connection)
        assert token not in "".join(str(tuple(r)) for r in rows)
        assert rows[0]["token_hash"] == hashlib.sha256(token.encode()).hexdigest()

    def test_expiry_follows_the_configured_ttl(self, auth, seeded_connection):
        auth.login(GOOD_USER, GOOD_PASSWORD)
        row = sessions_of(seeded_connection)[0]
        created = datetime.fromisoformat(row["created_at"])
        expires = datetime.fromisoformat(row["expires_at"])
        assert expires - created == SESSION_TTL

    @pytest.mark.parametrize(
        "token", [None, "", 123, b"tok", "not-a-real-token", "a" * 43]
    )
    def test_bogus_tokens_do_not_validate(self, auth, token):
        assert auth.validate_token(token) is None

    def test_a_forged_digest_does_not_validate(self, auth, seeded_connection):
        """The stored value is a digest, so knowing it is not knowing the
        token."""
        auth.login(GOOD_USER, GOOD_PASSWORD)
        digest = sessions_of(seeded_connection)[0]["token_hash"]
        assert auth.validate_token(digest) is None

    def test_an_expired_token_does_not_validate(self, auth, seeded_connection):
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        expire_session(seeded_connection, token)
        assert auth.validate_token(token) is None

    def test_validating_an_expired_token_clears_the_row(
        self, auth, seeded_connection
    ):
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        expire_session(seeded_connection, token)
        auth.validate_token(token)
        assert sessions_of(seeded_connection) == []

    def test_a_naive_stored_expiry_is_read_as_utc(self, auth, seeded_connection):
        """SQLite's datetime('now') writes naive UTC; treating it as local
        time would expire sessions early or late by the UTC offset."""
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None)
        seeded_connection.execute(
            "UPDATE sessions SET expires_at = ? WHERE token_hash = ?",
            (future.isoformat(), user_auth._hash_token(token)),
        )
        seeded_connection.commit()
        assert auth.validate_token(token) is not None

    def test_unreadable_expiry_fails_closed(self, auth, seeded_connection):
        """Corrupt session data must deny access, not raise -- the same way
        a corrupt password hash does."""
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        seeded_connection.execute(
            "UPDATE sessions SET expires_at = ? WHERE token_hash = ?",
            ("not-a-timestamp", user_auth._hash_token(token)),
        )
        seeded_connection.commit()
        assert auth.validate_token(token) is None

    def test_unreadable_expiry_drops_the_unusable_row(self, auth, seeded_connection):
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        seeded_connection.execute(
            "UPDATE sessions SET expires_at = ? WHERE token_hash = ?",
            ("not-a-timestamp", user_auth._hash_token(token)),
        )
        seeded_connection.commit()
        auth.validate_token(token)
        assert sessions_of(seeded_connection) == []

    def test_logout_revokes_the_session(self, auth):
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        assert auth.logout(token) is True
        assert auth.validate_token(token) is None

    def test_logout_is_not_replayable(self, auth):
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        auth.logout(token)
        assert auth.logout(token) is False

    @pytest.mark.parametrize("token", [None, "", 123, "unknown-token"])
    def test_logout_of_a_bogus_token_reports_nothing_removed(self, auth, token):
        assert auth.logout(token) is False

    def test_logout_leaves_other_sessions_alone(self, auth):
        first = auth.login(GOOD_USER, GOOD_PASSWORD)
        second = auth.login(GOOD_USER, GOOD_PASSWORD)
        auth.logout(first)
        assert auth.validate_token(second) is not None

    def test_logout_all_revokes_every_session_for_the_user(
        self, auth, seeded_connection
    ):
        tokens = [auth.login(GOOD_USER, GOOD_PASSWORD) for _ in range(3)]
        user_id = user_id_of(seeded_connection, GOOD_USER)
        assert auth.logout_all_sessions(user_id) == 3
        assert all(auth.validate_token(t) is None for t in tokens)

    def test_logout_all_spares_other_users(self, auth, seeded_connection):
        auth.login(GOOD_USER, GOOD_PASSWORD)
        other = auth.login("user1", "secret")
        auth.logout_all_sessions(user_id_of(seeded_connection, GOOD_USER))
        assert auth.validate_token(other) is not None

    def test_logout_all_for_a_user_with_no_sessions(self, auth, seeded_connection):
        assert auth.logout_all_sessions(user_id_of(seeded_connection, GOOD_USER)) == 0

    def test_purge_removes_only_expired_sessions(self, auth, seeded_connection):
        stale = auth.login(GOOD_USER, GOOD_PASSWORD)
        live = auth.login("user1", "secret")
        expire_session(seeded_connection, stale)
        assert auth.purge_expired_sessions() == 1
        assert auth.validate_token(live) is not None

    def test_purge_with_nothing_to_do(self, auth):
        auth.login(GOOD_USER, GOOD_PASSWORD)
        assert auth.purge_expired_sessions() == 0


# --------------------------------------------------------------------------
# Database failures are absorbed, not propagated
# --------------------------------------------------------------------------

class TestDatabaseErrors:

    @pytest.fixture
    def broken(self, auth, seeded_connection):
        token = auth.login(GOOD_USER, GOOD_PASSWORD)
        seeded_connection.close()
        return auth, token

    def test_login_returns_none(self, broken):
        auth, _ = broken
        assert auth.login(GOOD_USER, GOOD_PASSWORD) is None

    def test_validate_token_returns_none(self, broken):
        auth, token = broken
        assert auth.validate_token(token) is None

    def test_logout_returns_false(self, broken):
        auth, token = broken
        assert auth.logout(token) is False

    def test_logout_all_returns_zero(self, broken):
        auth, _ = broken
        assert auth.logout_all_sessions(1) == 0

    def test_purge_returns_zero(self, broken):
        auth, _ = broken
        assert auth.purge_expired_sessions() == 0


# --------------------------------------------------------------------------
# Exercise criteria
#
# The assertions the reference suite (solution/test_secure_authentication.py)
# makes, ported to this module's API. The reference drives UserAuth() with no
# arguments and calls register_user(); this module takes an injected
# connection (S2) and has no registration method, so `register` below stands
# in for the one it is missing -- see TestKnownGaps.
# --------------------------------------------------------------------------

def register(conn, username, password):
    """Create a user through the module's registration API."""
    return UserAuth(conn).register_user(username, password)


class TestReferenceSecurityCriteria:

    def test_registration_and_login_work(self, connection):
        user_id = register(connection, "testuser", "secure_password_123")
        assert isinstance(user_id, int)
        token = UserAuth(connection).login("testuser", "secure_password_123")
        assert token is not None and len(token) > 20

    def test_wrong_password_fails(self, connection):
        register(connection, "testuser", "correct_password_1")
        assert UserAuth(connection).login("testuser", "wrong_password_11") is None

    def test_nonexistent_user_fails(self, connection):
        assert UserAuth(connection).login("nonexistent", "any_password_1") is None

    @pytest.mark.parametrize(
        "injection",
        [
            "admin' OR '1'='1",
            "admin'; DROP TABLE users; --",
            "admin' UNION SELECT * FROM users --",
            "' OR 1=1 --",
        ],
    )
    def test_sql_injection_in_login_blocked(self, connection, injection):
        register(connection, "admin", "secure_password_1")
        auth = UserAuth(connection, rate_limiter=RateLimiter(max_attempts=10_000))
        assert auth.login(injection, "any_password") is None, (
            f"SQL injection '{injection}' should be blocked!"
        )

    def test_tokens_are_unique(self, connection):
        register(connection, "testuser", "a_good_password_1")
        auth = UserAuth(connection)
        tokens = [auth.login("testuser", "a_good_password_1") for _ in range(10)]
        assert len(set(tokens)) == len(tokens)

    def test_tokens_have_good_length(self, connection):
        register(connection, "testuser", "a_good_password_1")
        token = UserAuth(connection).login("testuser", "a_good_password_1")
        assert len(token) >= 32

    def test_empty_password_is_rejected(self):
        with pytest.raises(ValueError):
            hash_password("")

    def test_weak_password_is_rejected_at_registration(self):
        """Stronger than the reference, which stores 'password' happily."""
        with pytest.raises(ValueError):
            hash_password("password")

    def test_stored_hash_is_not_a_bare_digest(self, connection):
        """The reference hashes with unsalted SHA-256, which is reversible by
        rainbow table. A bcrypt hash is salted and cost-parameterised."""
        register(connection, "testuser", "secure_password_123")
        stored = connection.execute(
            "SELECT password_hash FROM users WHERE username = ?", ("testuser",)
        ).fetchone()["password_hash"]
        assert stored != hashlib.sha256(b"secure_password_123").hexdigest().encode()
        assert stored.startswith(b"$2b$")


class TestInformationDisclosure:

    def test_failure_reasons_are_indistinguishable_to_the_caller(self, connection):
        """Unknown user, wrong password and malformed input must be one
        answer, or the response itself is an enumeration oracle."""
        register(connection, "testuser", "secure_password_123")
        auth = UserAuth(connection, rate_limiter=RateLimiter(max_attempts=10_000))
        results = [
            auth.login("testuser", "wrong_password_11"),
            auth.login("nonexistent", "secure_password_123"),
            auth.login(None, "secure_password_123"),
            auth.login("testuser", 12345),
            auth.login("", ""),
        ]
        assert results == [None] * 5

    def test_database_errors_are_not_surfaced_to_the_caller(self, auth, seeded_connection):
        """A leaked sqlite3 error message discloses schema details."""
        seeded_connection.close()
        assert auth.login(GOOD_USER, GOOD_PASSWORD) is None


class TestAuditLogging:

    def test_successful_login_is_logged(self, auth, caplog):
        with caplog.at_level(logging.INFO, logger="user_auth"):
            auth.login(GOOD_USER, GOOD_PASSWORD)
        assert "login succeeded" in caplog.text

    def test_failed_login_is_logged(self, auth, caplog):
        with caplog.at_level(logging.INFO, logger="user_auth"):
            auth.login(GOOD_USER, "wrongpassword")
        assert "login failed" in caplog.text

    def test_lockout_is_logged_as_a_warning(self, auth, caplog):
        with caplog.at_level(logging.WARNING, logger="user_auth"):
            for _ in range(MAX_FAILED_ATTEMPTS + 1):
                auth.login(GOOD_USER, "wrongpassword")
        assert "account locked" in caplog.text
        assert "throttled" in caplog.text

    def test_passwords_are_never_written_to_the_log(self, auth, caplog):
        """Audit logging that records the credential is worse than none."""
        with caplog.at_level(logging.DEBUG, logger="user_auth"):
            auth.login(GOOD_USER, GOOD_PASSWORD)
            auth.login(GOOD_USER, "hunter2-in-the-clear")
        assert GOOD_PASSWORD not in caplog.text
        assert "hunter2-in-the-clear" not in caplog.text

    def test_tokens_are_never_written_to_the_log(self, auth, caplog):
        with caplog.at_level(logging.DEBUG, logger="user_auth"):
            token = auth.login(GOOD_USER, GOOD_PASSWORD)
            auth.validate_token(token)
            auth.logout(token)
        assert token not in caplog.text


# --------------------------------------------------------------------------
# S10 -- registration
# --------------------------------------------------------------------------

class TestRegistration:

    def test_returns_the_new_user_id(self, connection):
        assert isinstance(register(connection, "newuser", "secure_password_1"), int)

    def test_the_registered_user_can_log_in(self, connection):
        register(connection, "newuser", "secure_password_1")
        assert UserAuth(connection).login("newuser", "secure_password_1") is not None

    def test_the_password_is_stored_hashed(self, connection):
        register(connection, "newuser", "secure_password_1")
        stored = connection.execute(
            "SELECT password_hash FROM users WHERE username = ?", ("newuser",)
        ).fetchone()["password_hash"]
        assert stored.startswith(b"$2b$")
        assert b"secure_password_1" not in stored

    def test_duplicate_username_is_refused(self, connection):
        register(connection, "newuser", "secure_password_1")
        with pytest.raises(UsernameTakenError):
            register(connection, "newuser", "another_password_1")

    def test_duplicate_is_refused_case_insensitively(self, connection):
        """Otherwise 'admin' and 'ADMIN' are two rows that the NOCASE lookup
        cannot tell apart."""
        register(connection, "newuser", "secure_password_1")
        with pytest.raises(UsernameTakenError):
            register(connection, "NEWUSER", "another_password_1")

    def test_username_taken_is_catchable_as_value_error(self, connection):
        register(connection, "newuser", "secure_password_1")
        with pytest.raises(ValueError):
            register(connection, "newuser", "another_password_1")

    def test_a_refused_duplicate_leaves_the_original_intact(self, connection):
        register(connection, "newuser", "secure_password_1")
        with pytest.raises(UsernameTakenError):
            register(connection, "newuser", "another_password_1")
        assert UserAuth(connection).login("newuser", "secure_password_1") is not None

    @pytest.mark.parametrize(
        "username", ["", "   ", "\t\n", None, 123, b"user", "u" * (MAX_USERNAME_LENGTH + 1)]
    )
    def test_unusable_usernames_are_refused(self, connection, username):
        """S10: a name that could never match at login must not be storable."""
        with pytest.raises(ValueError):
            register(connection, username, "secure_password_1")

    @pytest.mark.parametrize("username", ["", "   ", None, 123])
    def test_a_refused_username_writes_no_row(self, connection, username):
        with pytest.raises(ValueError):
            register(connection, username, "secure_password_1")
        assert connection.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0

    def test_surrounding_whitespace_is_stripped_before_storing(self, connection):
        """Stored padded, the row would be unreachable: login trims first."""
        register(connection, "  newuser  ", "secure_password_1")
        stored = connection.execute("SELECT username FROM users").fetchone()["username"]
        assert stored == "newuser"
        assert UserAuth(connection).login("  newuser  ", "secure_password_1") is not None

    def test_username_at_the_length_limit_is_accepted(self, connection):
        name = "u" * MAX_USERNAME_LENGTH
        register(connection, name, "secure_password_1")
        assert UserAuth(connection).login(name, "secure_password_1") is not None

    @pytest.mark.parametrize(
        "password", ["", "short", "a" * (MIN_PASSWORD_BYTES - 1), None, 123]
    )
    def test_policy_violating_passwords_are_refused(self, connection, password):
        with pytest.raises(ValueError):
            register(connection, "newuser", password)

    def test_a_refused_password_writes_no_row(self, connection):
        """The hash is computed before the INSERT, so a rejected password
        never reaches the database."""
        with pytest.raises(ValueError):
            register(connection, "newuser", "short")
        assert connection.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0

    def test_registration_is_logged_without_the_password(self, connection, caplog):
        with caplog.at_level(logging.DEBUG, logger="user_auth"):
            register(connection, "newuser", "secure_password_1")
        assert "user registered" in caplog.text
        assert "secure_password_1" not in caplog.text

    def test_registration_reports_a_database_failure(self, connection):
        """Registration fails loudly; it does not swallow errors the way
        login does."""
        connection.close()
        with pytest.raises(sqlite3.ProgrammingError):
            register(connection, "newuser", "secure_password_1")
