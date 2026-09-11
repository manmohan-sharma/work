# Concept 5: Database Operations Review

## Exercise Overview

Review database operations code that demonstrates basic SQL injection vulnerabilities and simple structural issues. This builds on the security awareness from Concept 2.

## Learning Objectives

- Identify SQL injection vulnerabilities
- Recognize basic input validation issues  
- Apply systematic code review skills
- Understand database security basics

## Instructions

### Step 1: Run Tests to See the Issues
```bash
cd concept5-database-operations-review/starter
python -m pytest test_database_security.py -v
```

**Expected Output:**
- Basic functionality tests pass
- Security tests FAIL (demonstrating SQL injection!)
- Shows database security vulnerabilities

### Step 2: Review the Code
1. **Open** `starter/database_manager.py` and review the functions
2. **Apply** the engineering code review framework:
   - Structure & Organization
   - Naming & Clarity
   - Error Handling
   - Security Issues
3. **Document** your findings using the template below

### Step 3: Run the Solution Tests
```bash
cd ../solution
python -m pytest test_secure_database.py -v
```

**Expected Output:**
- All tests pass showing fixes work
- SQL injection is now blocked
- Notice improved parameterized queries

### Step 4: Compare and Learn
4. **Compare** your analysis with the improved code

## Review Template

> **Review context:** the code in `starter/database_manager.py` has *already been remediated* against
> this exercise's three headline defects. All three queries are parameterized (`:97`, `:143`, `:206`),
> every public method validates its inputs first (`:90`, `:135-136`, `:198-199`), and every connection
> is closed in a `finally` block (`:114-116`, `:176-179`, `:244-247`). Consequently
> `python -m pytest test_database_security.py -v` reports **5 passed, 5 failed** — and all 5 failures are
> the *tests* asserting vulnerabilities that no longer exist, not new bugs:
> `test_sql_injection_in_get_user_by_email` now dies on `ValueError: Invalid email format: ' OR '1'='1`,
> the two `TestInputValidation` cases get `ValueError` where they `pytest.raises((sqlite3.Error, TypeError))`,
> and both `TestSimpleErrorHandling` cases get the wrapped `Exception` instead of the `sqlite3.Error` they
> expect. The suite is now the stale artifact. Everything below reviews the code *as it currently stands*;
> all 7 defects were reproduced by execution, not read off by eye.
>
> **STATUS: fixes applied.** The findings below are kept as the review record, but all 7 are now
> resolved in `starter/database_manager.py`. `test_database_security.py` was rewritten to assert secure
> behavior and reports **42 passed**; the stray 0-byte `starter/test.db` was deleted. Originals are
> preserved as `database_manager.py.orig` / `test_database_security.py.orig` (safe to delete).
>
> **One finding was corrected while fixing it.** Under Security Issue 2(b) the review credits
> `re.fullmatch` with fixing the trailing-newline defect. That is wrong: `.strip()` normalization
> neutralizes a *trailing* newline, so such an address is now accepted and stored clean rather than
> rejected. `fullmatch` matters for *embedded* control characters (`evil@test.com\nBcc: victim@test.com`),
> which `strip()` cannot remove. Both behaviors are covered by tests.

### Issues Found

**Structure & Organization:**
- [x] Issue 1: **~60 lines of duplicated connection/error boilerplate.** `create_user` (`:138-179`) and
  `update_user_email` (`:201-247`) are near-identical: same `conn = None` / `sqlite3.connect` / three-arm
  `except` ladder (`IntegrityError` → `OperationalError` → `Error`, each with its own `rollback()`) / same
  `finally: if conn: conn.close()`. Across the file that is 3 `connect` sites, 8 `raise Exception`, 6
  `rollback()` and 3 `close()` calls, all hand-written. One `@contextmanager` yielding a cursor would
  collapse the file from 246 lines to well under half, and every new method currently has to re-copy the
  ladder correctly or silently leak.
- [x] Issue 2: **`__init__` accepts any path, and a new connection is opened per call.** `__init__`
  (`:28-29`) stores `db_path` with no validation — `DatabaseManager("")` is accepted (**confirmed**), and
  SQLite then silently creates a throwaway database, so writes vanish with no error. This is an actual
  regression against `solution/database_manager.py:14-15`, which does guard it. Separately, connecting on
  every call (`:94`, `:140`, `:203`) means no reuse, no pooling and no way to compose two operations into
  one transaction; `db_path` is also public and mutable mid-flight.

**Naming & Clarity:**
- [x] Issue 1: **`SELECT *` couples every caller to physical column order.** `:97` returns a bare
  positional tuple, so callers must index it — the tests already read `user[1]` and `user[2]`
  (`test_database_security.py:36-37`). Adding, reordering or dropping a column silently changes what every
  caller receives, with no error. Name the columns explicitly and set
  `conn.row_factory = sqlite3.Row` so results are accessed as `user["email"]`.
- [x] Issue 2: **Docstrings document the defect rather than describe a contract.** All three methods
  advertise `Raises: Exception` (`:87`, `:132`, `:195`), which tells a caller nothing actionable — the
  method name `get_user_by_email` is clear, but its *error* interface is unnamed. Likewise
  `_validate_name`'s length check reads `len(name) > 255` (`:60`) two lines after its emptiness check used
  `len(name.strip())` (`:57`), so "255 characters" silently means two different things depending on padding.

**Error Handling:**
- [x] Issue 1: **Exception-type laundering — specific errors are caught, then flattened to bare
  `Exception`.** All 8 handlers do `raise Exception(error_msg)` (`:108`, `:113`, `:158`, `:166`, `:174`,
  `:226`, `:234`, `:242`). The class carefully distinguishes `IntegrityError` from `OperationalError` from
  `Error` — and then throws that distinction away, so a caller cannot tell "duplicate email" (user error,
  HTTP 409, don't retry) from "database is down" (HTTP 503, do retry) without string-matching the message.
  Callers are forced into `except Exception`, which also swallows `KeyboardInterrupt`-adjacent bugs. Worse,
  there is no `from e`: **confirmed** `e.__cause__ is None` on the re-raised error, so the explicit
  exception chain is broken. Fix: define `UserAlreadyExistsError` / `DatabaseUnavailableError` subclasses
  and `raise ... from e`.
- [x] Issue 2: **The audit trail is written but never emitted.** `logging.basicConfig(level=logging.ERROR)`
  at import (`:24`) both hijacks the *root* logger — an application's decision, not a library module's —
  and pins the effective level to 40. **Confirmed:** `isEnabledFor(logging.INFO)` is `False`, so all four
  `logger.info`/`logger.warning` calls (`:101`, `:149`, `:214`, `:216`) — including
  "Successfully created user" and the "No user found with ID" miss signal — are dead code. Nothing records
  who created or changed an account. All six log calls also use eager f-strings instead of lazy `%s` args,
  and no handler passes `exc_info=True`, so every traceback is discarded.

**Security Issues:**
- [x] Issue 1: **Email PII in log messages, plus an account-enumeration oracle in propagated error text.**
  `:101` and `:149` interpolate the raw email address into log lines, so lowering the level to `INFO` in
  production — the obvious fix for the dead-audit-trail issue above — would immediately start writing user
  PII to disk (a GDPR data-minimization problem). The two issues are coupled: fixing one arms the other,
  so log the `user_id`, not the address. Separately, `:156` and `:224` append **"Email may already exist"**
  to the raised message; if that reaches an HTTP response body it confirms whether an address is registered.
  Raw SQLite text (`no such table: users`, `unable to open database file`) is propagated to callers the
  same way, disclosing schema and filesystem detail.
- [x] Issue 2: **Validation is thorough but has three exploitable gaps** (all **confirmed** by execution):
  (a) `isinstance(user_id, int)` (`:68`) accepts `bool`, since `bool` subclasses `int` — `update_user_email(True, ...)`
  passes both guards and rewrites **user id 1**, typically the admin row; (b) the regex uses `re.match` with
  a `$` anchor (`:44-45`), and Python's `$` matches *before a trailing newline*, so `"evil@test.com\n"`
  validates and is stored — use `re.fullmatch` or `\Z`; (c) emails are never case-normalized, so
  `john@test.com` and `JOHN@TEST.COM` both insert successfully, defeating a `UNIQUE(email)` constraint and
  permitting duplicate accounts for one real mailbox. `_validate_name` also rejects whitespace-only input
  but stores unpadded input verbatim — `"   Padded   "` is persisted with its spaces.

### Specific Recommendations

1. **SQL Injection:** **Already correctly fixed — no action needed, and do not regress it.** All three
   statements use `?` placeholders with a parameter tuple (`:97-98`, `:143-144`, `:206-207`); the payload
   `' OR '1'='1` is now bound as a literal string and additionally rejected by format validation before it
   ever reaches SQLite. The one thing to add is a lint guard (Bandit `B608`, or Ruff `S608`) in CI so a
   future edit cannot reintroduce f-string query construction, since the test that used to catch it is now
   inverted. Note for completeness that parameter binding protects *values* only — if a column or table
   name ever needs to be dynamic, it must be validated against a hardcoded allowlist, never interpolated.
2. **Input Validation:** Keep the extracted `_validate_*` helpers — that structure is right — and close the
   three confirmed gaps: reject `bool` explicitly (`if isinstance(user_id, bool) or not isinstance(user_id, int)`),
   switch to `re.fullmatch` so a trailing newline cannot pass, and normalize with
   `email = email.strip().lower()` *before* both validation and storage, returning the cleaned value so the
   canonical form is what actually gets written. Do the same for `name.strip()`. Also reorder
   `_validate_email` and `_validate_name` to check `isinstance` *before* truthiness (`:33-37`, `:50-54`): a
   non-string falsy value like `0` or `[]` currently raises `ValueError("cannot be empty")` when `TypeError`
   is the accurate signal. Finally, validate `db_path` in `__init__`, matching `solution:14-15`.
3. **Connection Management:** Correct but hand-rolled. Replace all three copies with one private helper —
   `@contextmanager def _cursor(self): conn = sqlite3.connect(self.db_path); try: conn.row_factory = sqlite3.Row; yield conn.cursor(); conn.commit(); except: conn.rollback(); raise; finally: conn.close()` —
   so commit/rollback/close are defined once and every future method inherits them. Add
   `sqlite3.connect(..., timeout=...)` and enable `PRAGMA foreign_keys = ON` (off by default in SQLite) in
   that single place. For anything beyond a single process, move to a pooled connection or a
   `threading.local`, since a fresh connect per call will not hold up under concurrency.
4. **Error Handling:** Introduce a small exception hierarchy — `DatabaseError(Exception)` with
   `UserAlreadyExistsError` and `DatabaseUnavailableError` subclasses — and replace all 8
   `raise Exception(msg)` sites with `raise UserAlreadyExistsError(...) from e`, preserving `__cause__`.
   Log the operator-facing detail (with `exc_info=True`) and raise a generic caller-facing message, so
   SQLite internals and the "Email may already exist" hint stop crossing the trust boundary. Move
   `logging.basicConfig` out of the module into the application entry point, drop the level to `INFO` so
   the audit lines actually emit, and simultaneously replace the logged email with `user_id` so that change
   does not start leaking PII. Convert the six f-string log calls to lazy `%s` args.

### Overall Assessment

- **Quality Rating:** **Good** — genuinely solid on the fundamentals this exercise targets: parameterized
  queries throughout, validation extracted into three reusable helpers, complete Args/Returns/Raises
  docstrings, specific-exception-first ordering, `rollback()` on every write failure, `finally`-guaranteed
  cleanup, and `rowcount` returned so callers can detect a no-op update. Held back from Excellent by the
  ~60 lines of copy-pasted error ladder, the exception-type laundering that undoes its own careful
  `IntegrityError`/`OperationalError` split, and the dead audit trail — not by anything unsafe.
- **Security Rating:** **Low Risk** — the injection class is fully closed at two independent layers
  (parameter binding *and* format validation), which is real defense in depth. Residual findings are
  hardening rather than exploitable holes: the `bool`-as-`user_id` coercion is the sharpest (it can rewrite
  the admin row, but only from an already-authorized caller), and the enumeration hint plus raw SQLite text
  in propagated messages matter only once these methods sit behind an HTTP boundary. **This becomes Medium
  Risk the moment the log level is lowered to `INFO`** without also removing the email interpolation at
  `:101`/`:149` — which is exactly what fixing the audit-trail defect requires, so sequence those two
  changes together.
- **Recommendation:** **Modify** — the architecture is sound and worth keeping; no rewrite. Four targeted
  changes clear everything above: (1) reject `bool` and switch to `re.fullmatch` + `.strip().lower()`
  normalization; (2) collapse the three duplicated ladders into one `@contextmanager`; (3) add the
  exception hierarchy with `raise ... from e`; (4) move `basicConfig` to the entry point and log `user_id`
  instead of `email`.
- **Reasoning:** Judged against the exercise's own four Common Issues, this code passes all four: no string
  concatenation in SQL, validation on every public method, error handling present, no connection leaks. The
  remaining defects are one tier up — maintainability and API contract quality rather than vulnerability
  classes — and the single highest-value fix is the exception hierarchy, because bare `Exception` is what
  forces every caller into `except Exception` and quietly discards the `IntegrityError`-vs-`OperationalError`
  distinction the code went to the trouble of making. Two housekeeping items fall outside the template but
  should ship with the fix: `starter/test_database_security.py` is now **inverted** — 5 of its 10 tests
  assert the vulnerabilities are still present and fail because they are not, so it must be rewritten to
  assert secure behavior (`solution/test_secure_database.py` passes 14/14 and is the model); and
  `starter/test.db` is a committed 0-byte SQLite artifact with no tables that should be deleted and
  gitignored, since the tests all build their own database via `tempfile`.


## Key Learning Points

- SQL injection occurs when user input is directly concatenated into queries
- Parameterized queries prevent SQL injection attacks
- Input validation should happen before database operations
- Database connections should be properly managed and closed

## Common Issues to Look For

1. **String concatenation** in SQL queries instead of parameterized queries
2. **No input validation** for user-provided data
3. **Missing error handling** for database operations
4. **Connection leaks** from unclosed database connections
5. **Generic exception handling** that hides specific database errors

After completing your review, check the solution to see the improved version with parameterized queries, proper input validation, and secure database practices.