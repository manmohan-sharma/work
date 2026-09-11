"""
Quiz orchestration: the state machine that runs a session.

``QuizEngine`` owns the queue, the grading rule and the running score. It takes
its ordering strategy through the constructor and performs no input or output of
its own, so a full session can be driven from a test in a handful of lines and
the same engine can later back a TUI or a web front end without modification.

Answer grading lives here rather than in the CLI because it is a rule about the
domain, not about the terminal: "paris" matching "Paris" is a decision about
what counts as knowing the answer.

Example:
    >>> from quiz_modes import SequentialMode
    >>> cards = [{'question': '2+2?', 'answer': '4'},
    ...          {'question': 'Capital of France?', 'answer': 'Paris'}]
    >>> engine = QuizEngine(cards, SequentialMode())
    >>> engine.start()
    >>> engine.next_card()['question']
    '2+2?'
    >>> engine.submit_answer('4').is_correct
    True
    >>> engine.next_card()['question']
    'Capital of France?'
    >>> engine.submit_answer('london').is_correct
    False
    >>> engine.next_card() is None
    True
    >>> results = engine.get_results()
    >>> results.correct_count, results.total_answered, results.accuracy
    (1, 2, 50.0)
"""
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from exceptions import EmptyDeckError, QuizStateError
from quiz_modes import QuizMode


@dataclass(frozen=True)
class AnswerResult:
    """Outcome of grading one submitted answer.

    Returned to the caller so the presentation layer has everything it needs to
    give feedback without reaching back into the engine.

    Attributes:
        question: The question that was asked.
        given_answer: What the learner typed, as typed.
        correct_answer: The card's authored answer.
        is_correct: Whether the answer was accepted.
        explanation: The card's explanation, or None if it has none.
        will_repeat: Whether the mode has queued this card to be asked again.
    """

    question: str
    given_answer: str
    correct_answer: str
    is_correct: bool
    explanation: Optional[str] = None
    will_repeat: bool = False


@dataclass(frozen=True)
class QuizResult:
    """Summary of a quiz session.

    Attributes:
        mode_name: Ordering strategy the session ran under.
        total_answered: Answers submitted, counting repeats of the same card —
            the denominator of the accuracy the learner actually achieved.
        correct_count: Answers accepted.
        incorrect_count: Answers rejected.
        accuracy: Percentage correct, rounded to one decimal; 0.0 when nothing
            was answered.
        missed_questions: Distinct questions answered wrong at least once, in
            the order they were first missed — the learner's revision list.
        is_complete: False if the session ended with cards still queued, which
            is what makes an early quit distinguishable from a finished quiz.
    """

    mode_name: str
    total_answered: int
    correct_count: int
    incorrect_count: int
    accuracy: float
    missed_questions: List[str] = field(default_factory=list)
    is_complete: bool = True


class QuizEngine:
    """Runs a flashcard quiz over a deck using an injected ordering strategy.

    Lifecycle: construct, ``start()``, then alternate ``next_card()`` and
    ``submit_answer()`` until ``next_card()`` returns None, then
    ``get_results()``. Calling those out of order raises ``QuizStateError``
    rather than producing a quietly wrong score.

    Answers are compared on whitespace-collapsed text, case-insensitively
    unless ``case_sensitive`` is set. Nothing else is normalised: stripping
    punctuation or accents would make "resume" match "résumé", which for a
    vocabulary deck marks a wrong answer right.

    Example:
        >>> from quiz_modes import SequentialMode
        >>> engine = QuizEngine([{'question': 'Q', 'answer': 'A'}],
        ...                     SequentialMode())
        >>> engine.submit_answer('A')
        Traceback (most recent call last):
            ...
        exceptions.QuizStateError: Quiz has not been started; call start() first
    """

    def __init__(
        self,
        flashcards: List[Dict[str, Any]],
        mode: QuizMode,
        *,
        case_sensitive: bool = False,
    ) -> None:
        """Wire the engine to a deck and an ordering strategy.

        Args:
            flashcards: Validated flashcards to quiz on.
            mode: Ordering strategy, injected so the engine never chooses one
                itself and can be tested with a stub.
            case_sensitive: Whether answer comparison respects letter case.

        Raises:
            EmptyDeckError: If the deck contains no flashcards.
        """
        if not flashcards:
            raise EmptyDeckError("Cannot start a quiz with an empty deck")

        self._flashcards = list(flashcards)
        self._mode = mode
        self._case_sensitive = case_sensitive

        self._queue: Deque[Dict[str, Any]] = deque()
        self._current: Optional[Dict[str, Any]] = None
        self._started = False
        self._answers: List[AnswerResult] = []

    @property
    def mode_name(self) -> str:
        """Name of the ordering strategy in use."""
        return self._mode.get_mode_name()

    @property
    def current_card(self) -> Optional[Dict[str, Any]]:
        """The card awaiting an answer, or None if there is none."""
        return self._current

    @property
    def cards_remaining(self) -> int:
        """Cards still queued, excluding the one awaiting an answer.

        A lower bound only: an adaptive mode can add to the queue as the session
        goes on, so this is honest progress information rather than a promise.
        """
        return len(self._queue)

    @property
    def is_finished(self) -> bool:
        """True once the queue is empty and no card is awaiting an answer."""
        return self._started and not self._queue and self._current is None

    def start(self) -> None:
        """Build the queue and begin a session.

        Safe to call again to restart: the mode's per-session state and all
        recorded answers are cleared, so a second quiz cannot inherit the first
        one's score.

        Raises:
            EmptyDeckError: If the mode returns an empty queue from a non-empty
                deck — a bug in the mode, reported rather than presented to the
                learner as a quiz with nothing in it.
        """
        self._mode.reset()
        queue = self._mode.build_queue(self._flashcards)
        if not queue:
            raise EmptyDeckError(
                f"Mode {self.mode_name!r} produced an empty queue from "
                f"{len(self._flashcards)} flashcard(s)"
            )

        self._queue = deque(queue)
        self._current = None
        self._answers = []
        self._started = True

    def next_card(self) -> Optional[Dict[str, Any]]:
        """Take the next card from the queue.

        Returns:
            The next flashcard, or None when the session is over.

        Raises:
            QuizStateError: If the quiz has not been started, or if the current
                card has not been answered yet — advancing past an unanswered
                card would drop it from the score silently.
        """
        self._require_started()
        if self._current is not None:
            raise QuizStateError(
                f"Card {self._current.get('question')!r} is still awaiting an "
                f"answer; call submit_answer() before next_card()"
            )

        self._current = self._queue.popleft() if self._queue else None
        return self._current

    def submit_answer(self, answer: str) -> AnswerResult:
        """Grade an answer to the current card and advance past it.

        Args:
            answer: The learner's answer, as typed.

        Returns:
            The graded result, including whether the mode has re-queued the card.

        Raises:
            QuizStateError: If the quiz has not been started, or no card is
                awaiting an answer.
        """
        self._require_started()
        if self._current is None:
            raise QuizStateError(
                "No card is awaiting an answer; call next_card() first"
            )

        card = self._current
        is_correct = self._is_correct(answer, card['answer'])

        will_repeat = self._mode.should_repeat(card, is_correct)
        if will_repeat:
            self._queue.append(card)

        result = AnswerResult(
            question=card['question'],
            given_answer=answer,
            correct_answer=card['answer'],
            is_correct=is_correct,
            explanation=card.get('explanation'),
            will_repeat=will_repeat,
        )
        self._answers.append(result)
        self._current = None
        return result

    def get_hints(self) -> List[str]:
        """Return the hints authored for the current card.

        Returns:
            The card's hints, or an empty list if it has none.

        Raises:
            QuizStateError: If no card is awaiting an answer.
        """
        self._require_started()
        if self._current is None:
            raise QuizStateError("No card is awaiting an answer; nothing to hint at")
        hints = self._current.get('hints') or []
        return list(hints)

    def get_results(self) -> QuizResult:
        """Summarise the session so far.

        Callable mid-session on purpose: quitting early is a normal way to end a
        quiz, and the learner should still see what they scored.

        Returns:
            The summary, with ``is_complete`` False if cards remain queued.

        Raises:
            QuizStateError: If the quiz has not been started.
        """
        self._require_started()

        correct_count = sum(1 for result in self._answers if result.is_correct)
        total_answered = len(self._answers)

        missed_questions: List[str] = []
        for result in self._answers:
            if not result.is_correct and result.question not in missed_questions:
                missed_questions.append(result.question)

        accuracy = (
            round(correct_count / total_answered * 100, 1) if total_answered else 0.0
        )

        return QuizResult(
            mode_name=self.mode_name,
            total_answered=total_answered,
            correct_count=correct_count,
            incorrect_count=total_answered - correct_count,
            accuracy=accuracy,
            missed_questions=missed_questions,
            is_complete=self.is_finished,
        )

    def _require_started(self) -> None:
        """Guard methods that are meaningless before ``start()``.

        Raises:
            QuizStateError: If the quiz has not been started.
        """
        if not self._started:
            raise QuizStateError("Quiz has not been started; call start() first")

    def _is_correct(self, given: str, expected: str) -> bool:
        """Compare a submitted answer with the authored one.

        Args:
            given: The learner's answer, as typed.
            expected: The card's authored answer.

        Returns:
            True if the two match after collapsing whitespace, and after
            case-folding unless the engine was built case-sensitive.
        """
        given_normalised = ' '.join(str(given).split())
        expected_normalised = ' '.join(str(expected).split())
        if self._case_sensitive:
            return given_normalised == expected_normalised
        return given_normalised.casefold() == expected_normalised.casefold()
