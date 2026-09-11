# Concept 3: Dependency Validation Review

## Exercise Overview

Review file processing code that demonstrates AI-specific red flags, particularly phantom libraries and dependency issues commonly found in AI-generated code.

## Learning Objectives

- Identify AI-specific code patterns and issues
- Learn to validate dependencies and imports
- Recognize phantom libraries that don't exist
- Understand the importance of verifying AI-generated code

## 🤖 AI-Specific Focus

This exercise specifically targets patterns commonly found in AI-generated code. Pay special attention to:
- Library imports and dependencies
- Function signatures and usage
- Context awareness and completeness

## Instructions

### Step 1: Run Phantom Library Detection Tests
```bash
cd concept3-dependency-validation-review/starter
pytest test_phantom_libraries.py -v -s
```

**Expected Output:**
- Import tests reveal dependency issues
- Dependency validation tests demonstrate verification methods
- Tests show patterns for validating external libraries

### Step 2: Review the Code
1. **Open** `starter/file_processor.py` and examine the imports
2. **Apply** the engineering code review framework:
   - Structure & Organization
   - Naming & Clarity
   - Error Handling
   - Dependency Validation
3. **Research any unfamiliar libraries** - verify they exist and are maintained

### Step 3: AI Pattern Detection
4. **Apply** the standard review framework PLUS AI-specific checks:
   - Library names that sound "too good to be true"
   - Generic, appealing names like "advanced" and "pro"
   - Missing documentation or GitHub repos
5. **Check for other issues:**
   - Using `print()` instead of logging
   - Generic exception handling

### Step 4: Run Real Dependencies Tests
```bash
cd ../solution
pytest test_real_dependencies.py -v
```

**Expected Output:**
- All tests pass with real libraries
- Proper error handling demonstrated
- No phantom dependencies detected

### Step 5: Compare and Learn
6. **Compare** the fixed version that uses real, verified libraries

## Review Template

### Dependency Analysis

**Import Verification:**
- [ ] `pandas` - Real library? ✅
- [ ] `advanced_file_processor` - Real library? ❌
- [ ] `data_cleaner_pro` - Real library? ❌ 
- [ ] Other imports: [SimpleImputer,StandardScaler] ✅

**Phantom Library Detection:**
- [ ] Library 1: [advanced_file_processor] - Status: Fake
- [ ] Library 2: [data_cleaner_pro] - Status: Fake

### AI-Specific Red Flags

**Missing Context:**
- [No] Does the code match what was requested?
- [Yes] Is any expected functionality missing?
- [Yes] Are there unexplained gaps in logic?

**Plausible but Wrong:**
- [advanced_file_processor, data_cleaner_pro] Libraries that sound real but aren't
- [SimpleImputer(strategy=method), FastProcessor] Function calls with incorrect signatures
- [None deprecated; sklearn fit_transform ndarray round-trip (no set_output), os.path over pathlib, f-string logging] Outdated or deprecated patterns

### Code Quality Issues

**Error Handling:**
- [x] Generic exception handling: [bare `except Exception as e` (L117) catches everything; worse, `except ValueError` (L115) swallows the all-NaN crash and mislabels it "Invalid file format" on a file that parsed fine. Failures are logged only - caller gets a silently shortened list]
- [x] Missing specific error types: [`ImportError` (absent openpyxl/pyarrow engines), `pd.errors.EmptyDataError` / `ParserError`, `PermissionError`, `TypeError`/`ValueError` for non-list input]

**Logging and Debugging:**
- [x] Using print() instead of logging: [NONE - 0 `print()` calls, correctly uses `logging.getLogger(__name__)`. But `logging.basicConfig()` at L25 hijacks root config at import (app's job, not a module's), and all 6 calls use eager f-strings instead of lazy `%s` args]
- [x] Missing debug information: [no `logger.debug()` anywhere; no `exc_info=True`/`logger.exception()` so every traceback is discarded; sklearn's "Skipping features ['allnan']" goes to `warnings`, bypassing the logger; no summary of which/how many files failed]

### Replacement Recommendations

**For phantom libraries, suggest real alternatives:**
- `advanced_file_processor` → [`pandas` readers (already in use) + the engines they actually need: `openpyxl` for .xlsx/.xls, `pyarrow` for .parquet; `chardet` if encoding detection was the "advanced" part]
- `data_cleaner_pro` → [`sklearn.impute.SimpleImputer` + `StandardScaler` (already in use) for imputation/scaling; plain `pandas` `dropna`/`fillna` for row cleanup; `pandera` for schema validation]

**For code improvements:**
1. [Add `.set_output(transform="pandas")` to the imputer and scaler so columns realign by name - fixes the all-NaN crash and the bogus "Invalid file format" label in one change]
2. [Split `clean_dataset` into `impute_missing` + `standardize_numeric`, move `dropna(how='all')` *before* imputation, and return the fitted transformers so the same transform is reusable]
3. [Return per-path results (or `(results, failures)`) instead of a silently shortened list; validate `file_paths` is a list and `method` is in the documented set; declare all deps in `requirements.txt`]

### Overall Assessment

- **AI Pattern Recognition:** [Yes - but there are none left in this file. All 5 imports (`os`, `logging`, `pandas`, `SimpleImputer`, `StandardScaler`) verify as real; `advanced_file_processor`/`data_cleaner_pro` survive only in `test_phantom_libraries.py`'s expectations, so the suite fails at import, not on an assertion]
- **Quality Rating:** **Fair** [complete docstrings, type hints, real logging, specific-exception-first ordering - but 3 of 4 advertised formats can't run, `clean_dataset` crashes on an all-NaN column, and one function is dead *and* wrong]
- **Primary Issue:** **Both** [deps: no manifest, undeclared openpyxl/pyarrow engines. Quality: 7 confirmed defects, all reproduced by execution]
- **Recommendation:** **Modify** [structure is sound and worth keeping; no rewrite needed - the 3 fixes above clear the blocking defects]

## How to Verify Libraries

1. **Check PyPI:** Search for the library on pypi.org
2. **Google Search:** Look for official documentation
3. **GitHub:** Check if there's an active repository
4. **Stack Overflow:** See if others are using it
5. **Package Managers:** Try `pip search` or `conda search`

## Common AI Library Issues

**Phantom Libraries:**
- Libraries that sound plausible but don't exist
- Combinations of real words that seem legitimate
- Outdated libraries that are no longer maintained

**Version Mismatches:**
- Using deprecated APIs
- Mixing different library versions
- Incorrect function signatures

**Context Loss:**
- Missing imports for referenced functions
- Incomplete implementations
- Functions that don't match their names

## Red Flag Patterns

🚩 Libraries with generic, appealing names like:
- `advanced_[something]_processor`
- `[domain]_pro` or `[domain]_master`
- `fast_[operation]` or `quick_[tool]`

🚩 Function calls that seem too convenient:
- Methods with `auto_detect` parameters
- One-line solutions to complex problems
- Perfect APIs that handle everything

After completing your analysis, examine the solution to see how the phantom libraries are replaced with real, well-maintained alternatives, and how proper error handling and logging are implemented.