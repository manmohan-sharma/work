# Expense Tracker CLI

A command-line tool that turns a CSV of your expenses into readable spending reports. Point it at a file, pick a report, read the answer — no spreadsheet formulas, no account linking, no programming knowledge required.

```bash
python3 main.py examples/sample_expenses.csv
```

## What it does

Expense Tracker reads expense records from a CSV file and prints one of three formatted reports to your terminal:

- **Category summary** — how much went to Food, Transportation, Utilities, and so on, with totals, counts, and averages per category
- **Monthly totals** — spending grouped by month, so you can see trends over time
- **Top expenses** — your largest individual purchases, ranked

It is built for personal budgeting and expense review. Your data stays in your own CSV file on your own machine; nothing is uploaded anywhere.

## Requirements

- **Python 3.10 or newer.** Check with `python3 --version`.
- **No third-party packages.** The tool uses only the Python standard library.

> **Note on the Python version:** the source uses PEP 604 union syntax in evaluated
> annotations (for example `list[str] | None` in `expense_tracker/cli.py`), so 3.10 is a
> hard floor. On Python 3.9 or earlier the program fails at import with a `TypeError`.

## Installation

```bash
git clone <repository-url>
cd expense-tracker
python3 main.py examples/sample_expenses.csv
```

If that last command prints a category summary table, you are ready to go. There is no build step and nothing to install.

For virtual environment setup and platform-specific instructions (Windows, macOS, Linux), see the [User Guide](docs/user_guide.md#installation).

## Quick start

Run the bundled sample data:

```bash
python3 main.py examples/sample_expenses.csv
```

```
Category Summary Report
==================================================
Category                    Total    Count        Avg
--------------------------------------------------
Shopping             $     575.00        2 $   287.50
Healthcare           $     500.00        2 $   250.00
Utilities            $     461.00        3 $   153.67
Food                 $     277.54        8 $    34.69
Transportation       $     265.00        3 $    88.33
Entertainment        $     164.99        2 $    82.50
--------------------------------------------------
TOTAL                $   2,243.53       20 $   112.18
```

Then try the other two reports:

```bash
python3 main.py examples/sample_expenses.csv --report monthly
python3 main.py examples/sample_expenses.csv --report top --top-n 5
```

## Usage

```
python3 main.py <csv-file> [--report {category,monthly,top}] [--top-n N]
```

| Argument | Description | Default |
|---|---|---|
| `<csv-file>` | Path to your expense CSV file. Required. | — |
| `--report` | Report to generate: `category`, `monthly`, or `top`. | `category` |
| `--top-n N` | How many expenses the `top` report shows. Ignored by other reports. | `10` |
| `-h`, `--help` | Show usage and exit. | — |

Full option reference, every report with real output, and end-to-end workflows are in the [User Guide](docs/user_guide.md).

## CSV format

Your file needs a header row and these four columns:

```csv
date,amount,category,description
2025-01-05,52.30,Food,Weekly groceries
2025-01-10,85.00,Transportation,Gas
2025-01-12,150.00,Utilities,Internet bill
```

- `date` — ISO 8601, `YYYY-MM-DD`. `01/15/2025` is rejected.
- `amount` — a positive number, digits only. `$42.50` is rejected; write `42.50`.
- `category` — any non-empty text. Case-sensitive: `Food` and `food` count separately.
- `description` — any non-empty text. Quote it if it contains a comma.

Column *order* does not matter — the file is read by header name — but all four must be present and no field may be blank. The full specification, including how quoting and whitespace are handled, is in the [User Guide](docs/user_guide.md#csv-file-format).

## Documentation

| Document | Audience | Contents |
|---|---|---|
| [User Guide](docs/user_guide.md) | End users | Installation, every command and option, CSV spec, worked examples, workflows |
| [Troubleshooting](docs/troubleshooting.md) | End users | Every error message, its cause, its fix, and its exit code; FAQ |
| [API Reference](docs/api_reference.md) | Developers | Module, class, and method reference with parameters, returns, and exceptions |
| [Architecture](docs/architecture.md) | Maintainers | Component diagram, data flow, design patterns, extension points, rationale |
| [Contributing](docs/contributing.md) | Contributors | Dev setup, code style, testing, PR checklist |
| [Changelog](docs/CHANGELOG.md) | Everyone | Release history |

## Project layout

```
.
├── main.py                            # Entry point
├── expense_tracker/
│   ├── cli.py                         # Argument parsing and orchestration
│   ├── domain/
│   │   ├── models.py                  # Transaction, ValidationResult
│   │   └── exceptions.py              # Error hierarchy
│   ├── data/
│   │   └── transaction_loader.py      # TransactionLoader ABC, CSVTransactionLoader
│   ├── reports/
│   │   ├── report_mode.py             # ReportMode ABC and the three reports
│   │   └── report_factory.py          # Report type registry
│   └── presentation/
│       └── formatters.py              # Formatting helpers (see note below)
├── examples/sample_expenses.csv       # 20 sample transactions
├── tests/                             # Unit tests and fixtures
└── docs/                              # Documentation
```

## Running the tests

```bash
python3 -m pytest tests/ -q
```

55 tests pass. Six tests in `tests/test_documentation_quality.py` are skipped by design — see [Contributing](docs/contributing.md#known-issue-documentation-quality-tests).

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Data could not be loaded or validated |
| `2` | Bad command-line arguments |
| `3` | File parsed but contained no usable transactions |
| `130` | Cancelled with Ctrl+C |

## Getting help

```bash
python3 main.py --help
```

If something is not working, [Troubleshooting](docs/troubleshooting.md) lists every error the tool can print, what causes it, and how to fix it.
