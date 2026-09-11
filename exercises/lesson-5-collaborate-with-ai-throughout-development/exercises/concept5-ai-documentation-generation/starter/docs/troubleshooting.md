# Troubleshooting

Every error Expense Tracker can print, what causes it, and how to fix it. All messages below were produced by running the tool, so you can match yours literally.

**Fastest route:** the tool's exit code tells you which kind of problem you have.

```bash
python3 main.py expenses.csv; echo "exit=$?"
```

| Exit code | Category | Jump to |
|---|---|---|
| `1` | The file could not be read, or its data broke a rule | [File errors](#file-errors) · [Data validation errors](#data-validation-errors) |
| `2` | Something is wrong with the command you typed | [Command-line errors](#command-line-errors) |
| `3` | The file was read fine but held no usable transactions | [No data errors](#no-data-errors) |
| `130` | You pressed Ctrl+C | Nothing is wrong |

## Contents

- [File errors](#file-errors)
- [Data validation errors](#data-validation-errors)
- [Command-line errors](#command-line-errors)
- [No data errors](#no-data-errors)
- [Startup and installation problems](#startup-and-installation-problems)
- [Wrong-looking results](#wrong-looking-results)
- [Display problems](#display-problems)
- [FAQ](#faq)
- [Diagnostic checklist](#diagnostic-checklist)

---

## File errors

All exit with code **1**.

### `Error loading data: File not found: expenses.csv`

The path does not exist. Almost always a working-directory or typo problem rather than a missing file.

Check where you are and whether the file is there:

```bash
pwd                      # Windows: cd
ls expenses.csv          # Windows: dir expenses.csv
```

Fixes, in order of likelihood:

- **Run from the right directory.** Paths are relative to where you run the command, not where `main.py` lives.
- **Use the full path:** `python3 main.py /home/you/finances/expenses.csv`
- **Quote paths with spaces:** `python3 main.py "My Folder/expenses.csv"`
- **Check the extension.** Windows hides known extensions, so `expenses.csv` on screen may really be `expenses.csv.txt`. Enable file-name extensions in Explorer's View tab.
- **Confirm the tool itself works** before blaming your file: `python3 main.py examples/sample_expenses.csv`.

### `Error loading data: Path is not a file: examples`

You gave a directory. Name the file inside it:

```bash
python3 main.py examples/sample_expenses.csv
```

### `Error loading data: File is empty: expenses.csv`

The file is zero bytes. It needs at least a header row:

```csv
date,amount,category,description
```

A file this size usually means an export failed or a redirect overwrote it (`>` truncates before writing). Check with `wc -c expenses.csv`.

### `Error loading data: Permission denied reading file: expenses.csv`

Your user cannot read the file.

```bash
ls -l expenses.csv          # inspect
chmod u+r expenses.csv      # grant yourself read access
```

On Windows, check Properties → Security. If the file is on a network share or an external drive, confirm it is still mounted.

### `Error loading data: File encoding error: expenses.csv`

The file is not valid UTF-8 — normally a Latin-1 or Windows-1252 export containing accented characters or a `£`/`€` symbol in a description or category.

Re-save it as UTF-8:

- **Excel:** Save As → **CSV UTF-8 (Comma delimited)**, not plain "CSV".
- **Google Sheets:** exports UTF-8 already.
- **VS Code:** click the encoding in the status bar → Save with Encoding → UTF-8.
- **Command line:** `iconv -f WINDOWS-1252 -t UTF-8 old.csv > new.csv`

### `Error loading data: CSV parsing error in expenses.csv: ...`

The file is malformed at the CSV level — most often an unclosed double quote, which makes the parser read to the end of the file looking for its partner.

Search for odd quote counts and fix or remove them. Every `"` needs a closing `"` on the same field.

---

## Data validation errors

All exit with code **1**. Messages include the row number, **counting the header as row 1**, so the first data row is row 2 — that number is the line number in your file.

Validation **stops at the first bad row**. Nothing is reported until the whole file is clean, so fix an error, rerun, and repeat. This is deliberate: a silently skipped row would make every total quietly wrong.

### `Validation error: CSV missing required columns: category`

A required header is absent or misspelled. All four of `date`, `amount`, `category`, `description` must be present. Order does not matter and extra columns are ignored.

Check your header against the expected one — lowercase, no spaces:

```csv
date,amount,category,description
```

**Header names are case-sensitive and must be lowercase.** `Category` does not match `category`. Other common causes: `amt` instead of `amount`, `desc` instead of `description`, or a stray space in a header name — `date ` does not match `date`, and reports as `missing required columns: date` while looking perfectly correct on screen.

#### The two cases that confuse people

**All four columns reported missing:**

```
Validation error: CSV missing required columns: amount, category, date, description
```

Either of two causes:

- **No header row** — the first line is data. The parser read `2025-01-05,52.30,Food,Groceries` as your column names. Insert a header line at the top.
- **Every header is capitalised** — `Date,Amount,Category,Description`. Matching is case-sensitive, so all four fail at once. Lowercase them.

**Only `date` reported missing, and your header clearly has it:**

```
Validation error: CSV missing required columns: date
```

Your file starts with a **UTF-8 byte order mark**, an invisible three-byte marker that Excel and Notepad add when saving as UTF-8. The first column name is really `﻿date`, which does not match `date`. The BOM is invisible in every editor, so the header looks perfect.

Fix it by re-saving without the BOM:

- **Excel:** Save As → **CSV UTF-8** *(this format is BOM-free despite the name in most versions; verify with the command below)*
- **VS Code:** the status bar shows `UTF-8 with BOM` → click it → Save with Encoding → **UTF-8**
- **Notepad++:** Encoding menu → **UTF-8** (not "UTF-8-BOM")
- **Command line:** `sed -i '1s/^\xEF\xBB\xBF//' expenses.csv`

Confirm it is gone — a BOM shows as `<feff>` or `ef bb bf`:

```bash
head -c 3 expenses.csv | xxd
```

### `Validation error: Row 2: Invalid date format '01/15/2025' (expected YYYY-MM-DD)`

Dates must be ISO 8601: four-digit year, two-digit month, two-digit day, hyphen-separated.

| Wrong | Right |
|---|---|
| `01/15/2025` | `2025-01-15` |
| `15-Jan-2025` | `2025-01-15` |
| `2025/01/15` | `2025-01-15` |
| `1/5/25` | `2025-01-05` |
| `2025-1-5` | `2025-01-05` |

**This is the most common problem, and spreadsheets cause it.** Excel and Google Sheets reformat dates to your locale on save, so a file that was correct becomes `01/15/2025` after one round trip. To prevent it, format the date column as **Text** before typing, or set the cell format to the custom pattern `yyyy-mm-dd`.

To convert a whole column in a spreadsheet, use a helper column with `=TEXT(A2,"yyyy-mm-dd")`, then paste the result back as values.

An impossible date such as `2025-02-30` produces the same message — the format is right, the day does not exist.

### `Validation error: Row 2: Invalid amount '$42.50' (must be a number)`

Amounts must be bare numbers. No currency symbols, no thousands separators, no units.

| Wrong | Right |
|---|---|
| `$42.50` | `42.50` |
| `42.50 USD` | `42.50` |
| `1,200.00` | `1200.00` |
| `£19.99` | `19.99` |
| `(42.50)` | not supported — see below |

Whole numbers are fine (`85` is read as `85.00`), and more than two decimal places are accepted, though reports display two.

The thousands separator is worth singling out: `1,200.00` unquoted also splits the row into an extra field, so it breaks twice over. Turn off thousands separators in your spreadsheet's number format before exporting.

Accounting-style negatives in parentheses are not recognised, and would be rejected anyway — see the next message.

### `Validation error: Row 2: Amount must be positive, got -42.50`

The amount is zero or negative. **This tool tracks expenses only** — there is no way to record income, a refund, or a credit, and no concept of a balance.

If your export contains credits, remove those rows before running:

```bash
head -1 expenses.csv > expenses_only.csv
grep -v ',-' expenses.csv >> expenses_only.csv
```

Check the result before trusting it; that pattern matches a minus sign anywhere in the row.

If your bank exports expenses as negative numbers and income as positive, strip the leading minus from expense rows and drop the rest. A spreadsheet with `=ABS(B2)` into a helper column is the simplest route.

### `Validation error: Row 4: Category field is empty`

*(Also `Date field is empty`, `Amount field is empty`, `Description field is empty`.)*

Every field is required on every row. Surrounding whitespace is stripped first, so a field containing only spaces counts as empty.

Go to the named line and fill in the blank. Use a placeholder like `Uncategorized` or `Misc` if you genuinely do not know — but keep the spelling consistent, or you will get several near-identical rows in the category report.

A trailing comma such as `2025-01-05,52.30,Food,` is this error, not a parse failure.

---

## Command-line errors

All exit with code **2**.

### `main.py: error: the following arguments are required: file`

You ran the tool with no file. The file path is required and takes no flag:

```bash
python3 main.py expenses.csv
```

### `main.py: error: argument --report: invalid choice: 'weekly' (choose from 'category', 'monthly', 'top')`

Only those three values are accepted, lowercase and exactly as spelled. `Category`, `CATEGORY`, and `categories` are all rejected.

```bash
python3 main.py expenses.csv --report category
python3 main.py expenses.csv --report monthly
python3 main.py expenses.csv --report top
```

### `main.py: error: argument --top-n: invalid int value: 'abc'`

`--top-n` takes a whole number: `--top-n 5`, not `--top-n five` or `--top-n 5.5`.

### `Unexpected error: top_n must be positive, got 0`

Exit code **1**, despite being an argument problem — a known wart, recorded in [Architecture](architecture.md#valueerror-escapes-the-error-hierarchy).

`--top-n` must be at least `1`. The same message appears for negative values (`got -5`). Asking for more than you have is fine — everything is shown with a note.

---

## No data errors

Exit code **3**.

### `No data to report: No valid transactions found in expenses.csv`

The file was read successfully and contained a valid header, but no data rows. The tool has nothing to total.

```bash
wc -l expenses.csv        # 1 means header only
cat expenses.csv
```

Causes:

- **Header only.** Add transaction rows below it.
- **A `>` redirect truncated the file.** `python3 main.py expenses.csv > expenses.csv` destroys the input before reading it. Never redirect onto your source file.
- **Blank lines only after the header.** Blank lines are skipped silently, so a file of header-plus-blank-lines reads as empty.
- **You filtered too hard.** If you built this file with `grep`, check the pattern matched anything: `grep -c ',Food,' original.csv`.

---

## Startup and installation problems

### `python3: command not found`

Try, in order: `python --version`, then `py --version` (Windows). Use whichever works in place of `python3`.

If none works, Python is not installed or not on your `PATH`. Install it from [python.org](https://www.python.org/downloads/) and, on Windows, tick **"Add Python to PATH"** in the installer.

### `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`

Your Python is **older than 3.10**. The code uses `list[str] | None` annotations that are evaluated at import time, and that syntax does not exist before 3.10.

```bash
python3 --version
```

You need 3.10 or newer. If your system Python is older, install a newer one alongside it — `python3.12 main.py expenses.csv` works if that binary exists. `pyenv` (macOS/Linux) or the python.org installer (Windows) both manage this.

### `ModuleNotFoundError: No module named 'expense_tracker'`

You are running from the wrong directory. Imports are absolute and resolve against your current directory, so `main.py` must be run from the project root:

```bash
cd /path/to/expense-tracker
python3 main.py examples/sample_expenses.csv
```

Running `python3 /path/to/expense-tracker/main.py` from elsewhere fails for this reason.

### `python3: can't open file 'main.py': [Errno 2] No such file or directory`

Same cause. `cd` into the project directory first, or give the full path to `main.py` *and* `cd` there anyway, since the import needs it.

---

## Wrong-looking results

No error message, but the numbers are not what you expect.

### The same category appears more than once

```
Food                 $     120.00        3 $    40.00
food                 $      45.00        1 $    45.00
Groceries            $      80.00        2 $    40.00
```

**Category matching is exact and case-sensitive.** `Food`, `food`, `FOOD`, and `Groceries` are four different categories, and trailing characters count too.

Normalise your file with a find-and-replace before running. Longer term, pick six to ten category names, write them down, and reuse exactly those spellings — this is the single biggest source of confusing output.

Note that surrounding whitespace *is* stripped, so ` Food ` and `Food` merge correctly. It is only the letters that must match.

### A month is missing from the monthly report

Months with no transactions are omitted rather than shown as zero. A gap between `2025-01` and `2025-03` means February had no rows in your file.

### Totals are lower than expected

- **Check the row count.** `wc -l expenses.csv` minus one should equal the `Count` in the `TOTAL` line. If it does not, rows are being lost — see the next item.
- **Blank lines are skipped silently.** They do not error, they just do not count.
- **An unquoted comma in a description silently truncates it,** and the extra fields are discarded. `Coffee, pastry, and juice` without quotes stores the description as just `Coffee`. The amount is unaffected, so totals stay right — but if a comma landed in a *numeric* column the row would have failed instead.
- **You may be reading a filtered copy.** Confirm the filename in your command is the file you meant.

### The top report's total does not match the grand total

By design. `TOTAL (top 10)` sums only the ten rows shown. Compare it against the `TOTAL` from `--report category` to see how concentrated your spending is.

### The heading says `Top 100` but only 20 rows appear

Cosmetic bug. When you request more transactions than exist, the heading echoes your request while the total line shows the real count, and a `Note: Only 20 transaction(s) available` is appended. The numbers are correct; the heading is not. Recorded in [Architecture](architecture.md#topexpensesreport-heading-can-contradict-its-total).

### A description is cut off with `...`

Descriptions longer than 30 characters are truncated in the top-expenses report. Shorten them in your file if the detail matters.

---

## Display problems

### Rows wrap and the table looks broken

The top-expenses report needs a terminal at least **80 characters wide**; the category and monthly reports need 50. Widen the window, reduce the font size, or send the output to a file and read it there:

```bash
python3 main.py expenses.csv --report top > top.txt
```

### Columns look misaligned

The reports align with spaces and assume a **monospace font**. A proportional font breaks every column. Terminals use monospace by default; this usually bites when output is pasted into a document or chat.

### Errors appear on screen but not in my redirected file

Working as intended. Reports go to stdout, error messages to stderr, so `>` captures clean report output. To capture both:

```bash
python3 main.py expenses.csv > report.txt 2>&1
```

---

## FAQ

**Can I track income as well as expenses?**
No. Amounts must be positive and there is no transaction type, so income, refunds, and credits cannot be represented. Remove those rows before running.

**Can I filter by date or category?**
Not with a flag. Split the CSV first — [the User Guide](user_guide.md#workflows) has copy-paste recipes for both.

**Does it handle multiple currencies?**
No. Amounts are unitless numbers displayed with a `$`. Mixing currencies in one file produces a meaningless total. Keep one file per currency.

**Can I change the `$` symbol?**
Not from the command line. It is hardcoded in the report format strings in `expense_tracker/reports/report_mode.py`.

**Will it modify or overwrite my CSV?**
Never. Every file is opened read-only and reports only ever go to the terminal. The one way to lose data is redirecting output onto your own input file — `> expenses.csv` truncates it before the tool reads it, which is your shell's doing, not the tool's.

**Is my data sent anywhere?**
No. There is no network code in the project. Everything happens locally, and the tool has no third-party dependencies that could phone home.

**How many transactions can it handle?**
Everything is loaded into memory, so tens of thousands of rows are comfortable and years of personal expenses are nowhere near the limit. It is not built for millions of rows.

**Can I export a report to CSV or Excel?**
Not directly. Reports are formatted text. Redirect to a `.txt` file, or use the [library API](api_reference.md#quick-start-as-a-library) to get at the transactions and write your own output.

**Why does one bad row stop everything instead of being skipped?**
Because a skipped row makes every total quietly wrong while still looking complete. An error naming the row is loud; a missing row is silent. The reasoning is in [Architecture](architecture.md#fail-fast-validation-rather-than-skip-and-warn).

**Can I add my own report type?**
Yes — that is what the design is for. [Architecture](architecture.md#adding-a-report-type) walks through it with a complete working example.

**Do I need to install anything besides Python?**
No, for using the tool. `pytest` only if you want to run the test suite.

**Why are 6 tests skipped when I run the suite?**
Expected. `tests/test_documentation_quality.py` has stale hardcoded paths. See [Contributing](contributing.md#known-issue-documentation-quality-tests).

---

## Diagnostic checklist

When something is wrong and you are not sure where to start, work down this list. Each step rules out a layer.

**1. Does the tool work at all?**

```bash
python3 main.py examples/sample_expenses.csv
```

Fails → the problem is your installation or Python version, not your data. Go to [Startup problems](#startup-and-installation-problems).

**2. What is the exit code?**

```bash
python3 main.py your_file.csv; echo "exit=$?"
```

`1` → [File](#file-errors) or [validation](#data-validation-errors). `2` → [your command](#command-line-errors). `3` → [no data](#no-data-errors).

**3. Does the file look right?**

```bash
head -3 your_file.csv          # header plus two rows
wc -l your_file.csv            # row count
head -c 3 your_file.csv | xxd  # BOM check — ef bb bf means trouble
```

**4. Does the row count match?**

Compare `wc -l` minus one against the `Count` in the report's `TOTAL` line. A mismatch means rows are being dropped — check for blank lines and unquoted commas.

**5. Bisect the file.**

If a large file fails and the row number does not make the cause obvious, cut it in half:

```bash
head -50 your_file.csv > first_half.csv
python3 main.py first_half.csv
```

The error message already names the row, so this is mainly useful when the row *looks* fine and you need to compare it against one that works.

**6. Check the layer.**

```bash
python3 -c "
from expense_tracker.data.transaction_loader import CSVTransactionLoader
t = CSVTransactionLoader().load('your_file.csv')
print(len(t), 'transactions'); print(t[0]); print('sum:', sum(x.amount for x in t))
"
```

A correct count and sum here means loading is fine and the surprise is in a report. This also gives a full traceback, which the CLI deliberately hides.

**Still stuck?** Open an issue with your Python version (`python3 --version`), the exact command, the full error message, and the first three lines of your CSV with any private details replaced.
