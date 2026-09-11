# Concept 2: Phantom Dependencies Pattern Recognition

## Exercise Overview

Review code that demonstrates the Phantom Dependencies pattern - when AI suggests libraries that sound plausible but don't exist, are outdated, or use incorrect APIs.

**Scenario**: You had a simple, working name formatter (`original_name_formatter.py`) and asked AI to "make the name formatting more robust". AI delivered an "enhanced" version (`name_formatter.py`) with impressive-sounding libraries like "name_formatter_pro" and "string_utils_plus" that don't actually exist.

**Your Task**: Compare the original vs AI-"improved" versions to identify phantom dependencies and broken imports.

## Learning Objectives

- Recognize imports that seem "too good to be true"
- Identify outdated or deprecated library usage patterns
- Understand why AI generates phantom dependencies
- Learn to verify library existence and current API documentation

## Instructions

### Step 1: Run Tests to See the Pattern
```bash
cd concept2-phantom-dependencies-pattern/starter
python -m pytest test_name_formatter.py -v
```

**Expected Output:**
- **Original version tests**: All pass (real dependencies work)
- **AI version import tests**: FAIL (phantom libraries don't exist)
- **Source code analysis tests**: Pass (detecting phantom patterns in code)
- **Comparison tests**: Show how AI broke working code with fake libraries

### Step 2: Review the Code
1. **First, examine the original working code** in `starter/original_name_formatter.py` 
2. **Then, review the AI-"improved" version** in `starter/name_formatter.py`
3. **Compare the two versions** and apply the phantom dependency checklist:
   - What libraries did AI add that don't exist?
   - What deprecated APIs did AI introduce?
   - How did AI make the simple, working code unusable?
4. **Document** your findings using the template below

### Step 3: Run the Solution Tests
```bash
cd ../solution
python -m pytest test_name_formatter.py -v
```

**Expected Output:**
- All tests pass with real, verified dependencies
- Same functionality using legitimate libraries
- Notice how real APIs are properly used

### Step 4: Compare and Learn
4. **Compare** your analysis with the corrected implementation

## Review Template

### Phantom Dependency Analysis

**Suspicious Imports:** *(all four verified against PyPI on 2026-09-09 — see Verification Results)*
- [x] Library name: **`name_formatter_pro`** (`name_formatter.py:1`) — Red flags: `_pro` suffix; the package name is a verbatim restatement of the task ("name formatter"), which is the strongest tell — real libraries are named for their domain, not for your ticket; **PyPI 404**.
- [x] Library name: **`string_utils_plus`** (`name_formatter.py:2`) — Red flags: `_plus` suffix; **PyPI 404**. Note the plausible near-miss: **`python-string-utils` is real** (PyPI 200). The phantom is a corrupted memory of a genuine package, which is exactly why it reads as credible.
- [x] Library name: **`text_optimizer`** (`name_formatter.py:3`) — Red flags: scope too broad to be one package ("optimizes text"); **PyPI 404**.
- [x] Library name: **`String`** (`name_formatter.py:5`) — Red flags: **Python 2 module name**. The stdlib module is lowercase `string`; capital-`String` has not existed since Python 1.x. Also **entirely unused** in the file — a dead import that only signals the training data was old. Confirmed: `python -c "import String"` → `ModuleNotFoundError`.

**API Usage Issues:**
- [x] Function: **`text_optimizer.BatchProcessor()`** (`name_formatter.py:47`) — Issue: **`NameError`, not `ImportError` — and it is a real bug independent of the phantom packages.** Line 3 is `from text_optimizer import FastStringCleaner`, which binds only `FastStringCleaner`; the bare module name `text_optimizer` is never bound (AST check confirms bound names are `AdvancedNameProcessor`, `FastStringCleaner`, `SmartCapitalizer`, `String`, and the two functions). Even if all three packages were `pip install`-able, this line would still crash. **This is the most instructive defect in the file:** the phantom imports are caught by the interpreter on line 1, so they mask an ordinary Python error further down that no import-check would ever surface.
- [x] Function: **`optimizer.process_batch(data=users, processor_func=format_user_name, ...)`** (`name_formatter.py:50`) — Issue: **arity mismatch that cannot work under any implementation.** `users` is a list of dicts (per the original and the tests); `format_user_name` takes two positional `str` arguments. No batch runner can bridge `dict` → `(first, last)` without being told the keys. The original did this explicitly with `user.get('first_name', '')`; that extraction logic was deleted and nothing replaced it.
- [x] Function: **`SmartCapitalizer.smart_title_case(..., detect_prefixes=True, handle_apostrophes=True)`** and **`AdvancedNameProcessor(auto_detect_culture=..., smart_casing=..., unicode_normalization="advanced")`** / **`combine_names(..., style="formal", validate_output=True)`** — Issue: fabricated keyword arguments with fabricated value vocabularies. `unicode_normalization="advanced"` is the giveaway — real Unicode normalization takes `NFC`/`NFD`/`NFKC`/`NFKD` (`unicodedata.normalize`), never a marketing adjective. Invented kwargs are harder to spot than invented packages because they fail only at call time, after the import gate has been passed.

**Verification Results:**
- [x] Checked package manager (pip/npm): `curl https://pypi.org/pypi/<name>/json` → **`name_formatter_pro` 404, `string_utils_plus` 404 (and `string-utils-plus` 404), `text_optimizer` 404 (and `text-optimizer` 404), `String` 404.** Control queries returning **200**: `nameparser`, `python-string-utils`, `unidecode`, `probablepeople`. Four for four are phantom; the method distinguishes real from fake cleanly.
- [x] Checked official documentation: No documentation exists for any of the four — there is no project page, no repository, no release history. For `String`, the CPython docs confirm the stdlib module is lowercase `string`; the capitalized form is a Python-2-era artifact.
- [x] Checked current API signatures: Not applicable — you cannot validate a signature for a class that does not exist. This is the point: **the signature check is unreachable until the package check passes**, so package existence must be verified first, before any of the API detail is even worth reading.

### Pattern Recognition

**Phantom Dependency Indicators:**
- [x] Library names with "pro", "advanced", "fast", "super" prefixes — **all three modules and all three classes.** `name_formatter_pro`, `string_utils_plus`, `AdvancedNameProcessor`, `SmartCapitalizer`, `FastStringCleaner`, `super_clean`, `smart_title_case`. Six adjectives, zero implementations.
- [x] Imports that seem too convenient or comprehensive — **`AdvancedNameProcessor(auto_detect_culture=True)`.** Culture-aware name handling is a genuinely hard, contested problem (see the real `nameparser` and `probablepeople`, both of which are careful about their limits). A boolean flag that solves it is the clearest "too good to be true" signal in the file.
- [x] Deprecated modules from old documentation — **`import String`** (Python 2).
- [x] Function calls that don't match current API docs — every call in the file, plus the two structural defects above (`NameError` at line 47, arity mismatch at line 50).

### Impact Assessment

**Immediate Impact:**
- [x] Code won't run due to import errors — **the module is dead on line 1.** `import name_formatter` raises `ModuleNotFoundError: No module named 'name_formatter_pro'`. Not degraded, not partly working: zero of the two functions is callable, and any module that imports this one fails too.
- [x] Dependencies can't be installed — `pip install` fails for all four. There is no version pin, mirror, or index that fixes this, because the packages were never published.
- [x] Function signatures don't match — `process_batch` is handed a two-argument function and a list of dicts (line 50), and `BatchProcessor` is referenced through an unbound name (line 47). Both would fail even in a world where the packages existed.

**Long-term Impact:**
- [x] Technical debt from incorrect assumptions — **working code was replaced with code that has never once executed.** The original handled `None`/empty inputs, returned `"Unknown User"` as a fallback, and extracted `first_name`/`last_name` from dicts. All of it was deleted, along with both docstrings, in exchange for nothing. Recovery means reverting, not repairing — so this file is also a Context Gap (Concept 1): the request was "make it more robust," and the deliverable removed every actual robustness feature the function had.
- [x] Security risks from unvetted libraries — **the serious one, and it outlives the fix.** Four names now sit in a source file (and would land in any `requirements.txt` derived from it) that resolve to nothing on PyPI. Anyone may register `name_formatter_pro` tomorrow, and the next `pip install` of that requirements file executes their code at install time. This is dependency confusion / typosquat-bait: an unresolvable name is not an inert error, it is an unclaimed namespace pointed at by your build. A phantom import is a supply-chain liability, not just a broken build — which is why deleting the names matters more than commenting them out.
- [x] Maintenance burden from deprecated APIs — `import String` marks the file as carrying Python-2-era assumptions; anything else copied from the same source deserves the same suspicion.

### Recommendations

1. **Verification Strategy:** Check existence before reading a single line of the implementation, because a plausible-looking call site makes a fake package *more* convincing, not less. Cheapest sufficient check: `pip index versions <pkg>` or `curl -s -o /dev/null -w '%{http_code}' https://pypi.org/pypi/<pkg>/json` — a 404 ends the review of that import. Then confirm the project has a repository and release history (a package that exists but was published last week by an unknown author is a different risk, not a cleared one). In CI, `pip install --dry-run -r requirements.txt` or `pip-compile` turns this into a build failure rather than a review responsibility. Treat any import you cannot resolve as **unresolved and dangerous**, not merely missing — leaving the name in the file leaves a namespace someone else can claim.
2. **Alternative Libraries:** For this task, **none — the standard library is the right answer**, which is what the solution demonstrates: `.strip()`, `.title()`, and `str.split("'")` cover the requirement, and `string.ascii_letters` backs the validator. Where real name handling genuinely exceeds built-ins, the verified options are **`nameparser`** (splits titles/suffixes/prefixes — the actual `detect_prefixes` the phantom advertised), **`probablepeople`** (probabilistic name parsing), **`unidecode`** (transliteration), and **`python-string-utils`** (the real package `string_utils_plus` was imitating). All four return 200 on PyPI. Note that each is narrower than the phantom it replaces — that narrowness is what makes them real.
3. **API Validation:** Once the package is confirmed, verify the surface against the installed version, not against recall: `pip show <pkg>` for the version, then `python -c "import pkg; help(pkg.Thing)"` or `inspect.signature`. Prefer the docs for the pinned version over a search result, which is how `import String` survives into 2026. For any argument that names a standard — encodings, normalization forms, locales — check that the accepted values are the standard's values; `unicode_normalization="advanced"` fails that test instantly, where `NFKC` would pass it.

### Overall Assessment

- **Pattern Confidence:** **High.** Unambiguous and independently verified: four non-existent imports (4/4 PyPI 404 against a 4/4 real-package control), six invented classes and methods, one Python-2 module name, and an unbound-module `NameError` that is a genuine bug in its own right. This is the cleanest of the three Lesson 2 fixtures — concepts 1 and 3 ship code that does not match their scenarios, this one does exactly what it claims.
- **Recommendation:** **Reject**
- **Reasoning:** This is the one case in the lesson where **Modify is the wrong call.** There is nothing to salvage: every line of logic routes through a class that does not exist, so no subset of the file is worth keeping, and there is no partial-credit repair — you would be writing it from scratch inside a diff. Meanwhile the thing it replaced was working, tested, and handled the edge cases (`None`, empty strings, missing dict keys, the `"Unknown User"` fallback) that the "more robust" version silently dropped. Revert to `original_name_formatter.py` and add the specific robustness actually wanted — the solution shows this costs about fifteen lines of stdlib and no dependencies at all. Rejecting also disposes of the supply-chain exposure properly: the four unclaimed names leave the codebase instead of lingering in a comment or a requirements file where a future `pip install` could resolve them to someone else's package.

### Test Run Notes

`python -m pytest test_name_formatter.py -v` in `starter/` → **9 passed, 0 failed**, matching the README's Step 1 expectations. The wording there is worth reading carefully: "**AI version import tests: FAIL**" describes the *import* failing, not the test. `test_ai_version_import_fails` asserts `not AI_IMPORTS_OK` and therefore **passes** because the import broke. A green suite here is the pattern being confirmed, not absent.

Step 3's path is wrong in this copy — `cd ../solution` does not exist. The solution is at `exercises/concept2-phantom-dependencies-pattern/solution/`; its **6 tests pass**, using only `import string` and `typing`. Two observations on it: `test_uses_only_real_libraries` verifies the absence of phantoms, which is a good habit to copy into a real project as a lint rule. And `.title()` still mangles `"mcdonald"` → `"Mcdonald"`, so the solution is honest about scope rather than claiming the culture-awareness the phantom advertised — which is precisely the difference between a real fix and `auto_detect_culture=True`.

## Key Learning Points

- Always verify that imported libraries actually exist before using AI suggestions
- Check package managers and official documentation for current API signatures
- Be suspicious of library names that sound "too good to be true"
- AI training data includes code from different time periods, leading to outdated suggestions

## Common Red Flags for Phantom Dependencies

1. **Convenient Names:** Libraries with "advanced", "pro", "fast", "super" in the name
2. **Perfect Fit:** Imports that seem exactly tailored to your use case
3. **Deprecated Paths:** Old import paths from outdated documentation
4. **Version Mismatches:** Function signatures that don't match current library versions
5. **Missing Context:** Libraries used without proper setup or configuration

After completing your review, check the solution to see how the same functionality can be achieved using real, well-documented libraries with proper API usage.