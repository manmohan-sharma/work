# User Guide

Complete instructions for installing and using Expense Tracker CLI. If you just want to get running in one minute, the [README](../README.md) is shorter. This guide covers everything.

## Contents

- [Installation](#installation)
- [Your first report](#your-first-report)
- [Command reference](#command-reference)
- [CSV file format](#csv-file-format)
- [The three reports](#the-three-reports)
- [Worked examples](#worked-examples)
- [Workflows](#workflows)
- [Tips for good results](#tips-for-good-results)
- [Limitations](#limitations)

---

## Installation

### Prerequisites

You need **Python 3.10 or newer**. Nothing else — the tool uses only modules that ship with Python.

Check your version:

```bash
python3 --version
```

You should see `Python 3.10.x` or higher. If the version is 3.9 or lower, the program will fail at startup with a `TypeError` about unsupported operand types; the source uses PEP 604 union syntax (`list[str] | None`) in annotations that Python evaluates at import time, and that syntax did not exist before 3.10.

If `python3` is not found, try `python --version` instead. On Windows, `py --version` also works. Use whichever name works on your system in place of `python3` in the commands below.

### Getting the code

```bash
git clone <repository-url>
cd expense-tracker
```

Or download and unpack the archive, then `cd` into the resulting folder.

### Verifying it works

From the project directory:

```bash
python3 main.py examples/sample_expenses.csv
```

A table of spending by category should appear. That is the whole installation — there is no build step, no `pip install`, and no configuration file.

### Optional: using a virtual environment

The tool needs no dependencies, so a virtual environment is not required. Create one anyway if you prefer to keep an isolated Python for this project, or if you plan to run the test suite (which needs `pytest`).

**macOS and Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 main.py examples/sample_expenses.csv
```

**Windows (PowerShell):**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py main.py examples\sample_expenses.csv
```

**Windows (Command Prompt):**

```cmd
py -m venv .venv
.venv\Scripts\activate.bat
py main.py examples\sample_expenses.csv
```

Run `deactivate` to leave the environment.

### Platform notes

- **Path separators.** Windows accepts both `examples\sample_expenses.csv` and `examples/sample_expenses.csv`. The examples in this guide use forward slashes.
- **Paths with spaces.** Quote them: `python3 main.py "My Folder/expenses.csv"`.
- **File encoding.** Input files must be UTF-8. If you export from Excel, choose "CSV UTF-8" rather than plain "CSV"; otherwise accented characters may produce a `File encoding error`.

---

## Your first report

The project ships with `examples/sample_expenses.csv`, twenty transactions across January and February 2025. Use it to learn the tool before pointing it at your own data.

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

Reading this table: each row is one category. **Total** is everything spent in it, **Count** is how many transactions, **Avg** is Total ÷ Count. Rows are ordered by Total, largest first, so your biggest spending areas are always at the top. The `TOTAL` row sums every category.

Here that says: Shopping was the largest category at $575.00 across just two purchases, while Food was the most *frequent* at eight transactions but only $34.69 each on average.

---

## Command reference

### Syntax

```
python3 main.py <csv-file> [--report {category,monthly,top}] [--top-n N]
```

### Arguments

#### `<csv-file>` — required

Path to the CSV file holding your expenses. Relative to your current directory, or an absolute path. This is a positional argument, so it takes no flag name.

```bash
python3 main.py expenses.csv
python3 main.py ~/finances/2025/expenses.csv
python3 main.py "C:/Users/Me/My Documents/expenses.csv"
```

Omitting it is an error:

```
usage: main.py [-h] [--report {category,monthly,top}] [--top-n N] file
main.py: error: the following arguments are required: file
```

#### `--report {category,monthly,top}` — optional

Which report to generate. Defaults to `category`.

| Value | Report |
|---|---|
| `category` | Spending grouped by category |
| `monthly` | Spending grouped by calendar month |
| `top` | The largest individual transactions |

Any other value is rejected before your file is read:

```
main.py: error: argument --report: invalid choice: 'weekly' (choose from 'category', 'monthly', 'top')
```

#### `--top-n N` — optional

How many transactions the `top` report lists. Defaults to `10`.

Only the `top` report uses this. Passing it with `category` or `monthly` is harmless and silently ignored:

```bash
python3 main.py expenses.csv --report category --top-n 3   # --top-n has no effect
```

`N` must be 1 or greater. Zero and negative values produce an error:

```
Unexpected error: top_n must be positive, got 0
```

If `N` is larger than the number of transactions you have, every transaction is listed and a note says so. Be aware of one cosmetic quirk: the *heading* still echoes the number you asked for, while the total line reports the real count.

```bash
python3 main.py examples/sample_expenses.csv --report top --top-n 100
```

```
Top 100 Expenses Report
...
TOTAL (top 20)  $   2,243.53

Note: Only 20 transaction(s) available
```

#### `-h`, `--help`

Prints usage, the options, and examples, then exits.

```bash
python3 main.py --help
```

```
usage: main.py [-h] [--report {category,monthly,top}] [--top-n N] file

Generate expense reports from CSV transaction data

positional arguments:
  file                  Path to CSV file containing expense data

options:
  -h, --help            show this help message and exit
  --report {category,monthly,top}
                        Type of report to generate (default: category)
  --top-n N             Number of top expenses to show (for "top" report,
                        default: 10)

Examples:
  main.py expenses.csv
  main.py expenses.csv --report monthly
  main.py expenses.csv --report top --top-n 20

Available report types:
  category - Summary by expense category
  monthly  - Totals by month
  top      - Largest individual expenses
```

### Exit codes

Useful when calling the tool from a script.

| Code | Meaning | Example cause |
|---|---|---|
| `0` | Success | Report printed |
| `1` | Load or validation failure | File missing, empty, bad date, negative amount |
| `2` | Bad arguments | No file given, unknown `--report` value |
| `3` | No usable data | File had a header but no transaction rows |
| `130` | Cancelled | You pressed Ctrl+C |

---

## CSV file format

### Required structure

A header row, then one row per expense:

```csv
date,amount,category,description
2025-01-05,52.30,Food,Weekly groceries
2025-01-08,12.50,Food,Coffee shop
2025-01-10,85.00,Transportation,Gas
```

All four columns — `date`, `amount`, `category`, `description` — must be present. **Column order does not matter**, because columns are matched by header name, so this works equally well:

```csv
description,category,date,amount
Weekly groceries,Food,2025-01-05,52.30
```

Extra columns beyond the four are ignored, so you can keep your own notes columns in the same file.

### Column rules

| Column | Format | Valid | Invalid |
|---|---|---|---|
| `date` | ISO 8601 `YYYY-MM-DD` | `2025-01-05` | `01/05/2025`, `5-Jan-2025`, `2025/01/05` |
| `amount` | Positive number, no symbols | `52.30`, `85`, `1200.00` | `$52.30`, `52.30 USD`, `-52.30`, `0`, `1,200.00` |
| `category` | Any non-empty text | `Food`, `Home Office` | *(blank)* |
| `description` | Any non-empty text | `Weekly groceries` | *(blank)* |

Details that matter in practice:

- **Every field is required on every row.** A blank in any of the four columns stops the run and names the row.
- **Amounts must be positive.** This tool tracks expenses, not income, so `0` and negative numbers are rejected. There is no way to record a refund or credit.
- **No thousands separators.** Write `1200.00`, not `1,200.00` — the comma would split the field.
- **Surrounding whitespace is trimmed** from all four fields, so ` Food ` is read as `Food`.
- **More than two decimal places are accepted** and kept internally, but reports display two.
- **Categories are case-sensitive.** `Food` and `food` appear as two separate rows in the category report.
- **Loading stops at the first bad row.** Nothing is reported until the whole file validates, so you fix errors one at a time. The error message always includes the row number, counting the header as row 1.

### Descriptions containing commas

Wrap the field in double quotes:

```csv
date,amount,category,description
2025-01-08,12.50,Food,"Coffee, pastry, and juice"
```

Without the quotes the extra commas create extra fields, and the description is silently truncated at the first comma rather than raising an error — an easy mistake to miss. Quote any description with a comma in it.

### A complete minimal file

Copy this into `my_expenses.csv` to get started:

```csv
date,amount,category,description
2025-03-01,45.00,Food,Grocery store
2025-03-02,120.00,Transportation,Monthly subway pass
2025-03-05,15.50,Food,Coffee and pastry
2025-03-08,85.00,Utilities,Electric bill
2025-03-10,200.00,Healthcare,Doctor visit
```

---

## The three reports

### Category summary — `--report category`

**Question it answers:** where does my money go?

Groups every transaction by its `category` field and reports total, count, and average for each. Sorted by total, largest first.

```bash
python3 main.py examples/sample_expenses.csv --report category
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

This is the default, so `--report category` and no flag at all do the same thing.

Use it for budget allocation — the top rows are where cutting has the most effect. The Count column separates two different problems: a high total from few large purchases (Shopping, here) needs different attention than a high total from many small ones (Food).

### Monthly totals — `--report monthly`

**Question it answers:** is my spending going up or down?

Groups transactions by calendar month, labelled `YYYY-MM`. Sorted chronologically, oldest first, so the column reads as a timeline.

```bash
python3 main.py examples/sample_expenses.csv --report monthly
```

```
Monthly Totals Report
==================================================
Month                  Total    Count        Avg
--------------------------------------------------
2025-01         $     816.79       10 $    81.68
2025-02         $   1,426.74       10 $   142.67
--------------------------------------------------
TOTAL           $   2,243.53       20 $   112.18
```

February totalled $1,426.74 against January's $816.79 — a 75% increase on the same transaction count of ten, meaning the rise came from larger purchases rather than more of them.

Months with no transactions are simply absent; the report does not print empty rows for gaps.

### Top expenses — `--report top`

**Question it answers:** what were my biggest single purchases?

Lists individual transactions sorted by amount, largest first, with full date, category, and description. Shows ten by default; `--top-n` changes that.

```bash
python3 main.py examples/sample_expenses.csv --report top
```

```
Top 10 Expenses Report
================================================================================
Date               Amount Category             Description
--------------------------------------------------------------------------------
2025-02-18 $     450.00 Shopping             New laptop accessory
2025-02-03 $     320.00 Healthcare           Dentist appointment
2025-01-20 $     215.50 Utilities            Electric bill
2025-02-25 $     180.00 Healthcare           Prescription medications
2025-01-12 $     150.00 Utilities            Internet bill
2025-02-10 $     125.00 Shopping             New shoes
2025-01-16 $     120.00 Transportation       Monthly metro pass
2025-02-12 $      95.50 Utilities            Water bill
2025-02-01 $      89.99 Entertainment        Movie tickets
2025-01-10 $      85.00 Transportation       Gas
--------------------------------------------------------------------------------
TOTAL (top 10)  $   1,830.99
```

The `TOTAL` line sums only the rows shown, not your whole file. Comparing it against the grand total from the category report tells you how concentrated your spending is: $1,830.99 of $2,243.53 here, so ten transactions account for 82% of two months of spending.

Descriptions longer than 30 characters are truncated with an ellipsis. This report needs a terminal at least 80 characters wide; narrower windows will wrap the rows.

---

## Worked examples

### Using your own data

**Step 1.** Create `my_expenses.csv`:

```csv
date,amount,category,description
2025-03-01,45.00,Food,Grocery store
2025-03-02,120.00,Transportation,Monthly subway pass
2025-03-05,15.50,Food,Coffee and pastry
2025-03-08,85.00,Utilities,Electric bill
2025-03-10,200.00,Healthcare,Doctor visit
```

**Step 2.** Run the default report:

```bash
python3 main.py my_expenses.csv
```

```
Category Summary Report
==================================================
Category                    Total    Count        Avg
--------------------------------------------------
Healthcare           $     200.00        1 $   200.00
Transportation       $     120.00        1 $   120.00
Utilities            $      85.00        1 $    85.00
Food                 $      60.50        2 $    30.25
--------------------------------------------------
TOTAL                $     465.50        5 $    93.10
```

**Step 3.** Look at it the other two ways:

```bash
python3 main.py my_expenses.csv --report monthly
python3 main.py my_expenses.csv --report top --top-n 3
```

```
Monthly Totals Report
==================================================
Month                  Total    Count        Avg
--------------------------------------------------
2025-03         $     465.50        5 $    93.10
--------------------------------------------------
TOTAL           $     465.50        5 $    93.10
```

```
Top 3 Expenses Report
================================================================================
Date               Amount Category             Description
--------------------------------------------------------------------------------
2025-03-10 $     200.00 Healthcare           Doctor visit
2025-03-02 $     120.00 Transportation       Monthly subway pass
2025-03-08 $      85.00 Utilities            Electric bill
--------------------------------------------------------------------------------
TOTAL (top 3)  $     405.00
```

### Saving a report to a file

Redirect standard output:

```bash
python3 main.py examples/sample_expenses.csv > category_report.txt
python3 main.py examples/sample_expenses.csv --report monthly > monthly_report.txt
```

Error messages go to standard error, so they appear on screen rather than in the file. To capture them too:

```bash
python3 main.py expenses.csv > report.txt 2>&1
```

### Generating all three reports at once

**macOS and Linux:**

```bash
for r in category monthly top; do
  echo "=== $r ==="
  python3 main.py examples/sample_expenses.csv --report "$r"
done > all_reports.txt
```

**Windows (PowerShell):**

```powershell
foreach ($r in 'category','monthly','top') {
  "=== $r ==="
  py main.py examples\sample_expenses.csv --report $r
} | Out-File all_reports.txt
```

### Checking for problems in a script

The exit code tells you whether the run succeeded:

```bash
if python3 main.py expenses.csv > report.txt; then
  echo "Report written."
else
  echo "Failed with exit code $?." >&2
fi
```

---

## Workflows

### Monthly review

Keep one CSV per year and append to it as you spend. At the end of each month:

```bash
python3 main.py 2025_expenses.csv --report monthly   # Is the trend rising?
python3 main.py 2025_expenses.csv --report category  # Which categories drove it?
python3 main.py 2025_expenses.csv --report top       # Any one-off purchases to explain it?
```

Reading them in that order goes from symptom to cause: the monthly report tells you *whether* something changed, the category report tells you *where*, and the top report tells you *what*.

### Comparing two periods

The tool has no date filter, so split the periods into separate files:

```bash
head -1 2025_expenses.csv > q1.csv
grep -E '^2025-0[123]-' 2025_expenses.csv >> q1.csv

head -1 2025_expenses.csv > q2.csv
grep -E '^2025-0[456]-' 2025_expenses.csv >> q2.csv

python3 main.py q1.csv
python3 main.py q2.csv
```

The `head -1` copies the header, which each file needs. This assumes `date` is your first column; if you reordered columns, filter in a spreadsheet instead.

### Focusing on one category

Also not built in, so filter first:

```bash
head -1 expenses.csv > food_only.csv
grep ',Food,' expenses.csv >> food_only.csv
python3 main.py food_only.csv --report monthly
```

That shows how one category's spending moves month to month.

---

## Tips for good results

**Keep category names consistent.** The tool matches them literally, so `Food`, `food`, and `Groceries` become three separate rows and your totals fragment. Pick a short list — six to ten categories — and reuse exactly those spellings. Fix drift with a find-and-replace before running.

**Write descriptions you will recognise later.** They appear in the top-expenses report, where `Amazon` tells you nothing six months on but `Amazon - desk lamp` does. Keep them under 30 characters to avoid truncation.

**Log expenses regularly.** Weekly beats monthly; reconstructing from memory is where wrong data comes from.

**Keep the file under version control or backed up.** It is plain text, so `git` works well and gives you a history of edits.

**Split by year.** One file per year keeps the monthly report readable — twelve rows rather than sixty.

---

## Limitations

Worth knowing before you build a routine around the tool:

- **Expenses only.** Amounts must be positive; income, refunds, and credits cannot be recorded.
- **No date or category filtering.** Narrow the data by splitting the CSV, as shown in [Workflows](#workflows).
- **No currency handling.** Amounts are unitless numbers displayed with a `$`. Mixing currencies in one file produces a meaningless total.
- **No budget targets.** The tool reports what you spent, not how that compares to a plan.
- **No writing.** Reports print to the terminal; nothing is ever written back to your CSV. Your data file is only ever read.
- **Whole-file loading.** Every transaction is held in memory. Fine for years of personal expenses; not intended for millions of rows.
- **Strict validation.** One bad row stops the run. This is deliberate — a silently skipped row would make every total quietly wrong — but it means messy exports need cleaning before the first report appears.

---

## Where to go next

- Something broken or an error you do not recognise? [Troubleshooting](troubleshooting.md) covers every message the tool can print.
- Want to use the code as a library, or add a report type? [API Reference](api_reference.md) and [Architecture](architecture.md).
- Want to contribute? [Contributing](contributing.md).
