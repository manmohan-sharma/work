"""
Exception hierarchy for the flashcard quizzer.

Every anticipated failure derives from ``QuizzerError``, so ``cli_interface``
can catch one type at the boundary and print a clean message instead of a
traceback. Anything that is not a ``QuizzerError`` is a genuine bug and should
be allowed to crash loudly.

The hierarchy is two levels deep on purpose: data problems (``FlashcardError``
and below) are the user's to fix by editing their JSON file, while quiz problems
(``QuizError`` and below) mean the program was driven into a state it does not
support. Those two need different messages and different exit codes, and
splitting them here is what keeps that decision out of the CLI.

Example:
    >>> try:
    ...     raise FlashcardValidationError("answer must be a non-empty string",
    ...                                    card_index=3, field="answer")
    ... except QuizzerError as error:
    ...     print(error)
    Card 3: answer must be a non-empty string (field: answer)
"""
from typing import List, Optional


class QuizzerError(Exception):
    """Base class for every error raised by the flashcard quizzer."""


# --- Data errors: the user's JSON file needs fixing ------------------------


class FlashcardError(QuizzerError):
    """Base class for problems with flashcard data or its source file."""


class FlashcardLoadError(FlashcardError):
    """Raised when a flashcard file cannot be read or parsed.

    Wraps the underlying ``OSError`` or ``json.JSONDecodeError`` so callers
    never have to know that the deck happens to be stored as JSON.

    Attributes:
        file_path: Path that could not be loaded, as a string.
    """

    def __init__(self, message: str, file_path: Optional[str] = None) -> None:
        """Build the message with the offending path appended.

        Args:
            message: Human-readable description of the failure.
            file_path: Path that could not be loaded.
        """
        super().__init__(f"{message}" + (f" [{file_path}]" if file_path else ""))
        self.file_path = file_path


class FlashcardValidationError(FlashcardError):
    """Raised when a flashcard's structure or values are invalid.

    Carries the card's position in the file and the offending field name, so the
    user is told which of two hundred cards to edit rather than being handed a
    generic "invalid flashcard".

    Attributes:
        card_index: Zero-based position of the card in the source list.
        field: Name of the field that failed validation.
    """

    def __init__(
        self,
        message: str,
        card_index: Optional[int] = None,
        field: Optional[str] = None,
    ) -> None:
        """Assemble a message that names the card and field at fault.

        Args:
            message: What was wrong with the value.
            card_index: Zero-based index of the card in the source list.
            field: Field that failed validation.
        """
        prefix = f"Card {card_index}: " if card_index is not None else ""
        suffix = f" (field: {field})" if field else ""
        super().__init__(f"{prefix}{message}{suffix}")
        self.card_index = card_index
        self.field = field


class EmptyDeckError(FlashcardError):
    """Raised when a quiz is requested over zero flashcards.

    Separate from ``FlashcardValidationError`` because an empty deck is not
    malformed — it is valid data that simply cannot be quizzed on, which is a
    message rather than an error report.
    """


# --- Quiz errors: the program was driven into an unsupported state ---------


class QuizError(QuizzerError):
    """Base class for problems with quiz orchestration or configuration."""


class QuizModeNotFoundError(QuizError):
    """Raised when a requested quiz mode name is not registered.

    Attributes:
        mode_name: The name that was requested.
        available: Registered mode names, listed in the message.
    """

    def __init__(self, mode_name: str, available: List[str]) -> None:
        """Tell the user what they asked for and what they can use instead.

        Args:
            mode_name: The unrecognised mode name.
            available: Names that are registered.
        """
        super().__init__(
            f"Unknown quiz mode {mode_name!r}. "
            f"Available modes: {', '.join(sorted(available)) or 'none'}"
        )
        self.mode_name = mode_name
        self.available = list(available)


class QuizStateError(QuizError):
    """Raised when an operation is invalid for the quiz's current state.

    Covers answering before the quiz has started, answering when no card is
    awaiting an answer, and advancing past a card that has not been answered.
    Each of these is a caller bug, and a specific exception makes it obvious
    which one happened rather than producing a quietly wrong score.

    Asking for results mid-quiz is deliberately NOT an error: quitting early is
    a normal way to end a session.
    """
