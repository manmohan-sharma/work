# Architecture Plan: CLI Expense Tracker

## 1. Alternatives Considered

Three distinct approaches were explored before committing to a design.

### Alternative A — Layered modules with conditional dispatch

Three flat modules: `loader.py` loads CSV, `reports.py` holds one function per report
type selected by an `if/elif` chain on a mode string, `display.py` prints results.

- **Pros**: Smallest amount of code; no indirection; a new reader understands it in
  five minutes; zero abstraction overhead.
- **Cons**: Every new report type means editing the existing `reports.py` dispatch —
  a direct violation of the Open/Closed Principle, which the requirements call out
  explicitly. The dispatch function grows without bound and becomes a merge-conflict
  magnet. Report logic and mode selection are tangled, so testing one report means
  routing through the dispatcher.

### Alternative B — Strategy pattern with a report registry

Each report type is a class implementing a shared `ReportMode` interface. A registry
maps mode names to strategy classes; a factory reads the registry to instantiate the
requested strategy. A `ReportEngine` orchestrates loader → strategy → formatter,
receiving all three as injected abstractions.

- **Pros**: Adding a report type means adding one new file and registering it — no
  existing module changes (satisfies OCP). Each strategy is a pure
  `transactions -> report data` transform, so unit tests need no mocking at all.
  Dependency injection at the engine boundary makes the whole workflow testable with
  in-memory fakes. Every module stays well under the 200-line limit.
- **Cons**: More files and one more layer of indirection than Alternative A. The
  registry is a small piece of shared mutable state that must be imported for its
  side effects, which can surprise newcomers.

### Alternative C — Plugin pipeline with runtime discovery

Report modes discovered at runtime by scanning a `plugins/` directory with
`importlib`, combined with a composable transform pipeline (filter → aggregate →
format) where each stage is independently pluggable.

- **Pros**: Maximum extensibility — third parties can add reports without touching
  the source tree. The pipeline stages compose, so "monthly totals for one category"
  needs no new report class at all.
- **Cons**: Substantial complexity for a single-user CLI. Dynamic import introduces a
  failure mode (a malformed plugin) that is genuinely awkward to test and to report
  clearly to the user. The pipeline abstraction is speculative: nothing in the
  requirements needs stage composition today. This is the over-engineering trap the
  exercise warns about.

---

## 2. Trade-off Analysis

| Criterion | A: Conditional | B: Strategy + registry | C: Plugin pipeline |
| --- | --- | --- | --- |
| Cost to add a report type | Modify existing module | Add one file | Drop a file in a folder |
| Open/Closed compliance | Violated | Satisfied | Satisfied |
| Testability | Report logic reachable only via dispatcher | Each strategy tested standalone, no mocks | Discovery layer needs mocking |
| Implementation complexity | Lowest | Moderate | High |
| Failure surface | Small | Small | Dynamic import errors |
| Fit to stated requirements | Fails extensibility requirement | Meets all | Exceeds; buys unneeded capability |

The decisive question is what the requirements actually ask for. Extensibility for new
report modes is a stated requirement *now*; a plugin architecture for third-party
report types is listed as a *future* concern. That asymmetry rules A out (it cannot
meet a current requirement) and argues against C (it pays today for a future need
while adding a failure mode that is hard to surface well in a terminal).

---

## 3. Selected Architecture

**Selected: Alternative B — Strategy pattern with a report registry.**

Rationale:

1. It is the simplest design that satisfies every stated requirement, including the
   explicit call for Strategy and for adding report modes without modifying existing
   code.
2. It maximises testability. Strategies are pure transforms over a list of
   transactions, so the bulk of the test suite requires no mocking, no filesystem, and
   no captured stdout.
3. It preserves the option to become Alternative C later. Only one function — the one
   that populates the registry — would need to change to switch from explicit
   registration to runtime discovery. The strategy interface, engine, and formatters
   are unaffected. Deferring C therefore costs nothing beyond a small later refactor.

I did not simply take the recommendation at face value: Alternative C was the more
"impressive" architecture and would have been easy to justify on extensibility
grounds. It was rejected because the extensibility it adds is speculative, while the
complexity and the new error-handling burden are immediate.

---

## 4. Module Design

Each module has a single responsibility and depends on abstractions rather than
concrete classes.

| Module | Responsibility |
| --- | --- |
| `utils/models.py` | Defines the `Transaction` data model and the report data structure. Owns no behaviour beyond construction and validation of a single record. |
| `utils/errors.py` | Defines the exception hierarchy (`ExpenseTrackerError`, `TransactionValidationError`, `ReportModeNotFoundError`) so callers can handle failures by category. |
| `utils/transaction_loader.py` | Responsible for reading a CSV file and converting rows into validated `Transaction` objects. Handles missing files, malformed rows, and bad dates or amounts. Knows nothing about reports. |
| `utils/report_modes.py` | Contains the concrete `ReportMode` strategies (`CategorySummaryReport`, `MonthlyTotalsReport`). Each one processes a list of transactions into report data and nothing else. |
| `utils/report_registry.py` | Maps mode names to strategy classes and constructs the requested strategy. Responsible for the one piece of knowledge that must change when a report type is added. |
| `utils/report_engine.py` | Orchestrates the workflow: ask the loader for transactions, ask the registry for a strategy, run it, hand the result to the formatter. Holds no report logic of its own. |
| `utils/cli_interface.py` | Manages argument parsing, terminal output, and turning exceptions into readable messages. The only module that performs I/O to the user. |
| `main.py` | Entry point. Wires concrete implementations together and delegates to the CLI interface. This is the only place where concrete classes are chosen. |

### Dependency direction

```
main.py
  │  (constructs concrete implementations, injects them)
  ▼
cli_interface ──▶ report_engine ──▶ interfaces (ReportMode, TransactionLoader)
                       │                  ▲            ▲
                       │                  │            │
                       └── report_registry┘            │
                                  │                    │
                        report_modes ─────────────────┘
                        transaction_loader ───────────┘
                                  │
                              models, errors
```

All arrows point toward abstractions or toward leaf data modules. `report_engine`
depends on the `ReportMode` and `TransactionLoader` interfaces, never on
`report_modes` or `transaction_loader` directly — that dependency is supplied by
`main.py`. There are no cycles: `models` and `errors` import nothing from the package,
and nothing imports `main`.

### How this applies SOLID

- **Single Responsibility**: each module in the table above has exactly one reason to
  change — a CSV format change touches only the loader, a display change only the
  formatter.
- **Open/Closed**: a new report type is a new class plus a registry entry. No existing
  module is modified.
- **Liskov Substitution**: every `ReportMode` accepts the same input type and returns
  the same report structure, so the engine can hold any strategy interchangeably.
- **Interface Segregation**: `ReportMode` declares two members (`name` and
  `process_transactions`); `TransactionLoader` declares one. Neither forces an
  implementer to provide methods it does not use.
- **Dependency Inversion**: `ReportEngine` depends on the `TransactionLoader` and
  `ReportMode` abstractions. Concrete choices are made once, in `main.py`.

---

## 5. Extension Strategy

**Adding a new report mode** (for example, "top merchants"):

1. Add a `TopMerchantsReport` class to `utils/report_modes.py` — or its own module —
   implementing `process_transactions`.
2. Register it in `utils/report_registry.py`.
3. Add `tests/test_report_modes.py::test_top_merchants`.

No existing module is edited. This is the extensibility the design exists to provide.

**Supporting a new data format** (JSON, OFX): write a `JsonTransactionLoader`
satisfying the `TransactionLoader` interface and select it in `main.py` based on the
file extension. The engine, strategies, and formatters are untouched because they
depend on the interface, not the CSV implementation.

**Changing output formatting** (CSV export, JSON output): add a formatter satisfying
the `ReportFormatter` interface and inject it. Report logic is unaffected because
strategies return structured data, never formatted strings.

**Future plugin architecture**: replace the explicit dictionary in
`report_registry.py` with runtime discovery. Only that module changes — this is the
deliberate upgrade path to Alternative C described above.

---

## 6. Implementation Roadmap

Ordered so that each phase is independently testable and nothing is built before what
it depends on.

1. **Foundations** — `models.py`, `errors.py`, `interfaces.py`. No dependencies; makes
   every later phase type-checkable.
2. **Data loading** — `transaction_loader.py` plus its tests, including malformed
   rows, missing files, and bad amounts. Delivers the first end-to-end-verifiable
   capability.
3. **First strategy** — `report_modes.py` with `CategorySummaryReport` only, tested
   against in-memory transaction lists. Proves the interface is workable before a
   second implementation locks it in.
4. **Orchestration** — `report_registry.py` and `report_engine.py`, tested with fake
   loaders and fake strategies to confirm the injection seams work.
5. **Second strategy** — `MonthlyTotalsReport`. Its real purpose here is to validate
   the Open/Closed claim: if this step requires editing anything from phase 3 or 4,
   the abstraction was wrong and should be revised now rather than later.
6. **Presentation** — `cli_interface.py` and `main.py`, with argument parsing and
   error-message formatting.
7. **Hardening** — integration tests over the full workflow, sample CSV fixtures, and
   the user-facing README.

Phases 1–5 require no terminal I/O at all, which keeps the majority of the test suite
fast and mock-free.
