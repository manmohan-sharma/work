# Refactoring Notes — `cli_interface_v1.py` → `cli_interface_v2.py`

## Method

Four refactorings applied one at a time. After each, two gates had to pass before
moving on:

1. `pytest test_cli_interface.py` — the 6 contract tests, unmodified
2. **Golden-output diff** — v2's stdout compared byte-for-byte against v1's across
   12 inputs, including edge cases the test suite does not exercise

The second gate exists because the supplied tests only assert substrings
(`'Food' in output`, `'150.50' in output`). They pass even if borders, column
alignment or blank-line padding are mangled. Substring assertions are not a
refactoring safety net; byte equality is.

| Step | Refactoring | Tests | Golden output |
|---|---|---|---|
| R0 | Verbatim copy v1 → v2 | 6/6 | identical |
| R1 | Magic values → class constants | 6/6 | identical |
| R2 | Report branches → `REPORT_TITLES` + `_print_panel` | 6/6 | identical |
| R3 | Error branches → `ERROR_CATEGORIES` table | 6/6 | identical |
| R4 | Complete type hints + docstrings | 6/6 | identical |

---

## Changes

### R1 — Magic values extracted into class constants

**What**: 16 constants (`LINE_WIDTH`, `HEAVY_RULE`, `LIGHT_RULE`, `ERROR_RULE`,
`INDENT`, `LABEL_WIDTH`, `AMOUNT_WIDTH`, `AMOUNT_PRECISION`, `CURRENCY_SYMBOL`,
`TOTAL_LABEL`, …) replacing literals scattered through both methods.

**Why**: `50` appeared 12 times, `"="` 8 times, `"!"` 6 times. Changing the panel
width meant 12 separate correct edits, with no way to tell a width `50` from a
coincidental `50`.

**Benefit**: width and styling are now a single point of change, and because they
are class attributes they are overridable by subclass — `test_constants_actually_drive_the_output`
proves this by rendering through a `LINE_WIDTH = 20` subclass.

**Risk**: LOW. Values substituted, structure untouched.

### R2 — Duplicated report branches collapsed

**What**: The `summary` and `monthly` arms of `display_report` were byte-identical
apart from one title string. Replaced with a `REPORT_TITLES` mapping plus three
focused helpers: `_build_report_body`, `_format_amount_row`, `_print_panel`.

**Why**: 13 lines duplicated. Every layout decision existed twice, so any fix had
to be made twice — and a fix applied to only one arm would still pass the tests,
since each mode has just one test.

**Benefit**: `display_report` drops from 33 lines to 16 and from CC 5 to CC 2.
Adding a third report mode is now a one-line dict entry rather than a 13-line
copy-paste. `test_report_modes_are_data_not_branches` enforces that this stays true.

**Risk**: LOW. Pure extraction; verified by byte-identical output.

### R3 — Duplicated error branches collapsed

**What**: Three `if`/`elif` arms, each printing the same 4-line panel with a
different heading, replaced by an ordered `ERROR_CATEGORIES` table read by
`_classify_error`.

**Why**: The classification *policy* (which keywords mean which category) was
buried inside control flow, invisible to anyone scanning the class.

**Benefit**: 15 lines → 2 plus a 5-line data table. The rules are now reviewable
data and directly testable.

**Risk**: **MEDIUM — the one genuinely risky change.** The table's order is
behavior, not presentation. `'value'` and `'invalid'` also appear in file-related
messages, so a message like `"Invalid value in file 'expenses.csv'"` matches both
category sets, and whichever is tested first wins. Reordering the table silently
changes that message's heading.

This risk was verified rather than asserted — see *Mutation testing* below.

### R4 — Complete type annotations

**What**: All parameters and returns annotated; `ReportData` and `ErrorCategory`
aliases introduced; constants annotated `ClassVar`.

**Why**: v1 had zero annotations, so nothing communicated that `report_data` is a
mapping with `mode`/`data`/`total` keys. `ReportData = Mapping[str, Any]` matches
what `ReportEngine.generate_report` actually returns (`Dict[str, Any]`).

**Benefit**: 0% → 100% annotation coverage; `mypy cli_interface_v2.py` reports
*Success: no issues found*.

**Risk**: LOW. Annotations are not enforced at runtime, so behavior cannot change.

---

## Metrics

| Metric | v1 | v2 | Change |
|---|---|---|---|
| Total lines | 64 | 137 | **+114%** ↑ |
| Non-blank lines | 52 | 108 | +108% ↑ |
| Executable statements | 42 | 50 | +19% ↑ |
| Methods | 2 | 6 | +4 |
| Class constants | 0 | 16 | +16 |
| Longest method | 33 lines | 16 lines | **−52%** ✓ |
| Peak per-method complexity | CC 5 | CC 4 | −20% ✓ |
| Total complexity | 10 | 12 | +20% ↑ |
| Distinct repeated source lines | 12 | 3 | **−75%** ✓ |
| Type hint coverage | 0% | 100% | ✓ |
| Test coverage | 98% | **100%** | ✓ |
| Contract tests passing | 6/6 | 6/6 | maintained |

### Reading these honestly

Three metrics moved the **wrong** way, and they should not be spun as wins:

- **Lines of code more than doubled.** Most of the increase is docstrings,
  annotations and the constants block — not logic. But it is a real cost: there
  is more text to read, and a reader now has to jump between `display_report`,
  `_build_report_body` and `_print_panel` to reconstruct one panel that v1 showed
  in a single glance. For a 64-line module, that trade is arguable.
- **Total cyclomatic complexity rose 10 → 12**, because complexity is counted
  per method with a baseline of 1, and there are now six methods instead of two.
  The metric that actually matters for readability — *peak per-method*
  complexity — fell from 5 to 4, and the worst method fell from CC 5 to CC 2.
- **Statement count rose 42 → 50.** More methods means more `def` and `return`
  statements.

The defensible claim is not "the code got smaller." It is that duplication fell
by 75%, no method now does four jobs at once, styling is a single point of change,
and the type checker can see the contract — at the cost of more lines and more
indirection.

---

## Verification

### Mutation testing

The improvement suite was itself tested, by deliberately breaking v2 and checking
the tests noticed:

| Mutation | Expected | Result |
|---|---|---|
| Hardcode `50` back into `_print_panel` | quality tests fail | ✓ caught (2 failures) |
| Swap `ERROR_CATEGORIES` order | behavior tests fail | ✗ **not caught initially** |

The second mutation exposed a real hole. The original error cases could not
discriminate the ordering: `"profile not found"` matches `'file'` (inside
*pro-file*) but never `'invalid'` or `'value'`, so no case matched both keyword
sets, and the R3 risk described above was untested despite a docstring claiming
otherwise. Two ambiguous cases were added — `"Invalid value in file 'expenses.csv'"`
and `"File contains an invalid value"` — after which the mutation fails 2 tests as
it should.

This is the reason to mutation-test a suite that exists to prove safety: it
passed 22/22 while blind to the single highest-risk change in the refactoring.

### Final state

```
pytest test_cli_interface.py test_refactoring_improvements.py
→ 30 passed, cli_interface_v2.py 100% coverage

mypy cli_interface_v2.py
→ Success: no issues found in 1 source file
```

---

## Deliberately not changed

**Unknown report mode uses a bare print, not the error panel** (`v1:44`).
`display_report` prints `\nError: Unknown report mode 'x'\n` with no border, while
`display_error` prints a bordered `!` panel for the same class of problem. Unifying
them would be a genuine improvement in consistency — and a **behavior change**,
which the exercise constraints forbid. It is preserved exactly, `UNKNOWN_MODE_TEMPLATE`
merely names the string.

Note this path was uncovered in v1 (the one missed line at 98% coverage), so it
had no test protecting it during the refactor. It is covered in v2.

Recommended as the first change for a version permitted to alter the output contract.
