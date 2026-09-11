# Project Plan: Vocabulary Builder with Spaced Repetition

Part B of Concept 1 — applying the Part A planning methodology to a new domain.

Companion deliverables: `myproject_interfaces.py`, `myproject_structure.txt`.

---

## 1. Project Vision

**What I'm building**: a command-line vocabulary trainer that schedules review sessions
using spaced repetition, so a learner reviews each word at the moment they are about to
forget it rather than on a fixed calendar.

**Why**: flashcard apps that quiz every card every session waste most of the learner's
time on words they already know. Spaced repetition solves this, but the good
implementations are web services that own your data. A local CLI over plain files keeps
the learner's decks portable and reviewable in a text editor.

**Why this project for this exercise**: it is deliberately *not* shaped like the expense
tracker. The expense tracker is a stateless read-and-report pipeline. This application
mutates and persists state on every interaction, and its core logic is time-dependent.
Those two differences force architectural decisions that the Part A design never had to
make, which is the point of re-applying the methodology rather than renaming it.

**Explicitly out of scope** for v1: audio pronunciation, image cards, multi-user
accounts, sync, and a GUI. Each is a plausible v2, and the architecture below notes
where they would attach.

---

## 2. Requirements Analysis

### Functional requirements

- Load one or more decks of vocabulary cards from local files (term, definition,
  example sentence, tags).
- Track per-card review state: when it was last seen, how well it was recalled, and
  when it is next due.
- Build a review session containing the cards due now, mixing in a bounded number of
  previously unseen cards.
- Present each card, accept a self-graded recall score, and schedule the next review
  from that grade.
- Persist updated state after the session so progress survives a restart — and survives
  a crash mid-session without corrupting the deck.
- Report progress: cards due today, retention rate, review streak, per-deck maturity.
- Handle a missing deck file, a malformed card, and an interrupted session gracefully.

### Technical requirements

- Python 3.8+, standard library only.
- Modular architecture following SOLID principles; each module under 200 lines.
- The scheduling algorithm must be swappable (SM-2, Leitner boxes, fixed interval)
  without modifying session, storage, or presentation code.
- The storage backend must be swappable (JSON now, SQLite later) behind one interface.
- **All time-dependent logic must take an injected clock.** No module may call
  `datetime.now()` directly. This is a hard requirement, not a preference: an algorithm
  whose behaviour depends on the wall clock is untestable without freezing time, and
  discovering that after implementation means rewriting every scheduling module.
- High testability with minimal mocking: the scheduling algorithm must be testable as a
  pure function.

### Quality attributes

| Attribute | Target |
| --- | --- |
| Testability | Scheduling and selection testable with zero I/O and zero mocks |
| Data safety | A crash mid-session must never leave a deck file truncated |
| Extensibility | A new scheduling algorithm is one new file plus one registry line |
| Transparency | Review history is human-readable and inspectable in a text editor |

---

## 3. Architectural Alternatives

The central design question in this domain: **where does "what to review next" live?**
It is tempting to treat that as one responsibility, but it is actually two:

1. **Selection** — which cards belong in today's session, and in what order.
2. **Scheduling** — given a grade for a card, when should that card next appear.

Designs that merge these produce a "Scheduler" that owns queue construction, algorithm
maths, and persistence at once. Each alternative below takes a different position on
that split.

### Alternative A — Card-centric (Active Record)

`Card` objects own their own review state and behaviour: `card.review(grade)` updates
the card's interval in place and `card.save()` writes it back. A `Session` object walks
a list of cards and calls `review()` on each.

- **Pros**: The least code and the most obvious mental model — a card knows about
  itself. Fast to build; no interfaces to design up front.
- **Cons**: `Card` ends up responsible for vocabulary data, scheduling maths, *and*
  persistence — three reasons to change in one class, squarely against SRP. Swapping
  SM-2 for Leitner means editing `Card` itself, violating OCP on the one axis the
  requirements say must be extensible. Worst of all for testability: scheduling cannot
  be tested without constructing a `Card` bound to storage, so the algorithm tests —
  the ones that matter most — become the slowest and most fragile in the suite.

### Alternative B — Layered domain with pure policies and a repository

A domain layer of plain data (`Card`, `ReviewState`, `Grade`) with no behaviour beyond
validation. A `SchedulingPolicy` strategy is a **pure function**
`(ReviewState, Grade, now) -> ReviewState`. A separate `SessionQueueBuilder` handles
selection. A `CardRepository` interface handles persistence. A `ReviewSession`
orchestrates the three, receiving all of them injected.

- **Pros**: Cleanly separates the two responsibilities the domain conflates. The
  scheduling policy is pure and deterministic, so its tests are instant, mock-free, and
  cover edge cases (a lapsed card, a first review, a maximum interval) by simply passing
  values. New algorithms satisfy OCP. Storage is swappable. The injected clock makes
  "this card is due in 6 days" directly assertable.
- **Cons**: More modules and interfaces than A, and the split between selection and
  scheduling has to be explained to a newcomer, because most flashcard code in the wild
  merges them.

### Alternative C — Event-sourced review log

Persist an append-only log of review events (`card_id, timestamp, grade`). A card's
current review state is not stored at all; it is a fold over that card's events, with
the scheduling policy applied at each step.

- **Pros**: Genuinely attractive in *this* domain, more so than the plugin architecture
  was in Part A. Changing the scheduling algorithm can be applied retroactively by
  replaying history under the new policy — a real feature for a learning tool, since a
  learner switching from Leitner to SM-2 otherwise loses their scheduling history. The
  log is a complete audit trail and makes rich analytics (retention curves, per-hour
  accuracy) fall out for free. Append-only writes are inherently crash-safe.
- **Cons**: Every read of "what's due" requires folding the whole history, so snapshot
  caching becomes necessary almost immediately — and a snapshot plus a log is markedly
  more machinery than a single-user CLI warrants. Storage grows without bound. The
  invalidation rule for snapshots is exactly the kind of subtle bug that is expensive to
  find.

### Trade-off summary

| Criterion | A: Active Record | B: Layered + pure policy | C: Event-sourced |
| --- | --- | --- | --- |
| Swap scheduling algorithm | Edit `Card` (violates OCP) | Add one file | Add one file |
| Test the interval maths | Needs storage-bound object | Pure function, no mocks | Pure, but fold adds setup |
| Retroactive algorithm change | Impossible | Possible via log (see below) | Native |
| Crash safety | Manual | Atomic write required | Inherent (append-only) |
| Read path cost | Trivial | Trivial | Fold or snapshot cache |
| Complexity | Lowest | Moderate | High |

---

## 4. Selected Architecture

**Selected: Alternative B, with one idea borrowed from C.**

Alternative B is the base: pure scheduling policies, explicit selection, repository
persistence, injected clock.

The borrowed idea: **also append every review to a plain-text review log**, while
keeping current state stored directly. The log is not the source of truth for
scheduling — current state is — so no fold is needed on the read path and there are no
snapshots to invalidate. But the log still delivers C's two real benefits: it feeds the
statistics module without polluting the card model with history, and it preserves enough
information to re-derive schedules later if the learner switches algorithms.

**Why not pure C**: the cost is concentrated in the read path (fold-per-read, snapshot
caching) while the benefit is concentrated in analytics and retroactive replay. Writing
the log without reading from it captures the benefit and skips the cost. If retroactive
replay ever becomes a real feature rather than a nice property, the log already contains
what that migration needs — a deliberate, cheap option on a future capability.

**Why not A**: it fails a stated requirement. Swappable scheduling algorithms are
required now, and A cannot provide them without editing `Card` on every change.

**Where I disagree with the obvious answer**: the conventional advice would be "you're
building a CLI flashcard app, just let the Card object schedule itself." I rejected that
specifically because of testability. Spaced repetition logic is where the bugs live — an
off-by-one in an interval calculation is invisible in manual testing and silently
degrades the learner's schedule for months. That logic deserves to be pure, isolated,
and exhaustively tested, which means it cannot live inside an object bound to storage.

### How this applies SOLID

- **Single Responsibility**: `SchedulingPolicy` computes intervals; `SessionQueueBuilder`
  chooses cards; `CardRepository` persists. Three reasons to change, three modules.
- **Open/Closed**: a new algorithm is a new `SchedulingPolicy` subclass plus a registry
  entry. Nothing existing is edited.
- **Liskov Substitution**: every policy accepts a `ReviewState` and returns a
  `ReviewState`, so the session holds any of them interchangeably.
- **Interface Segregation**: `Clock` declares one member. `SchedulingPolicy` declares
  two. A test fake for either is three lines.
- **Dependency Inversion**: `ReviewSession` depends on the policy, repository, clock,
  and presenter abstractions. Concrete choices happen once, in `main.py`.

---

## 5. Module Design

Full interface code is in `myproject_interfaces.py`; the directory layout is in
`myproject_structure.txt`.

| Module | Responsibility |
| --- | --- |
| `domain/models.py` | `Card`, `ReviewState`, `Grade` enum, `ReviewEvent`, `Deck`. Immutable data with construction-time validation; no behaviour, no I/O. |
| `domain/errors.py` | Exception hierarchy: `VocabError`, `DeckValidationError`, `PolicyNotFoundError`, `StorageError`. |
| `interfaces.py` | The shared contracts. The only module every layer may import. |
| `scheduling/sm2.py` | SM-2 policy: ease factor and interval maths. Pure. |
| `scheduling/leitner.py` | Leitner box policy. Pure. |
| `scheduling/registry.py` | Maps policy names to classes. The single extension seam. |
| `session/queue_builder.py` | Selection: filters cards due at `now`, orders them, caps new-card intake. Pure given a clock reading. |
| `session/review_session.py` | Orchestration: pull from queue, present, grade, apply policy, record event. Holds no scheduling maths. |
| `storage/json_repository.py` | `CardRepository` over JSON files. Owns atomic writes (temp file + rename). |
| `storage/review_log.py` | Appends `ReviewEvent` records to the review log. Append-only, never read on the session path. |
| `stats/stats_reporter.py` | Reads the review log and produces progress metrics. The only consumer of history. |
| `presentation/cli_presenter.py` | Terminal prompts, card display, grade input parsing. The only module doing user I/O. |
| `main.py` | Composition root: parses arguments, constructs concretes, injects, runs. |

### Dependency direction

```
main.py  (composition root: chooses concretes, injects them)
   │
   ▼
cli_presenter ──▶ review_session ──▶ interfaces (SchedulingPolicy, CardRepository,
                       │                         Clock, SessionPresenter)
                       │                    ▲         ▲          ▲
        queue_builder ─┤                    │         │          │
        policy registry┘                    │         │          │
                       │                    │         │          │
          scheduling/* ┴────────────────────┘         │          │
             storage/* ──────────────────────────────-┘          │
        stats_reporter ─────────────────────────────────────────-┘
                       │
                 domain/models, domain/errors
```

No cycles: `domain/*` imports nothing from the package, every arrow points at an
abstraction or a leaf, and nothing imports `main`.

### Extension points

- **New scheduling algorithm** → one file in `scheduling/` + one registry line.
- **SQLite storage** → one `CardRepository` implementation; nothing else changes.
- **Audio or image cards** → extend `Card` and `SessionPresenter`; scheduling untouched,
  because scheduling never inspects card content.
- **Web or TUI front end** → a new `SessionPresenter`; the session loop is unchanged.
- **Retroactive algorithm migration** → replay `review_log` under a new policy. The data
  is already being captured for exactly this.

---

## 6. Implementation Roadmap

Ordered so each phase is independently testable and nothing is built before its
dependencies.

1. **Foundations** — `domain/models.py`, `domain/errors.py`, `interfaces.py`, and a
   `SystemClock` plus a `FrozenClock` test double. The clock double comes first
   deliberately; every later phase depends on being able to control time.
2. **Scheduling policy** — SM-2 only, with exhaustive unit tests: first review, a
   perfect streak, a lapse, ease-factor floor, maximum interval. Pure functions, so this
   is the fastest and most valuable test file in the project. Built first because it is
   where correctness bugs hide.
3. **Storage** — `json_repository.py` with atomic writes, plus a test that a simulated
   crash mid-write leaves the original file intact.
4. **Selection** — `queue_builder.py` against in-memory card lists and a frozen clock:
   due cards only, ordering, new-card cap, empty-queue case.
5. **Session orchestration** — `review_session.py` wired with a fake presenter, fake
   repository, and frozen clock. No terminal involved, so the core workflow is fully
   tested before any UI exists.
6. **Second policy** — Leitner. Its real purpose is to validate the Open/Closed claim:
   if adding it requires touching phase 2, 4, or 5, the abstraction is wrong and should
   be fixed now rather than after a third algorithm exists.
7. **Presentation** — `cli_presenter.py` and `main.py`: argument parsing, card display,
   grade input, error messages.
8. **Statistics and hardening** — `review_log.py`, `stats_reporter.py`, integration
   tests over a full session, sample decks, and the user-facing README.

Phases 1–6 involve no terminal I/O at all, which keeps the majority of the suite fast
and mock-free — the same property that made the Part A design testable, achieved here
despite the application being stateful and time-dependent.

---

## Appendix: Adapted Prompt

The Part A template required four substantive changes, not just renaming the domain.
The changes are marked ★.

```xml
<role>Senior Python architect with expertise in SOLID principles and design patterns</role>

<task>
Evaluate and compare 2-3 architectural approaches for a CLI spaced-repetition
vocabulary trainer
</task>

<context>
<application_type>Command-line vocabulary trainer with spaced repetition</application_type>
<tech_stack>Python 3.8+, local file storage, terminal interface</tech_stack>

<!-- ★ CHANGE 1: one-shot pipeline becomes a stateful interactive loop -->
<user_workflow>
Load deck → build session of due cards → for each card: present, grade,
reschedule → persist updated state → show session summary
</user_workflow>

<!-- ★ CHANGE 2: records are MUTABLE and written back, unlike transactions -->
<data_structure>
Cards with term, definition, example, tags — each carrying mutable review state
(interval, ease factor, due date, repetition count) that the application updates
and persists on every review.
</data_structure>
</context>

<requirements>
<functional_requirements>
- Load decks from local files with validation
- Select cards due for review, mixing in a bounded number of new cards
- Present cards, accept self-graded recall, reschedule accordingly
- Persist progress durably across sessions
- Report retention rate, streak, and cards due
</functional_requirements>

<!-- ★ CHANGE 3: new section with no Part A equivalent -->
<temporal_requirements>
- All scheduling logic is time-dependent and MUST take an injected clock
- No module may call datetime.now() directly
- Scheduling must be deterministic and assertable under a frozen clock
</temporal_requirements>

<extensibility_requirements>
- Swap the scheduling algorithm (SM-2, Leitner, fixed) without touching
  session, storage, or presentation code
- Swap the storage backend (JSON now, SQLite later) behind one interface
- Support richer card types (audio, images) without changing scheduling
</extensibility_requirements>

<quality_attributes>
- Scheduling algorithm testable as a pure function, zero mocks
- Crash mid-session must not corrupt a deck file
- Clear separation: domain, scheduling, selection, storage, presentation
</quality_attributes>
</requirements>

<constraints>
<architecture_principles>Follow SOLID principles explicitly</architecture_principles>
<complexity_limits>Each module under 200 lines, single responsibility</complexity_limits>
<dependencies>Standard library only</dependencies>

<!-- ★ CHANGE 4: Strategy now applies to the ALGORITHM, not the report type -->
<design_patterns>
Strategy for the scheduling algorithm; Repository for persistence;
dependency injection at the session boundary
</design_patterns>
</constraints>

<deliverables>
- 2-3 distinct architectural approaches with trade-offs
- An explicit position on where "what to review next" logic belongs
- Module responsibilities and interfaces
- Extension points for new algorithms and storage backends
- Recommendation with justification
</deliverables>
```

**The most useful addition was `<temporal_requirements>`.** Without it, a generated
design will call `datetime.now()` inside the scheduling code, and every test of interval
maths then needs to patch the system clock. Naming the constraint in the prompt is
cheaper than discovering it during implementation.
