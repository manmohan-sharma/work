# AI-Assisted Development Project Report

**Student Name:** [Your Name]
**Project Title:** Task Manager CLI
**Date:** 2026-09-11

## Executive Summary

I built a command-line task manager extending the course starter with three features
beyond basic CRUD: sorting and filtering, multi-format export, and undo/redo. Each uses a
design pattern the feature genuinely needed. The application runs as one-shot subcommands
for scripting or as an interactive shell where the undo history is live.

The starter provided a `TaskManager`, a `FileHandler`, and 15 tests. The finished project
has 158 tests at 99% coverage and passes `black`, `isort`, `flake8`, and `mypy` cleanly.

Every line was drafted by Claude, then reviewed, tested, and in several cases corrected by
me. The useful finding was the specific shape of AI unreliability: sound on structure, weak
on edge-case semantics. Every substantive bug was in behaviour under unusual input, never
in the organisation of the code.

## Project Overview

### Problem Statement

The starter's `main.py` printed three hardcoded tasks and saved them. It demonstrated a
structure but was not usable: no way to enter a task, find one among many, recover from a
mistaken deletion, or get data out.

### Solution Approach

I kept the task domain so the starter's code and tests stayed useful. `TaskManager` knows
only the data model; sorting, exporting, undo, and the CLI each live in their own module
depending on the model but not on each other, so any one can be tested or replaced alone.
Stack: Python 3.10, `click` (already in `requirements.txt` but unused), `pytest`.

### Final Features

- [x] CRUD with validation on descriptions and priorities
- [x] Sorting and filtering by priority, date, description, status, keyword
- [x] Export to JSON, CSV, Markdown
- [x] Undo and redo for add, complete, delete
- [x] Interactive shell plus scriptable subcommands
- [x] Persistence that survives a corrupt save file

## AI Collaboration Experience

### AI Tools Used

- [x] Claude (via Claude Code)

### Collaboration Workflow

My cycle was: state the requirement, review the generated code, then write tests aimed at
the edge cases the code did not obviously handle. The tests were where I did my real
reviewing — reading told me whether code was well-organised, testing told me whether it was
correct. I also learned to control scope: Claude's first plan added git setup, security
scanning, a licence file, a fourth pattern, and an inflated coverage target. None were
required. Cutting them took one instruction, recorded in `docs/project_plan.md`.

### Most Valuable AI Interactions

Seven interactions are detailed in `docs/ai_edit_log.md`. Three mattered most.

**The CSV exporter.** Claude followed the factory example in `docs/design_patterns.md`
faithfully, including deriving the CSV header from `data[0].keys()`. Because
`complete_task` adds a `completed_at` key, exporting a pending task followed by a complete
one makes `DictWriter` raise on an unexpected field. The guide's version also returns early
on an empty list, producing a zero-byte file. A fixed column set fixes both. The bug came
from trusted course material, and the AI reproduced it because I pointed it there.

**The undo implementation.** Claude's first `DeleteTaskCommand.undo` appended the restored
task to the end of the list, and `CommandHistory.execute` did not clear the redo stack.
Both are structurally correct and behaviourally wrong: appending silently reorders the
user's list, and an uncleared redo stack reapplies work from an abandoned branch.

**The CLI design.** I asked for `undo` as a subcommand. Claude built the rest of the group,
then stopped to point out this could not work: each invocation is a separate process, so
the history would always be empty. This was the most valuable thing it did — it refused the
request as stated instead of shipping a feature that would have looked complete and done
nothing.

### Challenges with AI Collaboration

AI struggled where correctness depends on user expectation rather than specification. It
never produced malformed code, and `mypy` caught its one invented type annotation
instantly. It produced plausible code with subtly wrong boundary behaviour, and it expanded
scope by default.

## Software Engineering Practices

### Code Quality Measures

- [x] Formatting (Black, isort), configured in `pyproject.toml`
- [x] Linting (flake8, mypy with `disallow_untyped_defs`)
- [x] Type hints on every function
- [x] Google-style docstrings; comments explain why, not what
- [x] Validation at the model boundary; the CLI converts exceptions to messages

I configured the toolchain before any feature work: the starter had 51 `flake8` errors, and
`black`'s 88-character default contradicts `flake8`'s 79 until both are configured. Strict
typing then surfaced a latent starter bug — `add_task` was declared `-> int` but returned
`task["id"]` from a dict inferred as `dict[str, object]`, so the annotation was
unverifiable.

### Testing Strategy

Unit tests per module covering happy path, edge cases, and error conditions, at 99%
coverage. The number is not what I relied on: the most valuable tests encode specific bugs
found, and each fails against the earlier implementation. I did not use strict TDD — I
generated an implementation, then enumerated edge cases while writing tests, and that
enumeration found the defects. Writing tests first would have caught the CSV bug sooner.
The CLI is tested through `click.testing.CliRunner`, including the shell via stdin, taking
`main.py` from 0% to 99% and finding three bugs manual testing missed.

### Design Patterns Used

- **Strategy** (`utils/sorting.py`): each ordering and filter is a class behind one
  interface, composed at runtime by `TaskQuery`. The alternative is an if/elif chain that
  grows with every new ordering.
- **Factory** (`utils/exporters.py`): maps a user-supplied format string to an exporter.
  The format is untrusted input needing validation in one place.
- **Command** (`utils/commands.py`): each operation knows how to perform and reverse
  itself. Undo requires exactly this; the alternative is `TaskManager` tracking its own
  history, a separate concern from storing tasks.

### Code Structure and Organization

`main.py` holds the CLI; shell and subcommands route through one `TaskApp` handler layer,
so each operation has one implementation. Dependencies run one way: features depend on the
model, the CLI on the features, nothing back. The significant refactor was `TaskManager`
itself — undo required `delete_task` to return the removed task plus new `index_of`,
`insert_task`, and `reopen_task` methods. I also made `delete_task` raise on a missing ID;
the starter deleted silently, so `delete 999` reported success.

## Technical Challenges and Solutions

### Challenge 1: Undo cannot work in a stateless CLI

**Problem:** Undo was required, but a subcommand CLI starts a fresh process each
invocation, leaving no history.

**Solution:** An interactive shell for session-based operations, subcommands retained for
scripting, both sharing one handler layer. The limitation is stated in the README.

**AI Involvement:** Claude identified the problem before implementing and offered to
persist the history instead. I rejected that as a larger feature than undo itself.

**Lessons Learned:** An AI that pushes back on a flawed request is more valuable than one
that implements it well.

### Challenge 2: A corrupt save file could silently duplicate task IDs

**Problem:** The CLI reloads `data/tasks.json` every run, so anything malformed reaches the
model directly.

**Solution:** `from_dict` degrades gracefully on missing keys and malformed entries, and
trusts the stored `next_id` only when it exceeds the highest existing ID.

**AI Involvement:** I asked Claude to enumerate what could go wrong with the file before
writing code. It listed four cases including the ID collision, which I would not have
thought of unprompted.

**Lessons Learned:** That case is dangerous because it is silent — a stale counter hands
out a duplicate ID, after which `delete_task` removes only one of two matching tasks.
Asking for failure modes worked far better than asking for "proper error handling".

### Challenge 3: A path traversal vulnerability found in final review

**Problem:** Export filenames came from the user and were joined to the data directory
without checking. `export json --output ../../../../tmp/x.json` wrote outside the data
directory entirely, on both the subcommand and shell routes.

**Solution:** A single `FileHandler.resolve_path` guard that resolves the filename and
rejects anything landing outside the data directory, with every filename-taking method
routed through it.

**AI Involvement:** Claude found this while working through
`ai_guidance/code_review_checklist.md` on what I had intended as a final status check. It
tested the checklist's red-flag items by running them rather than reasoning about them.

**Lessons Learned:** The bug survived the feature work, 41 CLI tests, and a clean quality
gate, because all of those exercised the application as a cooperative user. None asked
what a hostile input would do. Coverage percentage says nothing about whether you tested
the right things.

## Code Quality Analysis

### Metrics

- Lines of code: 936 application, 1,120 test
- Test coverage: 99% (158 tests)
- Functions/classes: 82 application, 152 test functions
- Linting: `flake8` 0 errors; `mypy` clean across 14 files; `black` and `isort` clean

### Self-Assessment

- **Code Readability: 4** — consistent naming and docstrings. `_dispatch` is the weakest
  point: an if-chain that would read better as a command table.
- **Code Maintainability: 4** — adding a sort, filter, or format is one class and one
  registry entry. Against that, tasks are plain dictionaries, so a key typo escapes `mypy`.
- **Test Quality: 4** — tests target real failure modes rather than lines. I did not write
  them first, and none tested hostile input until final review, which is how a path
  traversal bug survived a 99%-coverage suite.
- **Documentation: 4** — README documents every feature with examples; the log records
  rejected suggestions. The rationale could be stronger on what I chose not to build.

## Learning Outcomes

### Technical Skills Developed

Building three patterns into one application exposed where each stops being useful. I had
not used `click`, configured `mypy` in strict mode, or tested an interactive loop through a
runner — the last was easier than expected and the highest-value testing work here.

### AI Collaboration Skills

The best prompts requested failure modes, not code: "what could go wrong with this file on
disk" produced better error handling than "handle errors properly". Reviewing for "what
would a user expect when this input is weird?" found every real bug; reviewing for "is this
the right pattern?" found none.

### Software Engineering Insights

Design patterns are about where knowledge lives. Undo needed the Command pattern because
each operation must know how to reverse itself. Each pattern here earned its place by
answering "where should this knowledge live?" — a more useful test than matching a problem
to a catalogue.

## Reflection

### What Worked Well

Configuring the toolchain first made every subsequent diff reviewable and caught a real
starter bug. Writing the AI log during the work captured rejected suggestions and reasoning
I could not have reconstructed later. I am most satisfied that undoing a deletion restores
the task to its original position — a small detail easy to accept as-is.

### What Could Be Improved

Writing tests first would have caught the CSV bug before it was committed. Tasks should be
a typed object rather than a dictionary. `_dispatch` should be a command table.

### Future Enhancements

Persisting the undo history so undo works across invocations, making the subcommand
interface feature-complete. Due dates and tags. A richer query syntax. None were in scope,
and I left them out rather than expanding past what was asked.

## Conclusion

I expected the main lesson to be about speed. It was instead about the shape of AI
unreliability. Claude produced well-organised, idiomatic, type-annotated code quickly. What
it did not reliably produce was correct behaviour at the boundaries, and those failures
were invisible to code review because the code looked right. Tests found them; reading did
not.

I will keep testing as the primary review mechanism for generated code, keep enumerating
edge cases deliberately rather than incidentally, and keep asking for failure modes before
implementations. And I will keep treating scope as mine to control. The moment I will
remember is the AI telling me my own request was impossible as stated.

## Appendices

### Appendix A: AI Interaction Log

See `docs/ai_edit_log.md` for seven entries. Most significant: the export factory entry
documenting a bug inherited from the course's own patterns guide; the Command pattern entry
covering the undo ordering and redo stack corrections; and the CLI entry where the AI
identified a flaw in my request.

### Appendix B: Code Statistics

- 158 tests passing, 99% coverage (HTML report in `htmlcov/`)
- Per-module: `commands.py`, `exporters.py`, `sorting.py`, `task_manager.py` at 100%;
  `main.py` 99%; `file_handler.py` 95%
- Starter baseline: 15 tests, 88% coverage, 51 `flake8` errors

### Appendix C: Additional Resources

- `docs/design_patterns.md` — pattern reference, and the source of the CSV header bug
- `ai_guidance/code_review_checklist.md` — used for the final review pass
- `docs/project_plan.md` — the plan and the record of what was cut from scope
- Click documentation, particularly `click.testing.CliRunner`
