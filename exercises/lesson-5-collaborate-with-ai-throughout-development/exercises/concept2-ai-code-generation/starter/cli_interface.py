"""
Terminal interface for the flashcard quizzer.

The only module that talks to a human. It reads and writes through two injected
callables (``input_fn`` and ``output_fn``) instead of calling ``input`` and
``print`` directly, which is what allows a whole session to be tested by handing
it a scripted list of answers and inspecting the captured lines — no pty, no
captured stdout, no monkeypatching.

It holds no quiz rules of its own. Grading, ordering and scoring belong to
``quiz_engine`` and ``quiz_modes``; this module decides only what appears on
screen and what the learner is allowed to type.

Commands are prefixed with a colon so they cannot collide with a real answer —
on a deck about study skills, ``hint`` is a plausible answer to a question, and
silently treating it as a command would mark a correct answer wrong:

    :hint   reveal the next hint for this card
    :skip   give up on this card and see the answer
    :quit   end the session and show the score so far

Example:
    >>> from quiz_engine import QuizEngine
    >>> from quiz_modes import SequentialMode
    >>> lines = []
    >>> cli = CLIInterface(input_fn=iter(['4', 'Paris']).__next__,
    ...                    output_fn=lines.append)
    >>> engine = QuizEngine([{'question': '2+2?', 'answer': '4'},
    ...                      {'question': 'Capital of France?',
    ...                       'answer': 'Paris'}], SequentialMode())
    >>> result = cli.run_quiz(engine)
    >>> result.correct_count, result.accuracy
    (2, 100.0)
"""
import argparse
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Optional

from exceptions import QuizzerError
from flashcard_loader import FlashcardLoader
from quiz_engine import AnswerResult, QuizEngine, QuizResult
from quiz_modes import available_modes, create_quiz_mode

HINT_COMMAND = ':hint'
SKIP_COMMAND = ':skip'
QUIT_COMMAND = ':quit'
RULE_WIDTH = 60


class CLIInterface:
    """Presents cards in a terminal and collects the learner's answers.

    Input and output are injected so the class is testable and so a different
    front end (a curses UI, a pipe) can reuse it unchanged.

    Attributes:
        input_fn: Called with no arguments to read one line from the learner.
        output_fn: Called with one string to display a line.
    """

    def __init__(
        self,
        input_fn: Callable[[], str] = input,
        output_fn: Callable[[str], Any] = print,
    ) -> None:
        """Store the input and output callables.

        Args:
            input_fn: Reads one line of input. Defaults to the builtin ``input``,
                called with no prompt — prompts are written through
                ``output_fn`` so that every line the learner sees passes through
                one place and can be captured in a test.
            output_fn: Displays one line. Defaults to ``print``.
        """
        self._input_fn = input_fn
        self._output_fn = output_fn

    # --- Session ----------------------------------------------------------

    def run_quiz(self, engine: QuizEngine) -> QuizResult:
        """Run a full quiz session and display the summary.

        Args:
            engine: A quiz engine over the deck to be quizzed. Started here, so
                the caller does not have to remember to.

        Returns:
            The session summary. An early quit returns a summary with
            ``is_complete`` False rather than raising.
        """
        engine.start()
        self._show_intro(engine)

        while True:
            card = engine.next_card()
            if card is None:
                break

            self.show_card(card, engine)
            answer = self._collect_answer(engine)
            if answer is None:  # :quit, Ctrl-C or end of input
                break

            self.show_feedback(engine.submit_answer(answer))

        result = engine.get_results()
        self.show_summary(result)
        return result

    def _collect_answer(self, engine: QuizEngine) -> Optional[str]:
        """Prompt until the learner gives an answer or ends the session.

        Args:
            engine: Engine holding the current card, used to fetch hints.

        Returns:
            The answer text, an empty string for ``:skip``, or None if the
            learner quit. ``KeyboardInterrupt`` and ``EOFError`` are treated as
            a quit: ending a session early is a normal thing to do, and a
            traceback would lose the score the learner just earned.
        """
        hints_shown = 0

        while True:
            self._output_fn(f"Your answer (or {HINT_COMMAND} / {SKIP_COMMAND} / "
                            f"{QUIT_COMMAND}):")
            try:
                raw_answer = self._input_fn()
            except (KeyboardInterrupt, EOFError, StopIteration):
                self._output_fn("")
                return None

            answer = raw_answer.strip()
            command = answer.lower()

            if command == QUIT_COMMAND:
                return None
            if command == SKIP_COMMAND:
                return ''
            if command == HINT_COMMAND:
                hints_shown = self._show_next_hint(engine, hints_shown)
                continue
            if not answer:
                self._output_fn("  Please type an answer, or "
                                f"{SKIP_COMMAND} to move on.")
                continue

            return answer

    def _show_next_hint(self, engine: QuizEngine, hints_shown: int) -> int:
        """Reveal one more hint for the current card.

        Hints are released one at a time rather than all at once, so a learner
        who needs a nudge does not get handed the answer.

        Args:
            engine: Engine holding the current card.
            hints_shown: How many hints have already been revealed.

        Returns:
            The updated number of hints revealed.
        """
        hints = engine.get_hints()
        if not hints:
            self._output_fn("  No hints for this card.")
            return hints_shown
        if hints_shown >= len(hints):
            self._output_fn(f"  No more hints ({len(hints)} shown).")
            return hints_shown

        self._output_fn(f"  Hint {hints_shown + 1}/{len(hints)}: "
                        f"{hints[hints_shown]}")
        return hints_shown + 1

    # --- Display ----------------------------------------------------------

    def _show_intro(self, engine: QuizEngine) -> None:
        """Announce the mode and deck size at the start of a session.

        Args:
            engine: Engine about to be run.
        """
        self._output_fn("=" * RULE_WIDTH)
        self._output_fn(f"Flashcard quiz — {engine.mode_name} mode, "
                        f"{engine.cards_remaining} card(s)")
        self._output_fn("=" * RULE_WIDTH)

    def show_card(self, flashcard: Dict[str, Any], engine: QuizEngine) -> None:
        """Display a card's question and its metadata.

        Args:
            flashcard: The card being asked.
            engine: Engine, used for the remaining-card count.
        """
        labels = [
            str(flashcard[field])
            for field in ('category', 'difficulty')
            if flashcard.get(field)
        ]
        suffix = f"  [{' · '.join(labels)}]" if labels else ""

        self._output_fn("")
        self._output_fn("-" * RULE_WIDTH)
        self._output_fn(f"Q: {flashcard['question']}{suffix}")
        self._output_fn(f"   ({engine.cards_remaining} card(s) to go)")

    def show_feedback(self, result: AnswerResult) -> None:
        """Display the outcome of one answer.

        Args:
            result: The graded answer.
        """
        if result.is_correct:
            self._output_fn("  Correct.")
        else:
            given = result.given_answer.strip()
            self._output_fn(f"  Incorrect — the answer is: {result.correct_answer}")
            if given:
                self._output_fn(f"  You answered: {given}")

        if result.explanation:
            self._output_fn(f"  {result.explanation}")
        if result.will_repeat:
            self._output_fn("  This card will come back later.")

    def show_summary(self, result: QuizResult) -> None:
        """Display the end-of-session score and revision list.

        Args:
            result: The session summary.
        """
        self._output_fn("")
        self._output_fn("=" * RULE_WIDTH)
        heading = "Quiz complete" if result.is_complete else "Quiz ended early"
        self._output_fn(f"{heading} — {result.mode_name} mode")

        if result.total_answered == 0:
            self._output_fn("No cards answered.")
            self._output_fn("=" * RULE_WIDTH)
            return

        self._output_fn(
            f"Score: {result.correct_count}/{result.total_answered} "
            f"({result.accuracy}%)"
        )
        if result.missed_questions:
            self._output_fn(f"Review these {len(result.missed_questions)} card(s):")
            for question in result.missed_questions:
                self._output_fn(f"  - {question}")
        self._output_fn("=" * RULE_WIDTH)

    def show_error(self, error: Exception) -> None:
        """Display an anticipated failure without a traceback.

        Args:
            error: The error to report.
        """
        self._output_fn(f"Error: {error}")


# --- Entry point ----------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns:
        Parser accepting a deck path and an optional ``--mode``.
    """
    parser = argparse.ArgumentParser(
        description="Quiz yourself on a JSON flashcard deck."
    )
    parser.add_argument('deck', type=Path, help="Path to a JSON flashcard file")
    parser.add_argument(
        '--mode',
        default='sequential',
        help=f"Quiz mode: {', '.join(available_modes())} (default: sequential)",
    )
    parser.add_argument(
        '--case-sensitive',
        action='store_true',
        help="Require answers to match letter case",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Load a deck, run a quiz, and report the outcome.

    The composition root: the one place concrete implementations are chosen.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit status — 0 on a completed or abandoned session, 1 for any
        anticipated failure (bad deck, unknown mode).
    """
    args = build_parser().parse_args(argv)
    cli = CLIInterface()

    try:
        flashcards = FlashcardLoader().load_flashcards(args.deck)
        engine = QuizEngine(
            flashcards,
            create_quiz_mode(args.mode),
            case_sensitive=args.case_sensitive,
        )
        cli.run_quiz(engine)
    except QuizzerError as error:
        cli.show_error(error)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
