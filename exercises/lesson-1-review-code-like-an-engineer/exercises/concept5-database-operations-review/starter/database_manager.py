"""
Simple database operations for the users table.

Security and structural fixes applied (see README.md "Review Template"):
1. SQL injection      -> parameterized queries (already present; kept and lint-guarded)
2. Input validation   -> bool rejected as user_id, re.fullmatch, case/whitespace normalization
3. Error handling     -> typed exception hierarchy raised with `from e`, no bare Exception
4. Resource handling  -> single `_cursor()` context manager owns connect/commit/rollback/close
5. Logging            -> no basicConfig side effect, lazy %s args, user_id logged instead of email
"""

import os
import re
import sqlite3
import logging
from contextlib import contextmanager

# A library must not configure the root logger; the application entry point owns that.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Anchors are unnecessary with fullmatch, which also refuses a trailing newline that `$` would allow.
_EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

_MAX_EMAIL_LENGTH = 254  # RFC 5321
_MAX_NAME_LENGTH = 255


class DatabaseError(Exception):
    """Base class for database failures raised by DatabaseManager."""


class UserAlreadyExistsError(DatabaseError):
    """A write violated a uniqueness or integrity constraint (e.g. duplicate email)."""


class DatabaseUnavailableError(DatabaseError):
    """The database could not be opened or the statement could not be executed."""


class DatabaseManager:
    def __init__(self, db_path, timeout=5.0):
        if db_path is None:
            raise ValueError("Database path cannot be empty or None")

        if not isinstance(db_path, (str, os.PathLike)):
            raise TypeError("Database path must be a string or path-like object")

        if isinstance(db_path, str) and not db_path.strip():
            raise ValueError("Database path cannot be empty")

        self.db_path = db_path
        self._timeout = timeout

    @contextmanager
    def _cursor(self):
        """
        Yield a cursor for one unit of work.

        Commits on clean exit, rolls back on any database error, and always closes the
        connection. Translates sqlite3 errors into this module's exception types so callers
        can branch on the failure kind without string-matching a message.
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=self._timeout)
        except sqlite3.Error as e:
            # Operator detail goes to the log; the caller gets no filesystem detail.
            logger.error("Could not open database at %s", self.db_path, exc_info=True)
            raise DatabaseUnavailableError("Database is unavailable") from e

        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")  # off by default in SQLite
            yield conn.cursor()
            conn.commit()

        except sqlite3.IntegrityError as e:
            conn.rollback()
            logger.error("Constraint violation during database operation", exc_info=True)
            raise UserAlreadyExistsError(
                "The record violates a uniqueness or integrity constraint"
            ) from e

        except sqlite3.OperationalError as e:
            # Covers connection-level faults and missing schema ("no such table").
            conn.rollback()
            logger.error("Operational error during database operation", exc_info=True)
            raise DatabaseUnavailableError("Database operation failed") from e

        except sqlite3.Error as e:
            conn.rollback()
            logger.error("Database error during operation", exc_info=True)
            raise DatabaseError("Database operation failed") from e

        finally:
            conn.close()

    def _validate_email(self, email):
        """Validate an email address and return it normalized (stripped, lowercased)."""
        if email is None:
            raise ValueError("Email cannot be empty or None")

        # Type is checked before emptiness so a falsy non-string reports TypeError, not ValueError.
        if not isinstance(email, str):
            raise TypeError("Email must be a string")

        email = email.strip().lower()

        if not email:
            raise ValueError("Email cannot be empty or None")

        if len(email) > _MAX_EMAIL_LENGTH:
            raise ValueError(
                f"Email exceeds maximum length of {_MAX_EMAIL_LENGTH} characters"
            )

        if not _EMAIL_PATTERN.fullmatch(email):
            raise ValueError(f"Invalid email format: {email}")

        return email

    def _validate_name(self, name):
        """Validate a name and return it stripped of surrounding whitespace."""
        if name is None:
            raise ValueError("Name cannot be empty or None")

        if not isinstance(name, str):
            raise TypeError("Name must be a string")

        name = name.strip()

        if not name:
            raise ValueError("Name cannot be empty or only whitespace")

        if len(name) > _MAX_NAME_LENGTH:
            raise ValueError(
                f"Name exceeds maximum length of {_MAX_NAME_LENGTH} characters"
            )

        return name

    def _validate_user_id(self, user_id):
        """Validate a user id and return it."""
        if user_id is None:
            raise ValueError("User ID cannot be None")

        # bool subclasses int, so True would otherwise pass as user id 1.
        if isinstance(user_id, bool) or not isinstance(user_id, int):
            raise TypeError("User ID must be an integer")

        if user_id <= 0:
            raise ValueError("User ID must be a positive integer")

        return user_id

    def get_user_by_email(self, email):
        """
        Retrieve a user by email address.

        Args:
            email: Email address to search for; normalized before lookup.

        Returns:
            sqlite3.Row with keys id, name, email (also indexable positionally),
            or None if no user matches.

        Raises:
            ValueError: If email is empty or malformed
            TypeError: If email is not a string
            DatabaseUnavailableError: If the database cannot be opened or queried
        """
        email = self._validate_email(email)

        with self._cursor() as cursor:
            # Explicit columns: callers no longer depend on physical column order.
            cursor.execute(
                "SELECT id, name, email FROM users WHERE email = ?", (email,)
            )
            row = cursor.fetchone()

        logger.info("Fetched user by email (found=%s)", row is not None)
        return row

    def create_user(self, name, email):
        """
        Create a new user.

        Args:
            name: User's name; stored stripped
            email: User's email address; stored normalized

        Returns:
            ID of the newly created user

        Raises:
            ValueError: If name or email is empty or malformed
            TypeError: If name or email is not a string
            UserAlreadyExistsError: If the email is already registered
            DatabaseUnavailableError: If the database cannot be opened or written
        """
        name = self._validate_name(name)
        email = self._validate_email(email)

        with self._cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (name, email) VALUES (?, ?)", (name, email)
            )
            user_id = cursor.lastrowid

        # Log the id, never the address, so enabling INFO does not start recording PII.
        logger.info("Created user id=%s", user_id)
        return user_id

    def update_user_email(self, user_id, new_email):
        """
        Update a user's email address.

        Args:
            user_id: ID of the user to update
            new_email: New email address; stored normalized

        Returns:
            Number of rows affected (0 if the user does not exist, 1 if updated)

        Raises:
            ValueError: If user_id is not positive, or email is empty or malformed
            TypeError: If user_id is not an integer (bool included) or email is not a string
            UserAlreadyExistsError: If the email is already registered to another user
            DatabaseUnavailableError: If the database cannot be opened or written
        """
        user_id = self._validate_user_id(user_id)
        new_email = self._validate_email(new_email)

        with self._cursor() as cursor:
            cursor.execute(
                "UPDATE users SET email = ? WHERE id = ?", (new_email, user_id)
            )
            rows_affected = cursor.rowcount

        if rows_affected == 0:
            logger.warning("No user found with id=%s", user_id)
        else:
            logger.info("Updated email for user id=%s", user_id)

        return rows_affected
