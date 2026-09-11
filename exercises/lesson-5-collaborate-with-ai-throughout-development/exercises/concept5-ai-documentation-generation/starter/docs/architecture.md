# Architecture

How Expense Tracker is put together and why. Written for anyone modifying, extending, or debugging the code.

For flat signatures and return values, see [API Reference](api_reference.md). This document covers structure, patterns, rationale, and the places the design is imperfect.

## Contents

- [System overview](#system-overview)
- [Design principles](#design-principles)
- [Component diagram](#component-diagram)
- [Data flow](#data-flow)
- [Layers and dependency rules](#layers-and-dependency-rules)
- [Design patterns](#design-patterns)
- [Module reference](#module-reference)
- [Extension points](#extension-points)
  - [Adding a report type](#adding-a-report-type)
  - [Adding a data source](#adding-a-data-source)
- [Design decisions](#design-decisions)
- [Known structural issues](#known-structural-issues)
- [Testing strategy](#testing-strategy)
- [Performance characteristics](#performance-characteristics)
- [Security considerations](#security-considerations)

---

## System overview

Expense Tracker is a single-process, read-only command-line program. It reads a CSV file, aggregates the rows, and prints a text report to stdout. There is no state between runs, no configuration file, no network access, and no write path back to the user's data.

The whole system is roughly 1,500 lines of Python across eight modules, with no third-party dependencies. That size is worth stating up front, because it explains the shape of the design: the abstraction here exists to make the code *extensible and testable*, not to manage complexity that already exists.

```
CSV file  →  [ load & validate ]  →  List[Transaction]  →  [ aggregate & format ]  →  stdout
```

Three things happen, in a fixed order, and each is owned by a different layer that knows nothing about the others.

---

## Design principles

**Depend on abstractions, not implementations.** `ExpenseTrackerCLI` never names `CSVTransactionLoader` in a type annotation or `CategorySummaryReport` anywhere. It works against `TransactionLoader` and `ReportMode`. Swapping either is a change at the wiring point, not a change threaded through the call chain.

**Open for extension, closed for modification.** A new report type or data source arrives as a new class. No existing class body needs editing — with one exception documented under [Adding a report type](#adding-a-report-type).

**One reason to change per module.** Loading, aggregating, formatting, and user interaction are separate modules. A change to the CSV format touches one file. A change to how category totals are computed touches one file.

**Fail fast and loudly.** A single malformed row aborts the entire load rather than being skipped. A silently dropped row would make every total quietly wrong, and a wrong total that looks right is worse than an error message.

**Immutable domain objects.** `Transaction` is a frozen dataclass that validates in `__post_init__`. Once one exists it is valid, and it stays valid — no defensive re-checking downstream.

**Exact money arithmetic.** Every amount is a `Decimal`, never a `float`, from parse through aggregation to display.

---

## Component diagram

```
                        ┌───────────────┐
                        │    main.py    │   entry point
                        └───────┬───────┘
                                │ calls cli.main()
                                ▼
      ┌──────────────────────────────────────────────────┐
      │              ExpenseTrackerCLI                   │   cli.py
      │  · parse arguments (argparse)                    │
      │  · orchestrate the run                           │   the only module
      │  · map exceptions → exit codes                   │   that prints or exits
      │  · print report to stdout, errors to stderr      │
      └───┬──────────────────────┬───────────────────────┘
          │                      │
          │ depends on           │ depends on
          │ abstraction          │ abstraction
          ▼                      ▼
 ┌──────────────────┐   ┌──────────────────────┐
 │ TransactionLoader│   │    ReportFactory     │   report_factory.py
 │      «ABC»       │   │  name → class registry│
 └────────┬─────────┘   └──────────┬───────────┘
          │ implements             │ creates
          ▼                        ▼
 ┌──────────────────┐   ┌──────────────────────┐
 │CSVTransactionLoad│   │      ReportMode      │   report_mode.py
 │       er         │   │        «ABC»         │
 │ · csv.DictReader │   └──────────┬───────────┘
 │ · validate rows  │              │ implements
 │ · build objects  │    ┌─────────┼──────────┐
 └────────┬─────────┘    ▼         ▼          ▼
          │        ┌──────────┐┌────────┐┌──────────┐
          │        │ Category ││Monthly ││   Top    │
          │        │ Summary  ││ Totals ││ Expenses │
          │        │  Report  ││ Report ││  Report  │
          │        └─────┬────┘└───┬────┘└────┬─────┘
          │              └─────────┼──────────┘
          │ produces                         │ consumes
          ▼                                  ▼
      ┌──────────────────────────────────────────────┐
      │        Transaction  (frozen dataclass)       │   models.py
      │        ValidationResult                      │
      │        ExpenseTrackerError hierarchy         │   exceptions.py
      └──────────────────────────────────────────────┘
                       domain — depends on nothing

      ┌──────────────────────────────────────────────┐
      │   formatters.py  ·  NOT WIRED IN  ·          │   presentation/
      │   six helpers, zero callers — see below      │
      └──────────────────────────────────────────────┘
```

Every arrow points downward or inward. Nothing in `domain/` imports from `data/`, `reports/`, `presentation/`, or `cli.py`.

---

## Data flow

A successful `python3 main.py expenses.csv --report monthly`:

```
 1. main.py                       calls cli.main()
 2. main()                        constructs ExpenseTrackerCLI, calls run()
 3. run()                         parser.parse_args() → Namespace(file=…, report='monthly', top_n=10)
 4. run()                         Path(file).exists()?  no → raise DataLoadError
 5. run()                         loader = CSVTransactionLoader()
 6. loader.load(path)             open file, csv.DictReader
 7.   ↳ check header              REQUIRED_COLUMNS ⊆ fieldnames?  no → ValidationError
 8.   ↳ per row (from row 2)      _validate_and_create_transaction(row, n)
 9.       ↳ strip fields          empty? → ValidationError(row_number=n)
10.       ↳ date.fromisoformat    bad? → ValidationError(row_number=n)
11.       ↳ Decimal(amount)       bad or ≤ 0? → ValidationError(row_number=n)
12.       ↳ Transaction(...)      __post_init__ revalidates → ValidationError
13.   ↳ return                    List[Transaction], source order preserved
14. run()                         empty list? → raise EmptyDatasetError
15. run()                         build kwargs: top_n only when report == 'top'
16. ReportFactory.create_report   registry lookup → MonthlyTotalsReport()
17. report.process_transactions   group by '%Y-%m' → sum/count/mean → sort → format
18. run()                         print(output) to stdout
19. run()                         return 0
20. main()                        sys.exit(0)
```

Steps 6–13 are the only file I/O. Steps 16–17 are pure computation over in-memory objects — which is exactly why the report classes are trivial to unit test.

On failure, control jumps to the matching `except` block in `run()` (`cli.py:169-197`), which prints to stderr and returns a code. Nothing else in the system prints or exits.

---

## Layers and dependency rules

| Layer | Package | May import from | Knows about |
|---|---|---|---|
| Entry | `main.py` | `cli` | Nothing but the entry function |
| Interface | `cli.py` | `data`, `reports`, `domain` | `argparse`, `sys`, stdout/stderr, exit codes |
| Reports | `reports/` | `domain` | Aggregation and text layout |
| Data | `data/` | `domain` | `csv`, the filesystem, validation rules |
| Domain | `domain/` | *(nothing in-project)* | Business rules only |
| Presentation | `presentation/` | *(nothing in-project)* | Generic formatting — **currently unused** |

The rule to preserve when changing things: **`domain/` imports nothing from the project.** It is the stable centre. Everything else may depend on it; it depends on no one. If you find yourself wanting `domain/models.py` to import from `data/`, the logic belongs elsewhere.

The second rule: **only `cli.py` talks to the outside world.** No `print()`, no `input()`, no `sys.exit()` anywhere else. This is what lets every other module be tested by calling a function and inspecting a return value.

---

## Design patterns

### Strategy — report types

`ReportMode` is an abstract base class with one meaningful operation, `process_transactions(transactions) -> str`. `CategorySummaryReport`, `MonthlyTotalsReport`, and `TopExpensesReport` are interchangeable implementations.

**Why here:** the three reports share an input type and an output type but nothing else — one groups by a string field, one by a date component, one doesn't group at all. Expressing that as conditional branches inside a single function would mean a growing `if report_type == ...` chain touched by every new report, with all three algorithms' locals in one scope. As separate classes, each algorithm is isolated, independently testable, and addable without editing the others.

**What it buys:** `cli.py` holds no report logic whatsoever. It obtains *a* `ReportMode` and calls one method. The CLI has never needed changing to accommodate a report's internals.

**The cost:** three classes and an ABC where a small program could have had three functions. Justified by the extension story, which is the point of the exercise this code comes from; for three permanently-fixed reports, plain functions in a dict would do the same work.

### Factory — report construction

`ReportFactory` maps a string name to a strategy class via a class-level `_registry` dict, and `create_report(name, **kwargs)` instantiates from it.

**Why here:** the CLI receives a *string* from the user and needs an *object*. Somebody has to own that translation. Putting it in the factory keeps the concrete report class names out of `cli.py` entirely and gives one place to ask "what reports exist?" — `get_available_types()`.

**What it buys:** `register_report()` becomes a genuine runtime extension point; a plugin or a test can add a report type without editing the shipped source.

**The cost:** the registry is class-level mutable shared state. A `register_report()` call in one test is visible to every later test in the same process. Register inside a fixture with teardown, or use unique names.

### Abstract base classes — contracts

Both `TransactionLoader` and `ReportMode` use `abc.ABC` with `@abstractmethod`.

**Why not duck typing:** the ABCs make instantiating an incomplete implementation a `TypeError` at construction rather than an `AttributeError` at some later call site. For a plugin boundary, where the implementer is not the person who wrote the caller, an error at the moment of the mistake is worth the ceremony. The abstract methods also carry the contract's documentation — including which exceptions an implementation is expected to raise.

### Dependency injection — in the loose sense

`ExpenseTrackerCLI.run()` constructs its own `CSVTransactionLoader` and asks `ReportFactory` for its report. Dependencies are not passed into the constructor.

**Be precise about this:** the class docstring claims "dependencies passed to methods", and that overstates what the code does. The dependency *direction* is inverted — `run()` only calls abstract methods — but the *wiring* is hardcoded inside `run()`. To substitute a fake loader in a test you must patch `expense_tracker.cli.CSVTransactionLoader`, not pass an argument. Constructor injection would be a genuine improvement and a small change; see [Known structural issues](#known-structural-issues).

### Immutable value objects

`Transaction` and `ValidationResult` are `@dataclass(frozen=True)` with validation in `__post_init__`.

**Why:** a `Transaction` cannot exist in an invalid state, and cannot be mutated into one after the fact. Aggregation code can therefore read `t.amount` without checking anything. Frozen dataclasses are also hashable, so transactions work as dict keys and set members for free.

---

## Module reference

### `main.py`

Fourteen lines. Imports `main` from `expense_tracker.cli` and calls it under `if __name__ == '__main__'`. Deliberately trivial: it exists so the project can be run as a script, and so the real entry point stays importable and testable.

**Extension point:** none. Don't add logic here.

### `expense_tracker/cli.py`

`ExpenseTrackerCLI` — argument parsing, orchestration, error handling.

- `_create_argument_parser()` builds the `argparse` parser, including the `choices` list for `--report` and the help epilogue.
- `run(args=None) -> int` does the work and returns an exit code. It does not call `sys.exit()`, which is what makes it testable.
- `main()` wraps `run()` in `sys.exit()` for the console entry point.

**Dependencies:** `CSVTransactionLoader` (concrete, hardcoded), `ReportFactory`, the exception hierarchy.

**Extension points:** add a flag in `_create_argument_parser()` and consume it in `run()`. Note the `--report` `choices` list duplicates the factory registry — see below.

### `expense_tracker/domain/models.py`

`Transaction` (frozen, validating) and `ValidationResult` (frozen, with `success()` / `failure()` constructors). Imports only from the standard library.

`ValidationResult` is currently unused — the loader raises instead of returning results. It is the scaffolding for a future accumulate-all-errors mode.

**Extension points:** adding a field to `Transaction` is a breaking change for every loader and report. Consider a separate type or an optional field with a default.

### `expense_tracker/domain/exceptions.py`

`ExpenseTrackerError` and its four subclasses. `ValidationError` carries `row_number` and prefixes its message with `Row {n}: `. `InvalidReportTypeError` takes `(report_type, available_types)` and assembles its own message.

**Extension points:** new failure categories subclass `ExpenseTrackerError`, then get a handler in `run()`. Without the handler they fall to the generic `except ExpenseTrackerError` and report exit code 3.

### `expense_tracker/data/transaction_loader.py`

`TransactionLoader` (ABC: `load`, `validate_source`) and `CSVTransactionLoader`.

The CSV implementation uses `csv.DictReader`, so `REQUIRED_COLUMNS` is a **set** membership check: column order in the file is irrelevant and extra columns are ignored. Validation lives in `_validate_and_create_transaction()`, which strips whitespace, rejects empty fields, parses the date with `date.fromisoformat()`, parses the amount with `Decimal()`, rejects non-positive amounts, and translates any `ValueError` from `Transaction.__post_init__` into a `ValidationError` with the row number attached.

**Extension points:** subclass `TransactionLoader` for a new source. Subclass `CSVTransactionLoader` and override `_validate_and_create_transaction()` to change validation while keeping the file handling.

### `expense_tracker/reports/report_mode.py`

The `ReportMode` ABC and all three reports. Each `process_transactions()` follows the same four steps: guard against an empty list, group into a `defaultdict`, compute total/count/mean per group, then build a list of lines and `'\n'.join()` it.

Column widths and separator lengths are inline f-string format specs. The two summary reports are 50 characters wide; `TopExpensesReport` is 80.

**Extension points:** a new report subclasses `ReportMode` and implements two methods.

### `expense_tracker/reports/report_factory.py`

`ReportFactory` with `_registry`, `create_report()`, `get_available_types()`, and `register_report()`. All class methods; the class is never usefully instantiated.

`register_report()` refuses to overwrite an existing name (`ValueError`) and type-checks against `ReportMode` (`TypeError`).

**Extension points:** this module *is* the extension point.

### `expense_tracker/presentation/formatters.py`

Six helpers: `format_currency`, `format_table`, `format_separator`, `format_header`, `format_summary_line`, `truncate_text`.

See [The unused presentation layer](#the-unused-presentation-layer) — this module has no callers.

---

## Extension points

### Adding a report type

Four steps. The first is the only one the Strategy pattern promised; the rest are the wiring reality.

**1. Write the strategy** in `expense_tracker/reports/report_mode.py`, or in your own module:

```python
from collections import defaultdict
from typing import List

from expense_tracker.domain.models import Transaction
from expense_tracker.domain.exceptions import EmptyDatasetError
from expense_tracker.reports.report_mode import ReportMode


class WeekdayReport(ReportMode):
    """Spending grouped by day of the week."""

    def process_transactions(self, transactions: List[Transaction]) -> str:
        if not transactions:
            raise EmptyDatasetError("Cannot generate report from empty transaction list")

        by_day = defaultdict(list)
        for t in transactions:
            by_day[t.date.strftime('%A')].append(t.amount)

        order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                 'Friday', 'Saturday', 'Sunday']

        lines = ["Weekday Report", "=" * 50]
        lines.append(f"{'Day':<15} {'Total':>12} {'Count':>8} {'Avg':>10}")
        lines.append("-" * 50)
        for day in order:
            if day not in by_day:
                continue
            amounts = by_day[day]
            total = sum(amounts)
            lines.append(
                f"{day:<15} ${total:>11,.2f} {len(amounts):>8} "
                f"${total / len(amounts):>9,.2f}"
            )
        return '\n'.join(lines)

    def get_report_name(self) -> str:
        return "Weekday"
```

Follow the existing conventions: guard the empty list first, use `Decimal` arithmetic throughout (`sum()` of `Decimal` stays `Decimal`), and match the 50-character layout so reports look like siblings.

**2. Register it** in `report_factory.py`'s `_registry`:

```python
_registry: Dict[str, Type[ReportMode]] = {
    'category': CategorySummaryReport,
    'monthly':  MonthlyTotalsReport,
    'top':      TopExpensesReport,
    'weekday':  WeekdayReport,     # ← added
}
```

Or, from outside the source tree, at runtime:

```python
ReportFactory.register_report('weekday', WeekdayReport)
```

**3. Add it to the CLI's `choices` list** in `cli.py`, in `_create_argument_parser()`:

```python
parser.add_argument(
    '--report',
    choices=['category', 'monthly', 'top', 'weekday'],   # ← added
    ...
)
```

**This step is the leak in the design.** `argparse` validates `--report` against a hardcoded list that duplicates the factory registry. Registering a report without editing this list leaves it reachable from the library but rejected by the CLI with `invalid choice`. It is also why `InvalidReportTypeError` can never fire through the CLI — `argparse` rejects unknown names first.

The fix, if you are touching this area anyway:

```python
parser.add_argument(
    '--report',
    choices=ReportFactory.get_available_types(),
    default='category',
    ...
)
```

That makes the registry the single source of truth. It does mean `--help` reflects whatever was registered at parser-construction time, which is the correct behaviour but worth knowing.

**4. Update the epilogue** in the same method so `--help` describes the new report, and add a row to the tables in [`README.md`](../README.md) and the [User Guide](user_guide.md#the-three-reports).

**5. Test it** — add a class to `tests/test_report_modes.py` following the existing pattern, and a registry assertion in `tests/test_report_factory.py`.

If your report needs constructor options like `TopExpensesReport`'s `top_n`, add the flag in `_create_argument_parser()` and extend the `report_kwargs` block in `run()`:

```python
report_kwargs = {}
if parsed_args.report == 'top':
    report_kwargs['top_n'] = parsed_args.top_n
```

This per-report conditional is the other small wart — it grows by one branch per parameterised report.

### Adding a data source

Cleaner than adding a report, because no `argparse` `choices` list stands in the way.

**1. Implement the interface:**

```python
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import List

from expense_tracker.data.transaction_loader import TransactionLoader
from expense_tracker.domain.models import Transaction
from expense_tracker.domain.exceptions import DataLoadError, ValidationError


class JSONTransactionLoader(TransactionLoader):
    """Loads transactions from a JSON array of objects."""

    def load(self, source: str) -> List[Transaction]:
        path = Path(source)
        if not path.exists():
            raise DataLoadError(f"File not found: {source}")

        try:
            records = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            raise DataLoadError(f"Invalid JSON in {source}: {e}") from e

        if not isinstance(records, list):
            raise ValidationError("Top-level JSON value must be an array")

        transactions = []
        for i, record in enumerate(records, start=1):
            try:
                transactions.append(Transaction(
                    date=date.fromisoformat(record['date']),
                    amount=Decimal(str(record['amount'])),
                    category=record['category'],
                    description=record['description'],
                ))
            except KeyError as e:
                raise ValidationError(f"Missing field {e}", row_number=i) from e
            except (ValueError, ArithmeticError) as e:
                raise ValidationError(str(e), row_number=i) from e

        return transactions

    def validate_source(self, source: str) -> bool:
        try:
            p = Path(source)
            return p.exists() and p.is_file()
        except Exception:
            return False
```

Honour the contract: raise `DataLoadError` for access problems, `ValidationError` with a `row_number` for data problems, return `[]` rather than raising for an empty-but-valid source, preserve source order, and never let `validate_source()` raise.

One subtlety specific to JSON, and a good illustration of the `Decimal` rule from
[Design decisions](#decimal-rather-than-float): `json.loads()` parses `52.30` into a
**float** before your code sees it, so `Decimal(str(record['amount']))` above launders the
amount through binary floating point and yields `Decimal('52.3')`. Harmless here, but
`0.1` becomes `Decimal('0.1')` only by luck of `repr()` rounding. Parse the number as a
decimal from the start instead:

```python
records = json.loads(path.read_text(encoding='utf-8'), parse_float=Decimal)
...
amount=record['amount'] if isinstance(record['amount'], Decimal) else Decimal(str(record['amount'])),
```

`CSVTransactionLoader` avoids the problem for free, because CSV fields arrive as strings
and go straight into `Decimal()`.

**2. Wire it up.** Because `run()` hardcodes `CSVTransactionLoader()`, selecting a loader means either a format flag:

```python
LOADERS = {'csv': CSVTransactionLoader, 'json': JSONTransactionLoader}
loader = LOADERS[parsed_args.format]()
```

or inference from the file extension, or — better — [constructor injection](#known-structural-issues) so the choice moves out of `run()` altogether.

**3. Test it** against the same behaviours `tests/test_csv_loader.py` covers: happy path, missing file, empty file, malformed record, and the row number in the error.

---

## Design decisions

### CSV rather than a database

**Chosen because** the input is a file the user already has or can produce from any bank export or spreadsheet, and it stays readable and diffable without the tool. There is no schema migration story, no connection handling, no daemon.

**Given up:** queries, indexes, concurrent access, and anything larger than memory. There is also no way to update a single record — you edit the file.

**Revisit when** the tool needs to filter by date or category at load time, or datasets outgrow memory. The `TransactionLoader` ABC exists precisely so a `SQLiteTransactionLoader` can be added without disturbing the reports.

### `Decimal` rather than `float`

**Chosen because** `0.1 + 0.2 != 0.3` in binary floating point, and a personal-finance tool whose totals are off by fractions of a cent is broken in the way most likely to be noticed and least likely to be forgiven. `Decimal` is exact for the base-10 quantities money is denominated in.

**Given up:** speed (irrelevant at this scale) and a small amount of ergonomics — `Decimal` must be constructed from strings, never floats, or the error it prevents is reintroduced at the boundary. The loader does this correctly by passing the raw CSV text to `Decimal()`.

### Fail-fast validation rather than skip-and-warn

**Chosen because** a skipped row produces a report that looks complete and is wrong. An aborted load produces an error message naming the row. The first failure mode is silent and the second is loud, and for a tool whose entire output is sums, loud is correct.

**Given up:** usability on messy real-world exports, where you fix one row, rerun, and hit the next. `ValidationResult` exists in `models.py` as the scaffolding for an opt-in accumulate-all-errors mode; nothing uses it yet.

### ABCs rather than duck typing or `Protocol`

**Chosen because** `abc.ABC` fails at instantiation when a method is missing, which for a plugin boundary is the earliest useful moment. The abstract method bodies also hold the contract documentation, including expected exceptions.

**Given up:** `Protocol` would give structural typing with no inheritance requirement, letting unrelated classes satisfy the interface. For this codebase's explicit-subclass extension model, nominal typing is the better fit.

### Reports return strings rather than printing

**Chosen because** a function returning a string is testable with `assertIn`; a function that prints needs stdout capture. It also keeps every report reusable behind a web or file output layer without modification.

**Given up:** streaming. The full report is built in memory before a single character is written. Irrelevant for hundreds of lines.

### Three reports, three classes

**Chosen because** the extension story is the point: each report is independently testable and addable. See the [Strategy](#strategy--report-types) discussion for the honest cost accounting — at three fixed reports this is more structure than the problem strictly demands, and the justification is the fourth report, not the first three.

---

## Known structural issues

Real inconsistencies in the current code, recorded so you neither trip over them nor mistake them for intentional design. None affects correctness of the reports.

### The unused presentation layer

`expense_tracker/presentation/formatters.py` provides six formatting helpers. **Nothing calls any of them.** A search for every function name across the project finds hits only inside that file; the report classes build their output with inline f-strings.

Consequences:

- **`format_table()` raises `NotImplementedError`** on every call, yet carries a docstring with a worked example and plausible output. That output has never been produced by running code. The function has never been called by anything, so the placeholder was never noticed.
- **`format_header()` ignores its `width` parameter.** It underlines with `underline_char * len(title)`, so `format_header('Short')` and `format_header('Short', width=10)` return identical strings.
- **`format_summary_line()` underruns silently.** When `len(label) + len(value) > width`, the padding count goes negative, `' ' * negative` yields `''`, and the strings are concatenated with no separator and no error.
- None of it is covered by tests, because none of it runs.

Two coherent ways forward. Either **adopt it** — implement `format_table()`, fix `format_header()`, and refactor the three reports to build their tables through these helpers, which would remove the duplicated column-width logic currently copy-pasted across `report_mode.py` — or **delete it**, and let the reports keep owning their own layout. Leaving it as-is is the only bad option, because the docstrings describe a formatting layer that does not exist.

If you adopt it, note the reports disagree on width (50 for the two summaries, 80 for top expenses); unifying that is part of the job.

### `--report` choices duplicate the factory registry

`cli.py` hardcodes `choices=['category', 'monthly', 'top']` while `ReportFactory._registry` holds the same three names. Two sources of truth for one fact. This makes `register_report()` half-useful — the new type works from the library but is rejected by the CLI — and makes `InvalidReportTypeError` unreachable through the CLI, since `argparse` rejects unknown values first with exit code 2.

Fix: `choices=ReportFactory.get_available_types()`. See [Adding a report type](#adding-a-report-type) step 3.

### Duplicate file-existence check

`run()` checks `Path(parsed_args.file).exists()` and raises `DataLoadError` before constructing the loader. `CSVTransactionLoader.load()` then performs the identical check. The loader's is dead code on the CLI path, though it correctly protects direct library callers. Harmless duplication; the CLI-side check could go, leaving validation to the layer that owns it.

### `run()` hardcodes its dependencies

The class docstring says dependencies are "passed to methods". They are not — `run()` constructs `CSVTransactionLoader()` itself. Testing with a fake loader requires `unittest.mock.patch` on the module attribute rather than passing an argument.

A small, contained improvement:

```python
class ExpenseTrackerCLI:
    def __init__(self, loader: TransactionLoader | None = None):
        self.parser = self._create_argument_parser()
        self.loader = loader or CSVTransactionLoader()
```

That makes the injection real, matches the docstring, removes the need to patch in tests, and solves loader selection for [Adding a data source](#adding-a-data-source) at the same time.

### `ValueError` escapes the error hierarchy

`TopExpensesReport.__init__` raises a plain `ValueError` for `top_n < 1`, and `Transaction.__post_init__` raises `ValueError` for invalid fields. Neither is an `ExpenseTrackerError`, so both fall through `run()`'s specific handlers into the generic `except Exception`, surfacing as `Unexpected error: top_n must be positive, got 0` with exit code 1. The message is accurate but the "Unexpected" framing is wrong — this is a perfectly expected bad-input case that should read as a validation error with exit code 2.

Fix: raise `ValidationError` from `TopExpensesReport.__init__`, or validate `--top-n` in `_create_argument_parser()` with a `type=` callable so `argparse` reports it.

### `TopExpensesReport` heading can contradict its total

Requesting more transactions than exist prints `Top 100 Expenses Report` above `TOTAL (top 20)`. The heading uses `self.top_n`; the total uses the actual count. Cosmetic, and the trailing `Note: Only 20 transaction(s) available` mitigates it, but the heading should use the real count.

### `ValidationResult` is unused

Defined, tested in `tests/test_models.py`, and never produced by any code path. It is scaffolding for accumulate-all-errors validation. Either build that mode or drop the class.

---

## Testing strategy

Sixty-one tests in `tests/`, using `unittest.TestCase` classes run under `pytest`:

```bash
python3 -m pytest tests/ -q
# 55 passed, 6 skipped
```

| File | Covers |
|---|---|
| `test_models.py` | `Transaction` validation and immutability, `ValidationResult` constructors |
| `test_csv_loader.py` | Happy path, missing file, empty file, missing columns, bad rows, row numbers |
| `test_report_modes.py` | All three reports: aggregation, sorting, totals, empty-dataset guard |
| `test_report_factory.py` | Registry lookup, unknown type, `register_report()` validation |
| `test_cli.py` | Exit codes end to end, error messages on stderr |
| `test_documentation_quality.py` | Presence and content of docs — **6 skipped, see below** |
| `fixtures/valid_expenses.csv` | Six-row known-good input |

**How the layers are tested.** The domain and report layers need no mocking at all: construct `Transaction` objects in the test, call `process_transactions()`, assert on the returned string. This is the direct payoff of reports returning strings instead of printing.

The loader is tested against real temporary files rather than a mocked filesystem — `csv` module behaviour, encoding, and `Path` semantics are the things most likely to break, and mocking them would test the mock.

`test_cli.py` exercises `run()` and asserts on its return code. Remember that `argparse` failures raise `SystemExit`, a `BaseException`, so tests for bad arguments need `pytest.raises(SystemExit)` rather than an equality assertion on the return value.

**What is not covered:** `presentation/formatters.py`, entirely, because nothing calls it.

**The skipped documentation tests.** `test_documentation_quality.py` checks paths like `../solution/README.md` and `../solution/transaction_loader.py` — a flat module layout in a sibling directory that does not match this package structure. Its `skipif` guards and `if not path.exists(): continue` blocks therefore skip rather than fail. The checks themselves are reasonable; the paths are stale. See [Contributing](contributing.md#known-issue-documentation-quality-tests).

**Adding tests.** Put them in the file matching the module under test, follow the `unittest.TestCase` convention already there, and use `tests/fixtures/` for input files rather than generating CSV inline where a fixture will do.

---

## Performance characteristics

Everything is O(n) or O(n log n) in the number of transactions, with the whole dataset in memory.

| Stage | Cost |
|---|---|
| CSV read and validate | O(n) time, one `Transaction` per row retained |
| Category / monthly grouping | O(n) time, O(k) extra space for k groups |
| Sorting groups | O(k log k), k = distinct categories or months |
| Top-N sort | O(n log n) — sorts everything, then slices |
| Formatting | O(rows in output) |

Memory is roughly a few hundred bytes per transaction (a frozen dataclass holding a `date`, a `Decimal`, and two `str`). Tens of thousands of transactions are comfortable; a year of personal expenses is a few hundred rows and runs instantly.

Nothing here needs optimising at the intended scale, and the obvious micro-optimisations would cost clarity. If datasets ever grow past memory, the fix is architectural, not incremental: a streaming loader yielding transactions lazily plus reports that consume an iterator and accumulate rather than retain. `TopExpensesReport` would need `heapq.nlargest()` instead of a full sort. The `TransactionLoader` ABC is the seam where that work would start.

---

## Security considerations

The threat surface is small: a local, read-only, single-user CLI with no network access, no subprocess execution, no deserialisation of code, and no credentials.

**What is handled:**

- **No `eval`, `exec`, or `pickle`.** Input is parsed with `csv`, `date.fromisoformat()`, and `Decimal()` — none of which execute input.
- **Read-only.** Every file is opened `'r'`. The tool never writes to the user's data.
- **No shell.** No `subprocess`, no `os.system`, so file paths cannot be injected into a command line.
- **Strict typing at the boundary.** Dates and amounts must parse into real `date` and `Decimal` values; malformed input becomes a `ValidationError`, not a surprising object downstream.
- **No formula execution.** A CSV cell containing `=cmd|'/c calc'!A1` is treated as ordinary text, never evaluated. This tool is not a spreadsheet.
- **Errors to stderr, reports to stdout,** so redirecting output cannot mix diagnostics into captured data.

**What to keep in mind:**

- **Path handling is unrestricted by design.** Any path the invoking user can read, the tool will read. That is correct for a CLI the user runs on their own files. It becomes a directory-traversal issue the moment this code is placed behind a service where the path comes from an untrusted caller — in that setting, validate and confine the path before calling `load()`.
- **Error messages include the full path.** `File not found: /home/alice/private/expenses.csv` is helpful locally and an information leak in a server log. Sanitise before surfacing these messages to a remote caller.
- **Unbounded input.** A very large CSV is read entirely into memory, so an attacker-supplied file is a memory-exhaustion vector in any multi-tenant context. Bound the size before loading.
- **Expense data is sensitive.** The tool does not encrypt anything and does not need to — but reports redirected to a file inherit the directory's permissions, and CSVs of personal spending in a shared or cloud-synced folder are readable by whoever can read that folder.
- **CSV injection on export.** Reports are plain text and the tool never writes CSV, so it does not create this risk. If you add CSV or spreadsheet export, escape leading `=`, `+`, `-`, and `@` in text fields.
