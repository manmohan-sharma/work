"""
Core interfaces for the vocabulary builder (Part B).

These are the contracts agreed during architectural planning. They are deliberately
minimal (Interface Segregation) and are what the session layer depends on rather
than any concrete implementation (Dependency Inversion), so that scheduling
algorithms and storage backends can be swapped without modifying existing code.

The single most important decision encoded here: SchedulingPolicy is a PURE
function of (state, grade, now). Time enters through an injected Clock and never
through datetime.now(), which is what makes spaced-repetition interval maths
exhaustively testable without patching the system clock.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from enum import IntEnum
from typing import List, Optional, Protocol, runtime_checkable


class VocabError(Exception):
    """Base class for every error raised by the vocabulary builder.

    Lets the CLI boundary distinguish an anticipated failure from an
    unexpected crash with a single except clause.
    """


class DeckValidationError(VocabError):
    """Raised when a card record cannot be parsed into a valid Card.

    Carries the deck name and record index so the CLI can name the offending
    entry rather than reporting a generic parse failure.
    """


class PolicyNotFoundError(VocabError):
    """Raised when a requested scheduling policy name is not registered."""


class StorageError(VocabError):
    """Raised when review state could not be persisted atomically."""


class Grade(IntEnum):
    """Learner's self-assessed recall quality for a single card.

    Ordered so that comparisons express difficulty directly (AGAIN < GOOD).
    Values follow the SM-2 convention: anything below GOOD is a lapse and
    resets the card's interval.
    """

    AGAIN = 0
    HARD = 3
    GOOD = 4
    EASY = 5


class Card(Protocol):
    """Structural contract for a single vocabulary card.

    Implemented in practice by a frozen dataclass. Declared as a Protocol so
    consumers depend on the shape of a card, not on the concrete model module.
    Note that scheduling never inspects these fields — which is precisely why
    richer card types (audio, images) can be added without touching scheduling.

    Attributes:
        card_id: Stable identifier, unique within a deck.
        term: The prompt side of the card.
        definition: The answer side.
        example: Example sentence providing usage context. May be empty.
        tags: Labels used for filtering and per-topic statistics.
    """

    card_id: str
    term: str
    definition: str
    example: str
    tags: List[str]


class ReviewState(Protocol):
    """Structural contract for a card's spaced-repetition state.

    Kept separate from Card because the two have different lifetimes: card
    content is authored once and rarely edited, while review state changes on
    every single review. Separating them is what allows deck content to be
    edited in a text editor without disturbing a learner's progress.

    Attributes:
        card_id: Identifies the card this state belongs to.
        due_at: When the card next becomes eligible for review.
        interval_days: Current spacing interval; 0 for a card never reviewed.
        ease_factor: Multiplier applied to the interval on a successful review.
        repetitions: Count of consecutive successful reviews; resets on a lapse.
        last_reviewed_at: When the card was last graded; None if never reviewed.
    """

    card_id: str
    due_at: datetime
    interval_days: int
    ease_factor: float
    repetitions: int
    last_reviewed_at: Optional[datetime]


class Deck(Protocol):
    """Structural contract for a named collection of cards and their state.

    Pairs content with progress at load time so that the session layer receives
    one coherent object rather than having to join two sources itself.
    """

    name: str
    cards: List[Card]
    states: List[ReviewState]


class Clock(Protocol):
    """Supplies the current time.

    Injected everywhere rather than calling datetime.now() directly, so that
    scheduling behaviour is deterministic and directly assertable. A test
    implementation returning a fixed datetime is three lines, which is what
    keeps the scheduling test suite free of mocking frameworks.
    """

    def now(self) -> datetime:
        """Return the current time as a timezone-aware datetime."""
        ...


class SchedulingPolicy(ABC):
    """Strategy computing when a card should next be reviewed.

    This is the system's primary extension point: a new algorithm (SM-2,
    Leitner, fixed interval) is one new subclass plus a registry entry,
    satisfying the Open/Closed Principle.

    Implementations MUST be pure: no I/O, no clock access, no mutation of the
    input state. All time enters through the ``now`` argument. This constraint
    is what makes interval maths exhaustively testable — every edge case (first
    review, perfect streak, lapse, ease-factor floor, maximum interval) is
    reachable by passing values, with no fixtures and no patching.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Policy identifier used on the command line, e.g. ``"sm2"``."""
        ...

    @abstractmethod
    def next_state(self, state: ReviewState, grade: Grade,
                   now: datetime) -> ReviewState:
        """Return a NEW review state with the next due date applied.

        Args:
            state: The card's state before this review. Must not be mutated.
            grade: The learner's self-assessed recall quality.
            now: The moment of review, supplied by the caller's Clock.

        Returns:
            A new ReviewState with due_at, interval_days, ease_factor,
            repetitions, and last_reviewed_at updated.

        Raises:
            Nothing. A never-reviewed card (interval_days == 0) is valid input,
            as is a lapse from any interval.
        """
        ...


class PolicyRegistry(Protocol):
    """Interface for looking up scheduling policies by name.

    The single component that must change when an algorithm is added, and the
    seam at which explicit registration could later become plugin discovery.
    """

    def available_policies(self) -> List[str]:
        """Return registered policy names, for CLI help and error messages."""
        ...

    def create(self, policy_name: str) -> SchedulingPolicy:
        """Instantiate the policy registered under ``policy_name``.

        Raises:
            PolicyNotFoundError: If no policy is registered under that name.
        """
        ...


class CardRepository(ABC):
    """Loads decks and persists updated review state.

    Implementations own all format knowledge, so adding SQLite means adding an
    implementation here and changing nothing else.

    Writes MUST be atomic — temp file plus rename, or an equivalent. An
    interrupted save must leave the previous state intact rather than
    truncated; a learner losing months of progress to a mistimed Ctrl-C is the
    one failure this application cannot recover from.
    """

    @abstractmethod
    def load_deck(self, deck_name: str) -> Deck:
        """Load a deck with its cards and current review state.

        Args:
            deck_name: Identifier of the deck to load.

        Returns:
            The deck with one ReviewState per card. Cards never reviewed
            receive a default state rather than being omitted.

        Raises:
            FileNotFoundError: If the deck does not exist.
            DeckValidationError: If a card record is malformed.
        """
        ...

    @abstractmethod
    def save_states(self, deck_name: str, states: List[ReviewState]) -> None:
        """Atomically persist updated review state for a deck.

        Args:
            deck_name: Deck whose progress is being saved.
            states: Complete set of states for the deck, not a partial update.

        Raises:
            StorageError: If the write could not be completed atomically.
        """
        ...


class ReviewLog(Protocol):
    """Append-only record of every review that has taken place.

    Deliberately write-only on the session path: current state remains the
    source of truth for scheduling, so nothing needs to fold this log to decide
    what is due. It exists to feed statistics without pushing history into the
    card model, and to preserve enough information to re-derive schedules if
    the learner later switches algorithms.
    """

    def append(self, card_id: str, grade: Grade, reviewed_at: datetime) -> None:
        """Record one review. Must not raise on a full disk in a way that
        aborts the session — a lost log line is recoverable, a lost session is
        not.
        """
        ...


class SessionQueueBuilder(ABC):
    """Selects and orders the cards that make up a review session.

    Held separate from SchedulingPolicy on purpose. Scheduling answers "when
    does this card come back"; selection answers "what am I reviewing now, and
    in what order". Merging them is the most common structural mistake in
    flashcard code, and it is what makes new-card mixing and daily caps
    impossible to change without touching the algorithm.
    """

    @abstractmethod
    def build(self, deck: Deck, now: datetime,
              max_cards: int, max_new: int) -> List[Card]:
        """Return the ordered cards to review in this session.

        Args:
            deck: Deck to draw from.
            now: Current time, supplied by the caller's Clock.
            max_cards: Upper bound on total session length.
            max_new: Upper bound on previously unseen cards included.

        Returns:
            Cards in presentation order. An empty list is a valid result
            meaning nothing is due — never an error.
        """
        ...


@runtime_checkable
class SessionPresenter(Protocol):
    """Presents cards to the learner and collects their self-graded recall.

    The only interface that performs user I/O, which is what allows the entire
    session workflow to be tested with a scripted fake and no terminal.
    Swapping this out is also how a TUI or web front end would attach.
    """

    def show_card(self, card: Card) -> None:
        """Display the prompt side of a card and wait for the learner."""
        ...

    def collect_grade(self, card: Card) -> Grade:
        """Reveal the answer and return the learner's recall grade.

        Raises:
            KeyboardInterrupt: If the learner ends the session early. The
                session layer must treat this as a normal exit and persist
                progress made so far.
        """
        ...

    def show_summary(self, reviewed: int, correct: int) -> None:
        """Display end-of-session results."""
        ...
