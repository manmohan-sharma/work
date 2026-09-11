"""
Quiz ordering strategies (Strategy pattern).

A mode answers two questions and nothing else: in what order are cards asked,
and does a missed card come back? Keeping those two decisions here — out of
``quiz_engine`` — is what makes a new mode a new class plus one registry entry,
with no change to the engine that runs it (Open/Closed Principle).

Modes never touch input or output, and ``RandomMode`` takes its randomness
through the constructor. Between them, those two rules mean every mode's
behaviour is assertable exactly, with no monkeypatching of ``random`` and no
captured stdout.

Available modes:
    sequential  Author order, one pass. Best for learning new material in the
                order it was written.
    random      Shuffled, one pass. Stops the learner memorising positions
                instead of content.
    adaptive    Easiest first, and missed cards come back. Spends the session's
                time on the material that is not yet known.

Example:
    >>> cards = [{'question': 'Q1', 'answer': 'A1'},
    ...          {'question': 'Q2', 'answer': 'A2'}]
    >>> mode = create_quiz_mode('sequential')
    >>> [card['question'] for card in mode.build_queue(cards)]
    ['Q1', 'Q2']
    >>> mode.should_repeat(cards[0], was_correct=False)
    False
"""
from abc import ABC, abstractmethod
import random
from typing import Any, Dict, List, Optional

from exceptions import QuizModeNotFoundError

DEFAULT_DIFFICULTY = 'medium'
DIFFICULTY_ORDER: Dict[str, int] = {'easy': 0, 'medium': 1, 'hard': 2}


class QuizMode(ABC):
    """Interface for a quiz ordering strategy.

    Implementations decide presentation order and whether missed cards are
    re-asked. They receive plain flashcard dicts and must not modify them.
    """

    @abstractmethod
    def get_mode_name(self) -> str:
        """Return the name this mode is selected by on the command line."""

    @abstractmethod
    def build_queue(self, flashcards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return the cards to ask, in presentation order.

        Args:
            flashcards: Validated flashcards to draw from. Must not be modified;
                implementations return a new list.

        Returns:
            Cards in the order they should be asked. An empty input yields an
            empty queue, which is valid — the engine decides what to do about it.
        """

    def should_repeat(self, flashcard: Dict[str, Any], was_correct: bool) -> bool:
        """Whether a just-answered card should be asked again later.

        Defaults to False, so a one-pass mode needs no implementation. Modes
        that repeat cards override this.

        Args:
            flashcard: The card that was just answered.
            was_correct: Whether the learner's answer was accepted.

        Returns:
            True to append the card to the end of the queue.
        """
        return False

    def reset(self) -> None:
        """Discard any per-session state.

        A no-op for stateless modes. Called by the engine when a quiz starts, so
        that reusing a mode instance for a second quiz cannot inherit counters
        from the first.
        """


class SequentialMode(QuizMode):
    """Asks every card once, in the order it appears in the deck.

    The predictable baseline: useful when the deck is deliberately ordered (a
    lesson, a chapter) and for reproducing a reported problem, since the card
    order is fixed.

    Example:
        >>> cards = [{'question': 'Q1', 'answer': 'A1'},
        ...          {'question': 'Q2', 'answer': 'A2'}]
        >>> SequentialMode().build_queue(cards) == cards
        True
    """

    MODE_NAME = 'sequential'

    def get_mode_name(self) -> str:
        """Return ``"sequential"``."""
        return self.MODE_NAME

    def build_queue(self, flashcards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return a copy of the deck in its original order.

        Args:
            flashcards: Validated flashcards to draw from.

        Returns:
            A new list with the same cards in the same order.
        """
        return list(flashcards)


class RandomMode(QuizMode):
    """Asks every card once, in shuffled order.

    Prevents the learner from memorising the deck's sequence rather than its
    content — a real effect on any deck reviewed more than a few times.

    The random source is injected so tests can pin the order. Passing
    ``random.Random(seed)`` also makes a session reproducible for bug reports.

    Example:
        >>> import random
        >>> cards = [{'question': str(n), 'answer': str(n)} for n in range(5)]
        >>> mode = RandomMode(rng=random.Random(1))
        >>> shuffled = [card['question'] for card in mode.build_queue(cards)]
        >>> sorted(shuffled) == ['0', '1', '2', '3', '4']
        True
    """

    MODE_NAME = 'random'

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        """Store the random source used for shuffling.

        Args:
            rng: Random source. Defaults to a fresh ``random.Random()``, seeded
                by the system, rather than the global ``random`` module — a mode
                instance should not be affected by unrelated calls to
                ``random.seed`` elsewhere in the process.
        """
        self._rng = rng if rng is not None else random.Random()

    def get_mode_name(self) -> str:
        """Return ``"random"``."""
        return self.MODE_NAME

    def build_queue(self, flashcards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return the deck's cards in shuffled order.

        Args:
            flashcards: Validated flashcards to draw from.

        Returns:
            A new shuffled list containing every input card exactly once.
        """
        queue = list(flashcards)
        self._rng.shuffle(queue)
        return queue


class AdaptiveMode(QuizMode):
    """Asks easiest cards first and brings missed cards back.

    Concentrates the session on material the learner has not mastered, which is
    the whole reason to prefer it over a straight pass. Cards with no
    ``difficulty`` are treated as ``medium`` so a partially annotated deck still
    orders sensibly, and ties keep author order (``sorted`` is stable) so the
    mode stays deterministic and testable.

    Unlike the other modes this one is stateful: it counts how often each card
    has been repeated so a card the learner keeps missing cannot loop forever.
    ``reset`` clears those counters, and the engine calls it at the start of
    every quiz.

    Example:
        >>> cards = [{'question': 'hard one', 'answer': 'A', 'difficulty': 'hard'},
        ...          {'question': 'easy one', 'answer': 'B', 'difficulty': 'easy'}]
        >>> mode = AdaptiveMode(max_repeats=1)
        >>> [card['question'] for card in mode.build_queue(cards)]
        ['easy one', 'hard one']
        >>> mode.should_repeat(cards[0], was_correct=False)
        True
        >>> mode.should_repeat(cards[0], was_correct=False)  # limit reached
        False
    """

    MODE_NAME = 'adaptive'
    DEFAULT_MAX_REPEATS = 2

    def __init__(self, max_repeats: int = DEFAULT_MAX_REPEATS) -> None:
        """Configure how often a single card may be re-asked.

        Args:
            max_repeats: Maximum extra appearances per card. 0 disables
                repeating and makes this a difficulty-ordered single pass.

        Raises:
            ValueError: If ``max_repeats`` is negative, which would otherwise
                silently behave like 0 and hide the caller's mistake.
        """
        if max_repeats < 0:
            raise ValueError(f"max_repeats must be >= 0, got {max_repeats}")
        self._max_repeats = max_repeats
        self._repeat_counts: Dict[int, int] = {}

    def get_mode_name(self) -> str:
        """Return ``"adaptive"``."""
        return self.MODE_NAME

    def build_queue(self, flashcards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return the deck ordered easy, then medium, then hard.

        Args:
            flashcards: Validated flashcards to draw from.

        Returns:
            A new list ordered by difficulty, preserving author order within
            each difficulty band.
        """
        return sorted(flashcards, key=self._difficulty_rank)

    def should_repeat(self, flashcard: Dict[str, Any], was_correct: bool) -> bool:
        """Re-ask a missed card until its repeat budget is spent.

        Args:
            flashcard: The card that was just answered.
            was_correct: Whether the learner's answer was accepted.

        Returns:
            True if the answer was wrong and this card has not yet been repeated
            ``max_repeats`` times.
        """
        if was_correct:
            return False

        # Identity, not content: two cards may legitimately share a question,
        # and dicts are unhashable so they cannot be used as keys directly.
        card_key = id(flashcard)
        if self._repeat_counts.get(card_key, 0) >= self._max_repeats:
            return False

        self._repeat_counts[card_key] = self._repeat_counts.get(card_key, 0) + 1
        return True

    def reset(self) -> None:
        """Clear the per-card repeat counters."""
        self._repeat_counts.clear()

    @staticmethod
    def _difficulty_rank(flashcard: Dict[str, Any]) -> int:
        """Return a sort rank for a card's difficulty.

        Args:
            flashcard: Card whose difficulty is being ranked.

        Returns:
            0 for easy, 1 for medium or unspecified, 2 for hard.
        """
        difficulty = flashcard.get('difficulty') or DEFAULT_DIFFICULTY
        return DIFFICULTY_ORDER.get(
            str(difficulty).strip().lower(), DIFFICULTY_ORDER[DEFAULT_DIFFICULTY]
        )


# The extension seam: a new mode is a new class above plus one entry here.
# Nothing else in the application needs to change.
MODE_REGISTRY = {
    SequentialMode.MODE_NAME: SequentialMode,
    RandomMode.MODE_NAME: RandomMode,
    AdaptiveMode.MODE_NAME: AdaptiveMode,
}


def available_modes() -> List[str]:
    """Return the registered mode names, sorted for stable CLI help text."""
    return sorted(MODE_REGISTRY)


def create_quiz_mode(mode_name: str) -> QuizMode:
    """Instantiate the quiz mode registered under ``mode_name``.

    Args:
        mode_name: Mode name, matched case-insensitively.

    Returns:
        A new mode instance with default configuration.

    Raises:
        QuizModeNotFoundError: If no mode is registered under that name. The
            message lists what is available.

    Example:
        >>> create_quiz_mode('ADAPTIVE').get_mode_name()
        'adaptive'
        >>> create_quiz_mode('psychic')
        Traceback (most recent call last):
            ...
        exceptions.QuizModeNotFoundError: Unknown quiz mode 'psychic'. Available modes: adaptive, random, sequential
    """
    try:
        mode_class = MODE_REGISTRY[mode_name.strip().lower()]
    except KeyError:
        raise QuizModeNotFoundError(mode_name, available_modes()) from None
    return mode_class()
