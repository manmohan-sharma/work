# API Reference

Developer reference for using `expense_tracker` as a library rather than through the CLI. Every signature, return value, and exception below was read from the source and exercised against the running code.

For *why* the pieces fit together the way they do, read [Architecture](architecture.md) first — this document is the flat reference.

## Contents

- [Package layout](#package-layout)
- [Quick start as a library](#quick-start-as-a-library)
- [`expense_tracker.domain.models`](#expense_trackerdomainmodels)
- [`expense_tracker.domain.exceptions`](#expense_trackerdomainexceptions)
- [`expense_tracker.data.transaction_loader`](#expense_trackerdatatransaction_loader)
- [`expense_tracker.reports.report_mode`](#expense_trackerreportsreport_mode)
- [`expense_tracker.reports.report_factory`](#expense_trackerreportsreport_factory)
- [`expense_tracker.cli`](#expense_trackercli)
- [`expense_tracker.presentation.formatters`](#expense_trackerpresentationformatters)
- [Exception-to-exit-code mapping](#exception-to-exit-code-mapping)

---

## Package layout

| Module | Contents |
|---|---|
| `expense_tracker.domain.models` | `Transaction`, `ValidationResult` |
| `expense_tracker.domain.exceptions` | Exception hierarchy |
| `expense_tracker.data.transaction_loader` | `TransactionLoader`, `CSVTransactionLoader` |
| `expense_tracker.reports.report_mode` | `ReportMode`, `CategorySummaryReport`, `MonthlyTotalsReport`, `TopExpensesReport` |
| `expense_tracker.reports.report_factory` | `ReportFactory` |
| `expense_tracker.cli` | `ExpenseTrackerCLI`, `main` |
| `expense_tracker.presentation.formatters` | Formatting helpers — **not used by the CLI**, see [the module's notes](#expense_trackerpresentationformatters) |

All `__init__.py` files are empty, so there are no package-level re-exports. Import from the full module path.

**Requires Python 3.10+.** Annotations such as `list[str] | None` in `cli.py` and `int | None` in `exceptions.py` are evaluated at import time and are syntax errors on earlier versions.

---

## Quick start as a library

```python
from expense_tracker.data.transaction_loader import CSVTransactionLoader
from expense_tracker.reports.report_factory import ReportFactory

transactions = CSVTransactionLoader().load('examples/sample_expenses.csv')
report = ReportFactory.create_report('category')
print(report.process_transactions(transactions))
```

Three steps, always in this order: load transactions, choose a report strategy, process. The loader knows nothing about reports, and the reports know nothing about CSV.

---

## `expense_tracker.domain.models`

Core data structures. No dependencies on any other project module.

### `class Transaction`

```python
@dataclass(frozen=True)
class Transaction:
    date: datetime.date
    amount: decimal.Decimal
    category: str
    description: str
```

One expense. A frozen dataclass, so instances are immutable and hashable — assigning to a field raises `dataclasses.FrozenInstanceError`.

**Fields**

| Field | Type | Constraint |
|---|---|---|
| `date` | `datetime.date` | None |
| `amount` | `Decimal` | Must be `> 0` |
| `category` | `str` | Must be non-empty after stripping |
| `description` | `str` | Must be non-empty after stripping |

**Raises**

- `ValueError` — from `__post_init__`, if `amount <= 0`, or if `category` or `description` is empty or whitespace-only. Messages are `Amount must be positive, got 0`, `Category cannot be empty`, and `Description cannot be empty`.

**Example**

```python
>>> from datetime import date
>>> from decimal import Decimal
>>> from expense_tracker.domain.models import Transaction
>>> t = Transaction(date(2025, 1, 15), Decimal('42.50'), 'Food', 'Lunch at cafe')
>>> t
Transaction(date=datetime.date(2025, 1, 15), amount=Decimal('42.50'), category='Food', description='Lunch at cafe')
>>> t.amount = Decimal('1')
Traceback (most recent call last):
  ...
dataclasses.FrozenInstanceError: cannot assign to field 'amount'
>>> Transaction(date(2025, 1, 1), Decimal('0'), 'Food', 'x')
Traceback (most recent call last):
  ...
ValueError: Amount must be positive, got 0
```

Pass `amount` as `Decimal`, constructed from a **string** (`Decimal('42.50')`, not `Decimal(42.50)`). Building one from a float reintroduces the binary rounding error that using `Decimal` exists to avoid. Nothing in the class enforces this — it is on the caller.

### `class ValidationResult`

```python
@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: list[str]
    row_number: Optional[int] = None
```

A validation outcome carrying its error messages. Frozen and immutable.

> **Not used anywhere in the codebase.** `CSVTransactionLoader` reports problems by raising `ValidationError` rather than returning a `ValidationResult`. The class is available for callers who want accumulated, non-fatal validation, but no shipped code path produces one.

**Class methods**

#### `ValidationResult.success() -> ValidationResult`

A passing result: `is_valid=True`, `errors=[]`, `row_number=None`.

#### `ValidationResult.failure(*errors: str, row_number: Optional[int] = None) -> ValidationResult`

A failing result from one or more messages.

```python
>>> from expense_tracker.domain.models import ValidationResult
>>> ValidationResult.success()
ValidationResult(is_valid=True, errors=[], row_number=None)
>>> ValidationResult.failure('Invalid date format', row_number=5)
ValidationResult(is_valid=False, errors=['Invalid date format'], row_number=5)
```

---

## `expense_tracker.domain.exceptions`

```
Exception
└── ExpenseTrackerError
    ├── DataLoadError
    ├── ValidationError
    ├── InvalidReportTypeError
    └── EmptyDatasetError
```

Catching `ExpenseTrackerError` catches everything this package raises deliberately. `ValueError`, `TypeError`, and `FrozenInstanceError` from the model and factory layers are *not* part of this hierarchy and escape such a handler — see [the mapping table](#exception-to-exit-code-mapping).

### `class ExpenseTrackerError(Exception)`

Base for all package errors. Never raised directly.

### `class DataLoadError(ExpenseTrackerError)`

The source could not be read. Raised for a missing path, a path that is not a file, an empty file, a permission error, an encoding error, a CSV parse error, or any other `OSError`.

### `class ValidationError(ExpenseTrackerError)`

```python
def __init__(self, message: str, row_number: int | None = None)
```

Data was read but broke a rule.

**Attributes**

- `row_number` — `int | None`, the originating CSV row, or `None` for file-level problems.

When `row_number` is given, the message is prefixed with `Row {n}: `. Row numbers count the header as row 1, so the first data row is 2.

```python
>>> from expense_tracker.domain.exceptions import ValidationError
>>> e = ValidationError("Amount field is empty", row_number=7)
>>> str(e)
'Row 7: Amount field is empty'
>>> e.row_number
7
>>> str(ValidationError("CSV file has no header row"))
'CSV file has no header row'
```

### `class InvalidReportTypeError(ExpenseTrackerError)`

```python
def __init__(self, report_type: str, available_types: list[str])
```

An unregistered report type was requested. Note the constructor takes **two required arguments**, not a message.

**Attributes**

- `report_type` — the invalid name requested
- `available_types` — the valid names

The message is assembled for you:

```python
>>> from expense_tracker.domain.exceptions import InvalidReportTypeError
>>> str(InvalidReportTypeError('weekly', ['category', 'monthly', 'top']))
"Unknown report type 'weekly'. Available: category, monthly, top"
```

> **Unreachable from the CLI.** `argparse` restricts `--report` with `choices`, so a bad value is rejected with exit code 2 before the factory is called. This exception only surfaces when calling `ReportFactory.create_report()` directly, or after registering types that `argparse` does not know about.

### `class EmptyDatasetError(ExpenseTrackerError)`

There is nothing to report on. Raised by `ExpenseTrackerCLI.run()` when the loader returns an empty list, and by every `ReportMode.process_transactions()` implementation when handed `[]`.

---

## `expense_tracker.data.transaction_loader`

### `class TransactionLoader(ABC)`

The contract for any transaction source. Subclass it to read from a database, an API, or another file format without touching existing code.

#### `load(source: str) -> List[Transaction]` — abstract

Read, validate, and return transactions from `source`, preserving source order. Returns `[]` if the source holds no records.

**Raises** `DataLoadError` if the source cannot be accessed; `ValidationError` if a record breaks a rule.

#### `validate_source(source: str) -> bool` — abstract

Cheap pre-flight check. Returns `True` if the source exists and is readable, `False` otherwise. Contractually raises nothing — implementations must swallow access errors and return `False`.

### `class CSVTransactionLoader(TransactionLoader)`

Loads from a UTF-8 CSV file with a header row.

**Class attribute**

```python
REQUIRED_COLUMNS = {'date', 'amount', 'category', 'description'}
```

A `set`, so **column order in the file is irrelevant** and extra columns are ignored. Rows are read with `csv.DictReader` and matched by header name.

#### `load(source: str) -> List[Transaction]`

Reads the whole file into memory, validating every row. **Fails fast:** the first bad row aborts the load, so either you get every transaction or you get an exception.

**Parameters**

- `source` — path to the CSV file, absolute or relative.

**Returns** a list of `Transaction` in file order. `[]` if the file has only a header.

**Raises**

| Exception | Condition |
|---|---|
| `DataLoadError` | Path missing (`File not found: …`) |
| `DataLoadError` | Path is a directory (`Path is not a file: …`) |
| `DataLoadError` | File is zero bytes (`File is empty: …`) |
| `DataLoadError` | `PermissionError`, `UnicodeDecodeError`, `csv.Error`, or `OSError` while reading |
| `ValidationError` | No header row (`CSV file has no header row`) |
| `ValidationError` | A required column is absent (`CSV missing required columns: category`) |
| `ValidationError` | A row fails validation — carries `row_number` |

**Example**

```python
>>> from expense_tracker.data.transaction_loader import CSVTransactionLoader
>>> loader = CSVTransactionLoader()
>>> transactions = loader.load('examples/sample_expenses.csv')
>>> len(transactions)
20
>>> transactions[0]
Transaction(date=datetime.date(2025, 1, 5), amount=Decimal('52.30'), category='Food', description='Weekly groceries')
```

Handling both failure modes separately:

```python
from expense_tracker.domain.exceptions import DataLoadError, ValidationError

try:
    transactions = loader.load('expenses.csv')
except DataLoadError as e:
    print(f"Could not read the file: {e}")
except ValidationError as e:
    if e.row_number:
        print(f"Bad data on row {e.row_number}: {e}")
    else:
        print(f"Bad file structure: {e}")
```

#### `validate_source(source: str) -> bool`

Checks existence, that the path is a file, and that it opens for reading. Does **not** inspect content — a file with the wrong columns still returns `True`.

```python
>>> loader.validate_source('examples/sample_expenses.csv')
True
>>> loader.validate_source('nope.csv')
False
>>> loader.validate_source('examples')      # a directory
False
```

#### `_validate_and_create_transaction(row: dict, row_number: int) -> Transaction`

Private. Validates one `DictReader` row and returns a `Transaction`. Documented because subclasses may want to reuse the rules.

Order of operations, which determines which error you see first:

1. Read the four fields, `.strip()` each, defaulting missing keys to `''`.
2. Raise `ValidationError` for any empty field — checked `date`, `amount`, `category`, `description` in that order.
3. Parse `date` with `date.fromisoformat()`. Failure → `Invalid date format '…' (expected YYYY-MM-DD)`.
4. Parse `amount` with `Decimal()`. Failure → `Invalid amount '…' (must be a number)`.
5. Reject `amount <= 0` → `Amount must be positive, got …`.
6. Construct the `Transaction`, converting any `ValueError` from `__post_init__` into a `ValidationError` with the row number attached.

Because whitespace is stripped first, ` 52.30 ` is valid. Because `Decimal()` is strict, `$52.30` and `1,200.00` are not.

---

## `expense_tracker.reports.report_mode`

Report strategies. Each is independent, stateless apart from its constructor options, and returns a finished string.

### `class ReportMode(ABC)`

#### `process_transactions(transactions: List[Transaction]) -> str` — abstract

Analyse the transactions and return a formatted, multi-line, terminal-ready report.

**Raises** `EmptyDatasetError` if `transactions` is empty. Every shipped implementation checks this first.

#### `get_report_name() -> str` — abstract

A short human-readable label for the report.

### `class CategorySummaryReport(ReportMode)`

Constructor takes no arguments.

Groups by `category`; computes total, count, and mean per group; sorts by total descending; appends a grand-total row.

```python
>>> from datetime import date
>>> from decimal import Decimal
>>> from expense_tracker.domain.models import Transaction
>>> from expense_tracker.reports.report_mode import CategorySummaryReport
>>> txns = [
...     Transaction(date(2025, 1, 15), Decimal('42.50'), 'Food', 'Lunch'),
...     Transaction(date(2025, 1, 16), Decimal('35.00'), 'Food', 'Dinner'),
...     Transaction(date(2025, 1, 17), Decimal('120.00'), 'Transport', 'Metro'),
... ]
>>> print(CategorySummaryReport().process_transactions(txns))
Category Summary Report
==================================================
Category                    Total    Count        Avg
--------------------------------------------------
Transport            $     120.00        1 $   120.00
Food                 $      77.50        2 $    38.75
--------------------------------------------------
TOTAL                $     197.50        3 $    65.83
```

`get_report_name()` returns `'Category Summary'`. Output is 50 characters wide.

### `class MonthlyTotalsReport(ReportMode)`

Constructor takes no arguments.

Groups by `date.strftime('%Y-%m')`; computes total, count, and mean per month; sorts chronologically by the string key. Months with no transactions are omitted rather than shown as zero.

```python
>>> from expense_tracker.reports.report_mode import MonthlyTotalsReport
>>> txns = [
...     Transaction(date(2025, 1, 15), Decimal('100.00'), 'Food', 'Lunch'),
...     Transaction(date(2025, 2, 10), Decimal('200.00'), 'Transport', 'Metro'),
... ]
>>> print(MonthlyTotalsReport().process_transactions(txns))
Monthly Totals Report
==================================================
Month                  Total    Count        Avg
--------------------------------------------------
2025-01         $     100.00        1 $   100.00
2025-02         $     200.00        1 $   200.00
--------------------------------------------------
TOTAL           $     300.00        2 $   150.00
```

`get_report_name()` returns `'Monthly Totals'`. Output is 50 characters wide.

### `class TopExpensesReport(ReportMode)`

```python
def __init__(self, top_n: int = 10)
```

Sorts all transactions by amount descending and lists the first `top_n` with full detail.

**Parameters**

- `top_n` — how many rows to show. Default `10`.

**Raises** `ValueError` at construction if `top_n < 1`: `top_n must be positive, got 0`. This is a plain `ValueError`, *not* an `ExpenseTrackerError`, so it escapes `except ExpenseTrackerError` handlers.

**Attributes**

- `top_n` — the configured limit, readable and writable.

```python
>>> from expense_tracker.reports.report_mode import TopExpensesReport
>>> txns = [
...     Transaction(date(2025, 1, 15), Decimal('450.00'), 'Electronics', 'New keyboard'),
...     Transaction(date(2025, 1, 22), Decimal('320.00'), 'Transport', 'Flight ticket'),
... ]
>>> print(TopExpensesReport(top_n=2).process_transactions(txns))
Top 2 Expenses Report
================================================================================
Date               Amount Category             Description
--------------------------------------------------------------------------------
2025-01-15 $     450.00 Electronics          New keyboard
2025-01-22 $     320.00 Transport            Flight ticket
--------------------------------------------------------------------------------
TOTAL (top 2)  $     770.00
```

`get_report_name()` returns `f'Top {top_n} Expenses'` — so `'Top 2 Expenses'` above.

Behaviour worth knowing:

- Descriptions over 30 characters are truncated to 27 plus `...`.
- If fewer than `top_n` transactions exist, all are shown and a trailing `Note: Only N transaction(s) available` is appended.
- In that case the **heading still shows the requested `top_n`** while the `TOTAL (top N)` line shows the real count. Asking for 100 of 20 prints `Top 100 Expenses Report` above `TOTAL (top 20)`. Cosmetic, but surprising in captured output.
- Output is 80 characters wide, unlike the other two reports' 50.
- Ties are ordered by Python's stable sort, i.e. original file order.

---

## `expense_tracker.reports.report_factory`

### `class ReportFactory`

Maps report names to strategy classes. All methods are class methods — there is no reason to instantiate it, though `ReportFactory().create_report(...)` works.

**Registry**

```python
_registry: Dict[str, Type[ReportMode]] = {
    'category': CategorySummaryReport,
    'monthly':  MonthlyTotalsReport,
    'top':      TopExpensesReport,
}
```

Private by convention. Mutate it through `register_report()`, and note that the registry is **class-level shared state**: a registration is visible to every caller in the process and persists for its lifetime.

#### `create_report(report_type: str, **kwargs) -> ReportMode` — classmethod

Instantiate a strategy by name. `**kwargs` is forwarded to the constructor.

**Raises** `InvalidReportTypeError` if `report_type` is not registered. Constructor errors propagate unchanged — an unexpected keyword raises `TypeError`, and `top_n=0` raises `ValueError`.

```python
>>> from expense_tracker.reports.report_factory import ReportFactory
>>> ReportFactory.create_report('category')
<expense_tracker.reports.report_mode.CategorySummaryReport object at 0x...>
>>> ReportFactory.create_report('top', top_n=3).get_report_name()
'Top 3 Expenses'
>>> ReportFactory.create_report('weekly')
Traceback (most recent call last):
  ...
expense_tracker.domain.exceptions.InvalidReportTypeError: Unknown report type 'weekly'. Available: category, monthly, top
```

#### `get_available_types() -> list[str]` — classmethod

Registered names, sorted alphabetically.

```python
>>> ReportFactory.get_available_types()
['category', 'monthly', 'top']
```

#### `register_report(name: str, strategy_class: Type[ReportMode]) -> None` — classmethod

Add a report type at runtime. The extension point for plugins and tests.

**Raises** `ValueError` if `name` is already registered (no silent overwrite); `TypeError` if `strategy_class` is not a `ReportMode` subclass.

Verified end to end:

```python
from typing import List
from expense_tracker.reports.report_mode import ReportMode
from expense_tracker.reports.report_factory import ReportFactory
from expense_tracker.data.transaction_loader import CSVTransactionLoader
from expense_tracker.domain.models import Transaction

class AverageReport(ReportMode):
    """Mean transaction size."""

    def process_transactions(self, transactions: List[Transaction]) -> str:
        total = sum(t.amount for t in transactions)
        return f'Mean: ${total / len(transactions):,.2f} over {len(transactions)} txns'

    def get_report_name(self) -> str:
        return 'Average'

ReportFactory.register_report('average', AverageReport)
print(ReportFactory.get_available_types())
# ['average', 'category', 'monthly', 'top']

txns = CSVTransactionLoader().load('examples/sample_expenses.csv')
print(ReportFactory.create_report('average').process_transactions(txns))
# Mean: $112.18 over 20 txns
```

Registering makes the type available to `create_report()`, but **not** to the CLI — `--report`'s `argparse` choices are a separate hardcoded list. See [Architecture](architecture.md#adding-a-report-type) for wiring a new report all the way through.

---

## `expense_tracker.cli`

### `class ExpenseTrackerCLI`

Argument parsing, orchestration, and error-to-exit-code translation. The only module that knows about `sys.exit`, `print`, or `argparse`.

#### `__init__()`

Builds the `argparse.ArgumentParser` into `self.parser`.

#### `run(args: list[str] | None = None) -> int`

Parse arguments, load, report, print. **Returns** an exit code; does not call `sys.exit()` itself, which is what makes it testable.

**Parameters**

- `args` — argument list without the program name. `None` means read `sys.argv[1:]`.

**Returns**

| Code | Meaning |
|---|---|
| `0` | Report printed to stdout |
| `1` | `DataLoadError`, `ValidationError`, or an unexpected exception |
| `2` | `InvalidReportTypeError`, or an `argparse` failure |
| `3` | `EmptyDatasetError` or another `ExpenseTrackerError` |
| `130` | `KeyboardInterrupt` |

Errors print to `stderr`; only the report goes to `stdout`, so redirecting stdout captures clean output.

```python
>>> from expense_tracker.cli import ExpenseTrackerCLI
>>> cli = ExpenseTrackerCLI()
>>> cli.run(['examples/sample_expenses.csv', '--report', 'monthly'])
Monthly Totals Report
...
0
>>> cli.run(['nope.csv'])
1
```

Two caveats:

- **`argparse` exits the process.** A bad flag or missing file argument makes `parse_args()` raise `SystemExit(2)`, which is a `BaseException` and passes straight through `run()`'s handlers. Calling `run()` in-process with invalid arguments terminates your program rather than returning `2`. Wrap it in `pytest.raises(SystemExit)` when testing that path.
- **The file-existence pre-check duplicates the loader's.** `run()` raises `DataLoadError` for a missing path before constructing the loader, so `CSVTransactionLoader.load()`'s own identical check is unreachable via the CLI.

#### `main() -> NoReturn`

Console entry point. Constructs the CLI, runs it, and calls `sys.exit()` with the result. Never returns. This is what `main.py` invokes.

---

## `expense_tracker.presentation.formatters`

Six module-level formatting helpers.

> **This module is dead code.** A `grep` for every function name across the project returns no hits outside this file: the report classes in `report_mode.py` build their output with inline f-strings instead. Nothing here is exercised by the CLI or by the test suite. Treat it as a utility library offered for reuse, not as the formatting layer the reports actually use — and see [Architecture](architecture.md#the-unused-presentation-layer) for what that means if you plan to refactor.

### `format_currency(amount: Decimal, symbol: str = '$') -> str`

Thousands-separated, two-decimal currency string.

```python
>>> format_currency(Decimal('1234.56'))
'$1,234.56'
>>> format_currency(Decimal('42.5'))
'$42.50'
>>> format_currency(Decimal('42.5'), symbol='EUR ')
'EUR 42.50'
```

The symbol is a bare prefix — include your own trailing space if you want one.

### `format_table(rows, headers, column_widths=None, align=None) -> str`

```python
def format_table(
    rows: List[Dict[str, Any]],
    headers: List[str],
    column_widths: Dict[str, int] | None = None,
    align: Dict[str, str] | None = None
) -> str
```

> **Not implemented.** Every call raises `NotImplementedError("format_table() must be implemented")`, regardless of arguments. Its docstring contains a worked example with plausible output; that output has never been produced by running code. Do not call this function.

### `format_separator(width: int = 80, char: str = '-') -> str`

A horizontal rule: `char` repeated `width` times.

```python
>>> format_separator(40, '=')
'========================================'
```

### `format_header(title: str, width: int = 80, underline_char: str = '=') -> str`

Title, newline, underline as long as the title.

```python
>>> print(format_header('Category Summary'))
Category Summary
================
```

> **The `width` parameter is ignored.** The implementation underlines with `underline_char * len(title)`, so `format_header('Short')` and `format_header('Short', width=10)` return identical strings. The parameter is accepted and discarded.

### `format_summary_line(label: str, value: str, width: int = 80) -> str`

`label` left-aligned, `value` right-aligned, padded to `width`.

```python
>>> format_summary_line('TOTAL', '$1,234.56', width=40)
'TOTAL                          $1,234.56'
```

If `len(label) + len(value)` exceeds `width` the padding count goes negative and `' ' * negative` yields `''`, so the two strings are concatenated with no separator and the result silently overruns `width`:

```python
>>> format_summary_line('LABEL', 'VALUE', width=3)
'LABELVALUE'
```

No exception is raised. Check your widths.

### `truncate_text(text: str, max_length: int, suffix: str = '...') -> str`

Shortens `text` to at most `max_length` characters *including* the suffix. Returns `text` unchanged when it already fits.

```python
>>> truncate_text('Very long description here', 15)
'Very long de...'
>>> truncate_text('Short', 15)
'Short'
```

With a `max_length` shorter than `suffix`, the slice index goes negative and the result is mangled rather than raising — pass sane values.

---

## Exception-to-exit-code mapping

How each failure reaches a user, and which ones a library caller must handle separately because they sit outside `ExpenseTrackerError`.

| Raised | By | Type | CLI exit code |
|---|---|---|---|
| `DataLoadError` | loader, CLI pre-check | `ExpenseTrackerError` | `1` |
| `ValidationError` | loader | `ExpenseTrackerError` | `1` |
| `InvalidReportTypeError` | factory | `ExpenseTrackerError` | `2` (unreachable via CLI) |
| `EmptyDatasetError` | CLI, report modes | `ExpenseTrackerError` | `3` |
| `ValueError` | `Transaction`, `TopExpensesReport` | **plain builtin** | `1`, as "Unexpected error" |
| `TypeError` | `ReportFactory` | **plain builtin** | `1`, as "Unexpected error" |
| `NotImplementedError` | `format_table` | **plain builtin** | `1`, as "Unexpected error" |
| `SystemExit` | `argparse` | **`BaseException`** | `2`, bypassing all handlers |
| `KeyboardInterrupt` | user | **`BaseException`** | `130` |

The practical consequence: `except ExpenseTrackerError` covers the four rows at the top and nothing else. `--top-n 0` surfaces as `Unexpected error: top_n must be positive, got 0` precisely because `ValueError` falls through to `run()`'s catch-all.
