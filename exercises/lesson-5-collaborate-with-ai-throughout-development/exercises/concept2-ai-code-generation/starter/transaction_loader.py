"""
CSV transaction loading with row-level validation.

This module provides the ``TransactionLoader`` contract and its CSV
implementation. The loader owns all knowledge of the file format, so adding a
JSON or OFX source means adding a sibling implementation rather than editing
anything that already works.

Validation is deliberately strict and fails on the first bad row: a report built
from a silently skipped transaction is worse than no report at all, because the
totals look plausible. Every error message names the row it came from so the
caller can point a user at the exact line to fix.

Example:
    >>> from transaction_loader import CSVTransactionLoader
    >>> loader = CSVTransactionLoader()
    >>> transactions = loader.load('examples/sample_expenses.csv')
    >>> transactions[0]
    {'date': '2024-01-15', 'amount': 45.5, 'category': 'Food',
     'description': 'Grocery shopping'}
    >>> loader.load('missing.csv')
    Traceback (most recent call last):
        ...
    FileNotFoundError: Transaction file not found: 'missing.csv'
"""
from abc import ABC, abstractmethod
import csv
from typing import Any, Dict, List


class TransactionLoader(ABC):
    """Interface for loading validated transactions from a data source.

    Consumers depend on this abstraction rather than on a concrete format, which
    is what allows the report layer to be tested against an in-memory list.
    """

    @abstractmethod
    def load(self, filepath: str) -> List[Dict[str, Any]]:
        """Load transactions from a file.

        Args:
            filepath: Path to the source file.

        Returns:
            List of dicts with keys: date, amount, category, description.
            The list preserves source order. An empty source yields an empty
            list.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format or any row is invalid.
        """


class CSVTransactionLoader(TransactionLoader):
    """Loads expense transactions from a CSV file with a header row.

    The file must contain the columns ``date``, ``amount``, ``category`` and
    ``description``; extra columns are ignored, so the loader tolerates exports
    that carry additional bank metadata. All values are stripped of surrounding
    whitespace, and ``amount`` is converted to a positive float.

    Example:
        >>> loader = CSVTransactionLoader()
        >>> loader.load('tests/fixtures/valid_expenses.csv')  # doctest: +SKIP
        [{'date': '2024-01-15', 'amount': 45.5, ...}]
    """

    REQUIRED_COLUMNS = ('date', 'amount', 'category', 'description')

    def load(self, filepath: str) -> List[Dict[str, Any]]:
        """Load and validate every transaction in a CSV file.

        Args:
            filepath: Path to the CSV file to read.

        Returns:
            List of validated transaction dicts in source order.

        Raises:
            FileNotFoundError: If ``filepath`` does not exist.
            ValueError: If the header is absent or missing required columns, or
                if any row fails validation. The message names the offending
                row.
        """
        try:
            with open(filepath, newline='', encoding='utf-8') as csv_file:
                reader = csv.DictReader(csv_file)
                self._validate_columns(reader.fieldnames, filepath)
                # start=2 because the header occupies row 1 of the file.
                return [
                    self._build_transaction(row, row_number)
                    for row_number, row in enumerate(reader, start=2)
                ]
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Transaction file not found: {filepath!r}"
            ) from None
        except IsADirectoryError:
            raise ValueError(
                f"Expected a CSV file but {filepath!r} is a directory"
            ) from None
        except UnicodeDecodeError as error:
            raise ValueError(
                f"{filepath!r} is not valid UTF-8 text: {error}"
            ) from error

    def _validate_columns(self, fieldnames: Any, filepath: str) -> None:
        """Check that the header row declares every required column.

        Args:
            fieldnames: Column names read by ``csv.DictReader``, or None when
                the file is empty.
            filepath: Path used in the error message.

        Raises:
            ValueError: If the header is missing or incomplete.
        """
        if not fieldnames:
            raise ValueError(f"{filepath!r} is empty: no header row found")

        present = {name.strip() for name in fieldnames if name}
        missing = [name for name in self.REQUIRED_COLUMNS if name not in present]
        if missing:
            raise ValueError(
                f"{filepath!r} is missing required column(s): "
                f"{', '.join(missing)}"
            )

    def _build_transaction(
        self, row: Dict[str, Any], row_number: int
    ) -> Dict[str, Any]:
        """Validate one CSV row and convert it to a transaction dict.

        Args:
            row: Raw row as produced by ``csv.DictReader``.
            row_number: 1-based line number in the file, used in messages.

        Returns:
            Dict with keys date, amount, category, description, where amount is
            a positive float and the remaining values are stripped strings.

        Raises:
            ValueError: If a required field is empty or missing, or if amount is
                non-numeric or not positive.
        """
        values: Dict[str, Any] = {}
        for column in self.REQUIRED_COLUMNS:
            raw_value = row.get(column)
            if raw_value is None or not str(raw_value).strip():
                raise ValueError(
                    f"Row {row_number}: required field {column!r} is empty"
                )
            values[column] = str(raw_value).strip()

        values['amount'] = self._parse_amount(values['amount'], row_number)
        return values

    @staticmethod
    def _parse_amount(raw_amount: str, row_number: int) -> float:
        """Convert an amount field to a positive float.

        Args:
            raw_amount: Stripped amount value from the CSV row.
            row_number: 1-based line number, used in the error message.

        Returns:
            The amount as a float greater than zero.

        Raises:
            ValueError: If the value is not numeric, or is zero or negative.
        """
        try:
            amount = float(raw_amount)
        except ValueError:
            raise ValueError(
                f"Row {row_number}: amount {raw_amount!r} is not a number"
            ) from None

        if amount <= 0:
            raise ValueError(
                f"Row {row_number}: amount must be positive, got {amount}"
            )
        return amount
