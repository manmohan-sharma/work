"""
Loading and validation of flashcard decks stored as JSON.

``FlashcardLoader`` is the only module that knows the deck is JSON on disk.
Everything downstream receives plain validated dicts, which is what lets the
quiz engine be tested against an in-memory list with no fixture files.

Validation is strict and fails on the first bad card rather than skipping it. A
quiz assembled from a silently dropped card looks perfectly normal — the learner
simply never sees the material they were trying to study, which is the one
failure mode they cannot detect themselves.

Expected file format — a JSON array of card objects, or an object with a
``"flashcards"`` array:

    [
      {
        "question": "What is the capital of France?",
        "answer": "Paris",
        "difficulty": "easy",
        "category": "Geography",
        "hints": ["It is on the Seine"],
        "explanation": "Paris has been the capital since 508 AD."
      }
    ]

Example:
    >>> from pathlib import Path
    >>> loader = FlashcardLoader()
    >>> cards = loader.load_flashcards(Path('decks/geography.json'))  # doctest: +SKIP
    >>> sorted(loader.get_categories(cards))                          # doctest: +SKIP
    ['Geography', 'History']
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from exceptions import (
    FlashcardLoadError,
    FlashcardValidationError,
)


class FlashcardLoader:
    """Loads flashcard decks from JSON files and validates their contents.

    Required fields are ``question`` and ``answer``; ``difficulty``,
    ``category``, ``hints`` and ``explanation`` are optional and absent keys are
    left absent rather than filled with defaults, so the quiz engine can tell
    "no hints authored" from "an empty hint list".

    The class is stateless and safe to reuse across decks.

    Example:
        >>> loader = FlashcardLoader()
        >>> loader.validate_flashcard({'question': 'Q?', 'answer': 'A'})
        True
        >>> loader.validate_flashcard({'question': 'Q?'})
        False
    """

    REQUIRED_FIELDS: Tuple[str, ...] = ('question', 'answer')
    VALID_DIFFICULTIES: Tuple[str, ...] = ('easy', 'medium', 'hard')
    TEXT_FIELDS: Tuple[str, ...] = ('question', 'answer', 'category', 'explanation')
    DECK_KEY = 'flashcards'

    def load_flashcards(self, file_path: Union[Path, str]) -> List[Dict[str, Any]]:
        """Load and validate a flashcard deck from a JSON file.

        Args:
            file_path: Path to the JSON deck. A plain string is accepted.

        Returns:
            The deck's flashcards in file order, every one of them validated.
            An empty file-level array yields an empty list, which is valid data
            — refusing to quiz on it is the caller's decision, not the loader's.

        Raises:
            FlashcardLoadError: If the file is missing, unreadable, not valid
                JSON, or does not contain a flashcard array.
            FlashcardValidationError: If any card fails validation. The message
                names the card's index and the offending field.

        Example:
            >>> FlashcardLoader().load_flashcards('missing.json')
            Traceback (most recent call last):
                ...
            exceptions.FlashcardLoadError: Flashcard file not found [missing.json]
        """
        path = Path(file_path)

        try:
            raw_text = path.read_text(encoding='utf-8')
        except FileNotFoundError:
            raise FlashcardLoadError("Flashcard file not found", str(path)) from None
        except IsADirectoryError:
            raise FlashcardLoadError(
                "Expected a JSON file but found a directory", str(path)
            ) from None
        except PermissionError:
            raise FlashcardLoadError(
                "Flashcard file is not readable", str(path)
            ) from None
        except UnicodeDecodeError as error:
            raise FlashcardLoadError(
                f"Flashcard file is not valid UTF-8 text: {error}", str(path)
            ) from error

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as error:
            raise FlashcardLoadError(
                f"Flashcard file is not valid JSON: {error.msg} "
                f"(line {error.lineno}, column {error.colno})",
                str(path),
            ) from error

        return self.validate_flashcards(self._extract_deck(payload, path))

    def validate_flashcard(self, flashcard: Dict[str, Any]) -> bool:
        """Check whether a single flashcard is structurally valid.

        Non-throwing by design, for callers that want to filter or count rather
        than fail. ``validate_flashcards`` applies the identical rules and
        raises instead; both share one implementation so the two can never
        disagree about what "valid" means.

        Args:
            flashcard: Candidate flashcard mapping.

        Returns:
            True if the card has non-empty ``question`` and ``answer`` strings
            and every optional field it does define is well-formed.

        Example:
            >>> loader = FlashcardLoader()
            >>> loader.validate_flashcard(
            ...     {'question': 'Q?', 'answer': 'A', 'difficulty': 'tricky'}
            ... )
            False
        """
        return self._find_problem(flashcard) is None

    def validate_flashcards(
        self, flashcards: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate an entire deck, failing on the first invalid card.

        Args:
            flashcards: Flashcards to validate, in file order.

        Returns:
            The same list, unmodified. Nothing is normalised or defaulted here:
            a loader that quietly rewrites the user's data makes the file on
            disk and the deck in memory two different things.

        Raises:
            FlashcardValidationError: If any card is invalid. The message
                carries the card's index and the offending field.

        Example:
            >>> FlashcardLoader().validate_flashcards(
            ...     [{'question': 'Q?', 'answer': ''}]
            ... )
            Traceback (most recent call last):
                ...
            exceptions.FlashcardValidationError: Card 0: 'answer' must be a non-empty string (field: answer)
        """
        for index, flashcard in enumerate(flashcards):
            problem = self._find_problem(flashcard)
            if problem is not None:
                field, reason = problem
                raise FlashcardValidationError(reason, card_index=index, field=field)
        return flashcards

    def get_categories(self, flashcards: List[Dict[str, Any]]) -> Set[str]:
        """Collect the distinct categories present in a deck.

        Args:
            flashcards: Flashcards to inspect. Cards with no ``category`` are
                skipped rather than counted under a placeholder, so an
                uncategorised deck reports no categories at all.

        Returns:
            Set of category names, whitespace-stripped.

        Example:
            >>> FlashcardLoader().get_categories([
            ...     {'question': 'Q1', 'answer': 'A1', 'category': 'Math'},
            ...     {'question': 'Q2', 'answer': 'A2'},
            ...     {'question': 'Q3', 'answer': 'A3', 'category': 'Math'},
            ... ]) == {'Math'}
            True
        """
        return {
            flashcard['category'].strip()
            for flashcard in flashcards
            if isinstance(flashcard.get('category'), str)
            and flashcard['category'].strip()
        }

    def _extract_deck(self, payload: Any, path: Path) -> List[Dict[str, Any]]:
        """Pull the flashcard array out of a parsed JSON payload.

        Accepts either a bare array or an object with a ``"flashcards"`` key,
        because both shapes are common in hand-written decks and rejecting one
        of them buys nothing.

        Args:
            payload: Result of ``json.loads`` on the deck file.
            path: Source path, used in error messages.

        Returns:
            The list of card objects.

        Raises:
            FlashcardLoadError: If no flashcard array can be found, or an entry
                is not a JSON object.
        """
        if isinstance(payload, dict):
            if self.DECK_KEY not in payload:
                raise FlashcardLoadError(
                    f"JSON object has no {self.DECK_KEY!r} key; expected an "
                    f"array of flashcards",
                    str(path),
                )
            payload = payload[self.DECK_KEY]

        if not isinstance(payload, list):
            raise FlashcardLoadError(
                f"Expected an array of flashcards but found "
                f"{type(payload).__name__}",
                str(path),
            )

        for index, entry in enumerate(payload):
            if not isinstance(entry, dict):
                raise FlashcardLoadError(
                    f"Flashcard at index {index} is a {type(entry).__name__}, "
                    f"not a JSON object",
                    str(path),
                )
        return payload

    def _find_problem(
        self, flashcard: Dict[str, Any]
    ) -> Optional[Tuple[str, str]]:
        """Return the first validation problem in a flashcard, if any.

        The single source of truth for what makes a flashcard valid. Written
        with early returns so each rule reads as one independent statement.

        Args:
            flashcard: Candidate flashcard mapping.

        Returns:
            ``(field, reason)`` for the first rule violated, or None if the card
            is valid.
        """
        if not isinstance(flashcard, dict):
            return ('<card>', f"expected a mapping, got {type(flashcard).__name__}")

        for field in self.REQUIRED_FIELDS:
            value = flashcard.get(field)
            if not isinstance(value, str) or not value.strip():
                return (field, f"{field!r} must be a non-empty string")

        difficulty = flashcard.get('difficulty')
        if difficulty is not None:
            if not isinstance(difficulty, str):
                return ('difficulty', "'difficulty' must be a string")
            if difficulty.strip().lower() not in self.VALID_DIFFICULTIES:
                return (
                    'difficulty',
                    f"'difficulty' must be one of "
                    f"{', '.join(self.VALID_DIFFICULTIES)}, got {difficulty!r}",
                )

        hints = flashcard.get('hints')
        if hints is not None:
            if not isinstance(hints, list):
                return ('hints', "'hints' must be a list of strings")
            for position, hint in enumerate(hints):
                if not isinstance(hint, str) or not hint.strip():
                    return (
                        'hints',
                        f"hint at index {position} must be a non-empty string",
                    )

        for field in ('category', 'explanation'):
            value = flashcard.get(field)
            if value is not None and not isinstance(value, str):
                return (field, f"{field!r} must be a string if provided")

        return None
