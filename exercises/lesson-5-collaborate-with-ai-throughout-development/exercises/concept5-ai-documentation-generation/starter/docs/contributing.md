# Contributing

How to set up a development environment, work on the code, and get a change accepted.

New to the codebase? Read [Architecture](architecture.md) first — it explains the layering and names the known rough edges, several of which are good first contributions.

## Contents

- [Development setup](#development-setup)
- [Project conventions](#project-conventions)
- [Code style](#code-style)
- [Docstring standards](#docstring-standards)
- [Running the tests](#running-the-tests)
- [Writing tests](#writing-tests)
- [Known issue: documentation quality tests](#known-issue-documentation-quality-tests)
- [Debugging](#debugging)
- [Submitting a change](#submitting-a-change)
- [Good first contributions](#good-first-contributions)
- [Release process](#release-process)

---

## Development setup

### Requirements

- **Python 3.10 or newer** — a hard floor, see [the note below](#why-310)
- **`pytest`** — the only development dependency
- **`git`**

### Setup

```bash
git clone <repository-url>
cd expense-tracker

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install pytest
```

Verify:

```bash
python3 main.py examples/sample_expenses.csv    # prints a category report
python3 -m pytest tests/ -q                     # 55 passed, 6 skipped
```

Both should succeed before you change anything. There is no build step, no linter config, no `setup.py`, and no `requirements.txt` — the application itself has zero third-party dependencies and that is worth preserving.

### Why 3.10?

The source uses PEP 604 unions in annotations that Python evaluates at import time:

```python
def run(self, args: list[str] | None = None) -> int:      # cli.py
def __init__(self, message: str, row_number: int | None = None)   # exceptions.py
column_widths: Dict[str, int] | None = None               # formatters.py
```

There is no `from __future__ import annotations`, so these are evaluated, not strings. On 3.9 and earlier the package fails at import. If you want to support older versions, add the `__future__` import to every module rather than rewriting the annotations — but check first whether that is wanted, since 3.10 has been the floor since this code was written.

### No dependencies, please

The application must keep running on a bare Python install. That constraint is why `report_mode.py` formats tables with f-strings instead of using `rich` or `tabulate`, and it is deliberate: the tool should work on a locked-down machine with no network access. Development-only dependencies (`pytest`, a formatter, a type checker) are fine; runtime dependencies need a strong argument.

---

## Project conventions

Read [Architecture](architecture.md#layers-and-dependency-rules) for the full rules. The two that matter most in review:

**`domain/` imports nothing from the project.** `models.py` and `exceptions.py` depend only on the standard library. Everything else may depend on them. If a change makes `domain/` import from `data/` or `reports/`, the logic is in the wrong place.

**Only `cli.py` touches the outside world.** No `print()`, no `input()`, no `sys.exit()`, no file writing anywhere else. Reports *return* strings; the CLI prints them. This is what keeps the rest of the codebase testable without capturing stdout, so a `print()` added to a report class will be asked about in review.

Alongside those:

- **`Decimal` for money, never `float`.** Construct from strings — `Decimal('42.50')`, never `Decimal(42.50)`. See [the JSON example](architecture.md#adding-a-data-source) for how easily a float sneaks in at a parsing boundary.
- **Validate at the boundary, trust afterwards.** `Transaction.__post_init__` guarantees validity, so aggregation code does not re-check. Don't add defensive checks downstream; fix the boundary.
- **Fail fast on bad data.** One malformed row aborts the load. Don't add skip-and-continue behaviour without discussion — a silently dropped row makes every total quietly wrong. The intended path for a lenient mode is `ValidationResult`, which exists unused for this purpose.
- **New exceptions subclass `ExpenseTrackerError`,** and get a handler in `run()`. Without one they fall to the generic handler and report exit code 3.

---

## Code style

PEP 8, as the existing code follows it. No formatter is configured; match the surrounding file.

- **Four-space indents**, no tabs.
- **Lines under ~88 characters.** Not enforced, but the codebase stays near it.
- **Type hints on every public signature,** including return types. `-> None` where nothing is returned.
- **Naming:** `snake_case` for functions and variables, `PascalCase` for classes, `_leading_underscore` for private helpers, `UPPER_CASE` for class constants (`REQUIRED_COLUMNS`).
- **Import order:** standard library, then blank line, then project imports. Project imports use full paths (`from expense_tracker.domain.models import Transaction`), never relative ones.
- **Explicit exception chaining.** Use `raise ... from e` when re-raising, as the loader does throughout. It preserves the original traceback.
- **Catch narrowly.** `except (InvalidOperation, ValueError)`, not bare `except:`. The single deliberate catch-all is `run()`'s last resort, and it reports rather than swallows.
- **f-strings** for interpolation, not `%` or `.format()`.
- **Comments explain why.** The code says what it does; a comment earns its place by saying why. The existing `# Start at 2 (header is row 1)` is a good example.

---

## Docstring standards

**Google style**, as used throughout. Every module, public class, and public method needs one; private helpers need one when the logic is non-obvious.

**Module level** — purpose, and a usage example where it helps:

```python
"""
Abstract interface for report generation strategies.

This module implements the Strategy pattern for different report types,
following the Open/Closed Principle for easy extensibility.

Example Usage:
    >>> report = CategorySummaryReport()
    >>> output = report.process_transactions(transactions)
    >>> print(output)
"""
```

**Class level** — what it is, when to use it, and its output shape if it produces one. The report classes document their column layout, which is genuinely useful.

**Method level** — one-line summary, then `Args:`, `Returns:`, `Raises:`, and `Example:` where the call is non-obvious:

```python
def load(self, source: str) -> List[Transaction]:
    """
    Load transactions from CSV file.

    Args:
        source: Path to CSV file (absolute or relative)

    Returns:
        List of validated Transaction objects in file order.
        Returns empty list if file contains only headers.

    Raises:
        DataLoadError: If file not found, cannot be read, or is empty
        ValidationError: If CSV structure invalid or data fails validation
    """
```

List **every** exception a caller can see, including ones raised by code you call. `Raises:` is the contract most likely to be relied on and most likely to go stale.

### Two rules learned from this codebase

**Never write an example you have not run.** `formatters.format_table()` carries a docstring with a worked example and plausible output — and the function body raises `NotImplementedError`. The example was never executed, so nobody noticed. If you document output, produce it by running the code and paste the real thing.

**Don't describe intent the code doesn't implement.** `ExpenseTrackerCLI`'s docstring claims "Dependency Injection (dependencies passed to methods)", but `run()` constructs `CSVTransactionLoader()` itself. A docstring describing the design you wanted is worse than none, because readers trust it. Either fix the code or describe what it does.

When you change behaviour, update the docstring in the same commit. When you notice a docstring that lies, fixing it is a welcome standalone change.

---

## Running the tests

```bash
python3 -m pytest tests/ -q               # everything
python3 -m pytest tests/ -v               # per-test names
python3 -m pytest tests/test_cli.py -v    # one file
python3 -m pytest tests/ -k "category"    # by name
python3 -m pytest tests/ -rs              # show skip reasons
python3 -m pytest tests/ -x               # stop at first failure
```

Expected: **55 passed, 6 skipped**. The six skips are explained [below](#known-issue-documentation-quality-tests) and are not your fault.

Run from the project root — imports are absolute (`expense_tracker.…`) and resolve against the current directory.

The suite runs in well under a second, so run it on every change rather than at the end.

`unittest` works too, since the tests are `TestCase` classes:

```bash
python3 -m unittest discover tests -v
```

`pytest` is preferred; it is what the skip markers in `test_documentation_quality.py` rely on.

---

## Writing tests

Every behaviour change needs a test. Put it in the file matching the module:

| Module changed | Test file |
|---|---|
| `domain/models.py` | `tests/test_models.py` |
| `data/transaction_loader.py` | `tests/test_csv_loader.py` |
| `reports/report_mode.py` | `tests/test_report_modes.py` |
| `reports/report_factory.py` | `tests/test_report_factory.py` |
| `cli.py` | `tests/test_cli.py` |

### Follow the existing pattern

`unittest.TestCase` classes with `setUp()` building shared fixtures:

```python
import unittest
from datetime import date
from decimal import Decimal

from expense_tracker.domain.models import Transaction
from expense_tracker.reports.report_mode import CategorySummaryReport
from expense_tracker.domain.exceptions import EmptyDatasetError


class TestCategorySummaryReport(unittest.TestCase):

    def setUp(self):
        self.transactions = [
            Transaction(date(2025, 1, 15), Decimal('42.50'), 'Food', 'Lunch'),
            Transaction(date(2025, 1, 16), Decimal('35.00'), 'Food', 'Dinner'),
        ]

    def test_groups_by_category(self):
        output = CategorySummaryReport().process_transactions(self.transactions)
        self.assertIn('Food', output)
        self.assertIn('77.50', output)

    def test_empty_raises(self):
        with self.assertRaises(EmptyDatasetError):
            CategorySummaryReport().process_transactions([])
```

### What to test where

**Domain and reports need no mocking.** Build `Transaction` objects, call the method, assert on the returned string. This works because reports return strings instead of printing — don't break that.

**Assert on content, not exact layout.** `assertIn('77.50', output)` survives a column-width change; comparing the whole report string does not. Reserve full-output comparison for tests specifically about formatting.

**Loaders are tested against real temporary files,** not a mocked filesystem — `csv` behaviour, encoding, and `Path` semantics are the likely breakages, and mocking them tests the mock. Use `tempfile` or add a fixture to `tests/fixtures/`.

**Cover the failure paths.** For a loader change that means: happy path, missing file, empty file, missing column, malformed row, and the `row_number` on the resulting `ValidationError`.

### Two traps

**`argparse` raises `SystemExit`, which is a `BaseException`.** It passes straight through `run()`'s handlers, so a bad-argument test must expect the exception rather than a return code:

```python
def test_missing_file_argument_exits(self):
    with self.assertRaises(SystemExit) as ctx:
        ExpenseTrackerCLI().run([])
    self.assertEqual(ctx.exception.code, 2)
```

**`ReportFactory._registry` is class-level shared state.** A `register_report()` call persists for the whole process and is visible to every later test. Clean up, or use a name nothing else uses:

```python
def tearDown(self):
    ReportFactory._registry.pop('test_report', None)
```

---

## Known issue: documentation quality tests

`tests/test_documentation_quality.py` reports **6 passed, 6 skipped** when run alone, and every one of those results is misleading. Its paths were written for a different project layout — a flat set of modules in a sibling `solution/` directory — and were never updated for this package structure.

What actually happens:

| Test group | Result | Why |
|---|---|---|
| `TestReadmeQuality` (4 tests) | Pass | Reads `../solution/README.md`, which exists — **the copy in `solution/`, not the `README.md` you edit in `starter/`** |
| `TestArchitectureDocQuality` (4 tests) | Skip | Looks for `../solution/ARCHITECTURE.md`; the architecture doc lives at `docs/architecture.md` |
| `test_transaction_loader_has_module_docstring` | Skip | Looks for `../solution/transaction_loader.py`; the real path is `expense_tracker/data/transaction_loader.py` |
| `test_report_modes_has_module_docstring` | Skip | Looks for `../solution/report_modes.py`; the real file is `expense_tracker/reports/report_mode.py` (singular) |
| `test_classes_have_docstrings` | Pass **vacuously** | Its four paths all miss, the loop `continue`s over each, and it asserts that an empty list is empty |

So the README checks grade the wrong file, and the one test that would catch a missing class docstring passes without examining a single class. **Do not read a green result here as documentation coverage.**

The checks themselves are reasonable; only the paths are wrong. Fixing it means pointing them at real files:

```python
DOCS = Path(__file__).resolve().parent.parent
README = DOCS / 'README.md'
ARCHITECTURE = DOCS / 'docs' / 'architecture.md'
SOURCE_FILES = [
    DOCS / 'expense_tracker' / 'data' / 'transaction_loader.py',
    DOCS / 'expense_tracker' / 'reports' / 'report_mode.py',
    DOCS / 'expense_tracker' / 'reports' / 'report_factory.py',
    DOCS / 'expense_tracker' / 'cli.py',
]
```

Anchoring on `__file__` rather than the process working directory also makes the suite pass from any directory, which the current relative paths do not.

This is deliberately left unfixed — the file is exercise scaffolding, and repairing it is [a good first contribution](#good-first-contributions). Until then, the six skips are expected and the two vacuous passes are known.

---

## Debugging

**Start with the exit code** — it localises the failure before you read anything:

```bash
python3 main.py expenses.csv; echo "exit=$?"
```

`1` is load or validation, `2` is arguments, `3` is an empty dataset, `130` is Ctrl+C. The full table is in [Troubleshooting](troubleshooting.md).

**Get a real traceback.** `run()` catches everything, so the stack is hidden by design. Bypass it:

```python
from expense_tracker.data.transaction_loader import CSVTransactionLoader
from expense_tracker.reports.report_factory import ReportFactory

txns = CSVTransactionLoader().load('expenses.csv')      # traceback on failure
print(ReportFactory.create_report('category').process_transactions(txns))
```

Or temporarily add `raise` inside the handler you are investigating in `cli.py`. The catch-all at `cli.py:193` has a `# In production, log full traceback here` comment marking the spot.

**Isolate the layer.** Loading and reporting are independent, so find out which one is wrong:

```bash
python3 -c "
from expense_tracker.data.transaction_loader import CSVTransactionLoader
t = CSVTransactionLoader().load('expenses.csv')
print(len(t), 'loaded'); print(t[0]); print(sum(x.amount for x in t))
"
```

If the count and sum are right, the bug is in a report. If not, it's the loader or the data.

**Check for `float` contamination** when totals are off by tiny amounts:

```bash
python3 -c "
from expense_tracker.data.transaction_loader import CSVTransactionLoader
for t in CSVTransactionLoader().load('expenses.csv'):
    if not isinstance(t.amount, __import__('decimal').Decimal): print('NOT DECIMAL:', t)
"
```

**Use `pytest --pdb`** to drop into a debugger at a failure, and `-x` to stop at the first one.

---

## Submitting a change

### Before you open a pull request

- [ ] `python3 -m pytest tests/ -q` → **55 passed, 6 skipped** (plus your new tests)
- [ ] New behaviour has a test; changed behaviour has an updated test
- [ ] Public signatures have type hints and Google-style docstrings
- [ ] Every example in a docstring or doc was **run**, and the output pasted is real
- [ ] No new runtime dependency
- [ ] `domain/` still imports nothing from the project
- [ ] Nothing outside `cli.py` prints, exits, or writes files
- [ ] Money is `Decimal`, built from strings
- [ ] `python3 main.py examples/sample_expenses.csv` still works for all three reports
- [ ] Affected docs updated — see the table below

### Documentation that goes stale

| Change | Also update |
|---|---|
| New report type | [`README.md`](../README.md), [User Guide](user_guide.md#the-three-reports), [API Reference](api_reference.md), `--help` epilogue in `cli.py` |
| New or changed CLI flag | [`README.md`](../README.md), [User Guide](user_guide.md#command-reference), `--help` epilogue |
| New exception or exit code | [Troubleshooting](troubleshooting.md), [API Reference](api_reference.md#exception-to-exit-code-mapping), [`README.md`](../README.md) |
| CSV validation rule | [User Guide](user_guide.md#csv-file-format), [Troubleshooting](troubleshooting.md) |
| Structural refactor | [Architecture](architecture.md) — including its [Known structural issues](architecture.md#known-structural-issues) if you fixed one |
| Minimum Python version | [`README.md`](../README.md), [User Guide](user_guide.md#prerequisites), this file |

### Commits

One logical change per commit. Imperative mood, under ~72 characters on the subject line, with a body explaining *why* when it isn't obvious:

```
Add weekday report mode

Groups transactions by day of week to expose weekend spending
patterns, which neither the category nor monthly report reveals.
```

### Pull requests

Say what changed, why, and how you verified it. Paste real command output for anything user-visible. If you fixed something from [Known structural issues](architecture.md#known-structural-issues), link it. If review turns up disagreement about layering or the no-dependencies rule, raise it as a question rather than working around it — those two constraints shape everything else.

---

## Good first contributions

Each of these is real, scoped, and already analysed in [Architecture](architecture.md#known-structural-issues).

**Fix the documentation quality tests.** Repoint `test_documentation_quality.py` at real paths, anchored on `__file__`. Turns six skips and two vacuous passes into genuine checks. Smallest useful change in the repo. ([details](#known-issue-documentation-quality-tests))

**Make `--report` choices come from the registry.** Replace the hardcoded list in `cli.py` with `ReportFactory.get_available_types()`. Removes a duplicated source of truth and makes `register_report()` actually reach the CLI. ([details](architecture.md#--report-choices-duplicate-the-factory-registry))

**Validate `--top-n` properly.** `--top-n 0` currently surfaces as `Unexpected error: top_n must be positive, got 0` with exit code 1, because `TopExpensesReport` raises a plain `ValueError`. Make it a `ValidationError`, or validate in `argparse` with a `type=` callable. ([details](architecture.md#valueerror-escapes-the-error-hierarchy))

**Fix the `TopExpensesReport` heading.** `--top-n 100` over 20 transactions prints `Top 100 Expenses Report` above `TOTAL (top 20)`. Use the real count. ([details](architecture.md#topexpensesreport-heading-can-contradict-its-total))

**Make dependency injection real.** Add an optional `loader` parameter to `ExpenseTrackerCLI.__init__`. Matches the docstring's existing claim, removes the need to patch in tests, and prepares for alternative data sources. ([details](architecture.md#run-hardcodes-its-dependencies))

**Resolve the presentation layer.** Either implement `format_table()`, fix `format_header()`'s ignored `width`, and refactor the reports to use these helpers — which would remove the column-layout logic duplicated across `report_mode.py` — or delete the module. Largest of these, and worth discussing in an issue first. ([details](architecture.md#the-unused-presentation-layer))

**Add a report type.** The [step-by-step walkthrough](architecture.md#adding-a-report-type) includes a complete working `WeekdayReport`. Good way to learn the layering.

---

## Release process

The project is versioned with [semantic versioning](https://semver.org/) and its history is in [`docs/CHANGELOG.md`](CHANGELOG.md).

**MAJOR** — a breaking change to the CSV format, the CLI surface, or the public API, including a raised minimum Python version.
**MINOR** — a new report, flag, or data source, backward compatible.
**PATCH** — bug fixes and documentation.

To cut a release:

1. Confirm `python3 -m pytest tests/ -q` is clean.
2. Run all three reports against `examples/sample_expenses.csv` and check the output by eye.
3. Move the `CHANGELOG.md` unreleased entries under a new version heading with today's date, grouped as Added / Changed / Fixed / Removed.
4. Verify the docs table above was honoured for everything in the release.
5. Commit as `Release vX.Y.Z`, tag `vX.Y.Z`, push with `--tags`.

Being a dependency-free, single-file-entry-point tool, there is nothing to publish or build — a tag is the release.
