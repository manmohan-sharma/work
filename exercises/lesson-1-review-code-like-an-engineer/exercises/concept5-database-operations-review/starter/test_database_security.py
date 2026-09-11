"""
Tests for secure database operations.

These tests assert that the vulnerabilities are CLOSED. The previous version of this file
asserted the opposite (that injection succeeded and validation was absent), so it failed
once the code was fixed. Each test below maps to a finding in README.md.
"""

import logging
import os
import pathlib
import sqlite3
import tempfile

import pytest

from database_manager import (
    DatabaseManager,
    DatabaseError,
    DatabaseUnavailableError,
    UserAlreadyExistsError,
)


@pytest.fixture
def db_path():
    """A throwaway database file with a users table. UNIQUE(email) is what makes
    duplicate detection meaningful, so the schema the code assumes is the schema tested."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        path = tmp.name
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE)"
    )
    conn.commit()
    conn.close()
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def db(db_path):
    return DatabaseManager(db_path)


class TestInitialization:
    """__init__ validates db_path (was accepted unvalidated)."""

    def test_rejects_empty_path(self):
        with pytest.raises(ValueError, match="Database path cannot be empty"):
            DatabaseManager("")

    def test_rejects_whitespace_only_path(self):
        with pytest.raises(ValueError, match="Database path cannot be empty"):
            DatabaseManager("   ")

    def test_rejects_none_path(self):
        with pytest.raises(ValueError, match="Database path cannot be empty"):
            DatabaseManager(None)

    def test_rejects_non_string_path(self):
        with pytest.raises(TypeError, match="must be a string or path-like"):
            DatabaseManager(42)

    def test_accepts_valid_path(self):
        assert DatabaseManager("valid_path.db").db_path == "valid_path.db"

    def test_accepts_pathlike(self, db_path):
        """pathlib.Path callers are not broken by the new type check."""
        assert DatabaseManager(pathlib.Path(db_path)).get_user_by_email("a@b.co") is None


class TestBasicDatabaseOperations:
    def test_create_and_find_user(self, db):
        user_id = db.create_user("John Doe", "john@test.com")
        user = db.get_user_by_email("john@test.com")

        assert user_id is not None
        assert user is not None
        assert user[1] == "John Doe"          # positional access still works
        assert user[2] == "john@test.com"

    def test_row_supports_named_access(self, db):
        """SELECT names its columns, so callers need not depend on column order."""
        db.create_user("John Doe", "john@test.com")
        user = db.get_user_by_email("john@test.com")
        assert user["name"] == "John Doe"
        assert user["email"] == "john@test.com"

    def test_missing_user_returns_none(self, db):
        assert db.get_user_by_email("nobody@test.com") is None

    def test_update_returns_rows_affected(self, db):
        user_id = db.create_user("John", "john@test.com")
        assert db.update_user_email(user_id, "new@test.com") == 1
        assert db.get_user_by_email("new@test.com") is not None

    def test_update_of_absent_user_returns_zero(self, db):
        assert db.update_user_email(9999, "new@test.com") == 0


class TestSQLInjectionPrevention:
    """Parameterized queries + format validation, two independent layers."""

    def test_get_user_by_email_blocks_injection(self, db):
        db.create_user("John", "john@test.com")
        # Rejected at validation; it never reaches SQLite as a query fragment.
        with pytest.raises(ValueError, match="Invalid email format"):
            db.get_user_by_email("' OR '1'='1")

    def test_create_user_injection_is_stored_as_literal_text(self, db):
        """A payload in `name` is bound as a value, so it cannot add rows."""
        malicious = "John'); INSERT INTO users (name, email) VALUES ('Hacker', 'hack@evil.com"
        db.create_user(malicious, "test@email.com")

        conn = sqlite3.connect(db.db_path)
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        stored = conn.execute("SELECT name FROM users").fetchone()[0]
        conn.close()

        assert count == 1, "injection must not create extra rows"
        assert stored == malicious, "payload is stored verbatim as data"
        assert db.get_user_by_email("hack@evil.com") is None

    def test_update_user_email_blocks_injection(self, db):
        user_id = db.create_user("John", "john@test.com")
        with pytest.raises(ValueError, match="Invalid email format"):
            db.update_user_email(user_id, "x@y.co'; DROP TABLE users; --")

        # Table intact and unchanged.
        assert db.get_user_by_email("john@test.com") is not None

    def test_drop_table_payload_does_not_execute(self, db):
        db.create_user("John", "john@test.com")
        with pytest.raises(ValueError):
            db.get_user_by_email("'; DROP TABLE users; --")
        assert db.get_user_by_email("john@test.com") is not None


class TestInputValidation:
    def test_rejects_empty_email(self, db):
        with pytest.raises(ValueError, match="Email cannot be empty"):
            db.get_user_by_email("")

    def test_rejects_whitespace_only_email(self, db):
        with pytest.raises(ValueError, match="Email cannot be empty"):
            db.get_user_by_email("   ")

    def test_rejects_none_name(self, db):
        with pytest.raises(ValueError, match="Name cannot be empty"):
            db.create_user(None, "test@email.com")

    def test_rejects_non_string_name(self, db):
        """A falsy non-string reports TypeError, not a misleading 'empty' ValueError."""
        with pytest.raises(TypeError, match="Name must be a string"):
            db.create_user(0, "test@email.com")

    def test_rejects_non_string_email(self, db):
        with pytest.raises(TypeError, match="Email must be a string"):
            db.create_user("John", 0)

    def test_rejects_string_user_id(self, db):
        with pytest.raises(TypeError, match="User ID must be an integer"):
            db.update_user_email("not_a_number", "new@email.com")

    def test_rejects_bool_user_id(self, db):
        """FIX: bool subclasses int, so True previously passed and rewrote user id 1."""
        db.create_user("Admin", "admin@test.com")   # becomes id 1
        with pytest.raises(TypeError, match="User ID must be an integer"):
            db.update_user_email(True, "attacker@test.com")
        assert db.get_user_by_email("admin@test.com") is not None
        assert db.get_user_by_email("attacker@test.com") is None

    def test_rejects_non_positive_user_id(self, db):
        for bad in (0, -1):
            with pytest.raises(ValueError, match="positive integer"):
                db.update_user_email(bad, "new@email.com")

    def test_trailing_newline_email_is_normalized_not_stored(self, db):
        """FIX: `$` let a trailing newline through and it was STORED; it is now stripped."""
        db.create_user("NL", "evil@test.com\n")
        stored = db.get_user_by_email("evil@test.com")
        assert stored is not None
        assert stored["email"] == "evil@test.com", "newline must not survive into storage"
        assert "\n" not in stored["email"]

    def test_rejects_embedded_newline_email(self, db):
        """fullmatch also refuses interior control characters, which strip() cannot remove."""
        with pytest.raises(ValueError, match="Invalid email format"):
            db.create_user("Hdr", "evil@test.com\nBcc: victim@test.com")

    def test_rejects_overlong_email(self, db):
        with pytest.raises(ValueError, match="maximum length"):
            db.create_user("X", "a" * 250 + "@test.com")

    def test_rejects_overlong_name(self, db):
        with pytest.raises(ValueError, match="maximum length"):
            db.create_user("x" * 256, "test@email.com")

    def test_email_is_normalized_to_lowercase(self, db):
        """FIX: case variants no longer create duplicate accounts for one mailbox."""
        db.create_user("John", "John@Test.COM")
        assert db.get_user_by_email("john@test.com") is not None
        assert db.get_user_by_email("JOHN@TEST.COM") is not None
        assert db.get_user_by_email("john@test.com")["email"] == "john@test.com"

    def test_case_variant_duplicate_is_rejected(self, db):
        db.create_user("John", "john@test.com")
        with pytest.raises(UserAlreadyExistsError):
            db.create_user("Impostor", "JOHN@TEST.COM")

    def test_name_is_stored_stripped(self, db):
        """FIX: padding was previously persisted verbatim."""
        db.create_user("   Padded   ", "pad@test.com")
        assert db.get_user_by_email("pad@test.com")["name"] == "Padded"

    def test_email_is_stored_stripped(self, db):
        db.create_user("John", "  spaced@test.com  ")
        assert db.get_user_by_email("spaced@test.com") is not None


class TestErrorHandling:
    """Typed exceptions replace bare `Exception`, and the cause chain is preserved."""

    def test_duplicate_email_raises_typed_error(self, db):
        db.create_user("John", "john@test.com")
        with pytest.raises(UserAlreadyExistsError) as exc:
            db.create_user("Other", "john@test.com")
        assert isinstance(exc.value.__cause__, sqlite3.IntegrityError)

    def test_update_to_taken_email_raises_typed_error(self, db):
        db.create_user("John", "john@test.com")
        jane_id = db.create_user("Jane", "jane@test.com")
        with pytest.raises(UserAlreadyExistsError):
            db.update_user_email(jane_id, "john@test.com")

    def test_unopenable_database_raises_typed_error(self):
        db = DatabaseManager("/nonexistent/directory/test.db")
        with pytest.raises(DatabaseUnavailableError) as exc:
            db.get_user_by_email("test@email.com")
        assert isinstance(exc.value.__cause__, sqlite3.OperationalError)

    def test_missing_table_raises_typed_error(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            path = tmp.name
        try:
            sqlite3.connect(path).close()      # empty database, no tables
            db = DatabaseManager(path)
            with pytest.raises(DatabaseUnavailableError) as exc:
                db.get_user_by_email("test@email.com")
            assert isinstance(exc.value.__cause__, sqlite3.OperationalError)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_typed_errors_share_a_base_class(self, db):
        """Callers can catch DatabaseError without resorting to `except Exception`."""
        assert issubclass(UserAlreadyExistsError, DatabaseError)
        assert issubclass(DatabaseUnavailableError, DatabaseError)
        db.create_user("John", "john@test.com")
        with pytest.raises(DatabaseError):
            db.create_user("Other", "john@test.com")

    def test_error_messages_do_not_leak_internals(self):
        """Raw SQLite text and the filesystem path stay in the log, not in the exception."""
        path = "/nonexistent/directory/secret_location.db"
        db = DatabaseManager(path)
        with pytest.raises(DatabaseUnavailableError) as exc:
            db.get_user_by_email("test@email.com")
        message = str(exc.value)
        assert "unable to open database file" not in message
        assert path not in message

    def test_failed_write_is_rolled_back(self, db):
        db.create_user("John", "john@test.com")
        with pytest.raises(UserAlreadyExistsError):
            db.create_user("Other", "john@test.com")

        conn = sqlite3.connect(db.db_path)
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        assert count == 1, "the failed insert must not be persisted"


class TestLogging:
    """The audit trail is emittable, and enabling it does not start logging PII."""

    def test_module_does_not_configure_root_logger(self):
        """FIX: basicConfig(level=ERROR) at import both hijacked root and killed INFO."""
        assert logging.getLogger("database_manager").level == logging.NOTSET

    def test_audit_lines_are_emitted_at_info(self, db, caplog):
        with caplog.at_level(logging.INFO, logger="database_manager"):
            user_id = db.create_user("John", "john@test.com")
        assert any("Created user" in r.message for r in caplog.records)
        assert any(str(user_id) in r.getMessage() for r in caplog.records)

    def test_email_is_not_written_to_the_audit_log(self, db, caplog):
        """FIX: enabling INFO previously started writing user email addresses to disk."""
        with caplog.at_level(logging.INFO, logger="database_manager"):
            db.create_user("John", "john@test.com")
            db.get_user_by_email("john@test.com")
        assert "john@test.com" not in caplog.text

    def test_missing_user_is_recorded(self, db, caplog):
        with caplog.at_level(logging.WARNING, logger="database_manager"):
            db.update_user_email(9999, "new@test.com")
        assert any("No user found" in r.message for r in caplog.records)
