"""
Report strategies for aggregating transactions.

Implements the Strategy pattern: every report is a class behind the same
``ReportMode`` interface, so the CLI picks one by name and calls it without
knowing which aggregation it got. Adding a report type means adding a class
here and nothing else changes — the point of the pattern.

Each strategy returns data rather than formatted text. Keeping aggregation
separate from presentation is what lets the same numbers feed a table, a chart
or a JSON export, and it is what makes these classes assertable in a unit test
without parsing strings.

Example:
    >>> from report_modes import MonthlyTotalReport, SummaryByCategory
    >>> transactions = [
    ...     {'date': '2024-01-15', 'amount': 45.50, 'category': 'Food',
    ...      'description': 'Grocery'},
    ...     {'date': '2024-02-10', 'amount': 75.00, 'category': 'Fun',
    ...      'description': 'Concert'},
    ... ]
    >>> SummaryByCategory().process_transactions(transactions)
    {'mode': 'summary', 'data': {'Food': 45.5, 'Fun': 75.0}, 'total': 120.5}
    >>> MonthlyTotalReport().process_transactions(transactions)
    {'mode': 'monthly', 'data': {'2024-01': 45.5, '2024-02': 75.0}, 'total': 120.5}
"""
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Dict, List

MONTH_KEY_LENGTH = 4 + 1 + 2  # "YYYY-MM" sliced from an ISO date string.


class ReportMode(ABC):
    """Interface for a transaction aggregation strategy.

    Implementations group transactions on one dimension and sum the amounts.
    All of them return the same result shape so the caller can format any
    report with a single code path.
    """

    @abstractmethod
    def process_transactions(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate transactions into report data.

        Args:
            transactions: Transaction dicts as produced by a TransactionLoader.
                An empty list is valid input, not an error.

        Returns:
            Dict with keys ``mode`` (this report's name), ``data`` (group key to
            summed amount) and ``total`` (sum across all groups).

        Raises:
            ValueError: If a transaction is missing the field this report groups
                on, or its amount is not numeric.
        """

    @abstractmethod
    def get_mode_name(self) -> str:
        """Return the identifier used for this mode on the command line."""


def _aggregate(
    transactions: List[Dict[str, Any]],
    mode_name: str,
    group_key_field: str,
    group_key_of,
) -> Dict[str, Any]:
    """Sum transaction amounts into buckets chosen by ``group_key_of``.

    Shared by every strategy so that totals, rounding and error messages stay
    identical across report types — the inconsistency that would otherwise show
    up as two reports disagreeing about the same data.

    Args:
        transactions: Transaction dicts to aggregate.
        mode_name: Value placed under the result's ``mode`` key.
        group_key_field: Field each transaction is grouped on, for messages.
        group_key_of: Callable mapping a transaction to its group key.

    Returns:
        Report dict with ``mode``, ``data`` and ``total`` keys.

    Raises:
        ValueError: If a transaction lacks the grouping field or has a
            non-numeric amount.
    """
    totals_by_group: Dict[str, float] = defaultdict(float)

    for position, transaction in enumerate(transactions, start=1):
        if group_key_field not in transaction:
            raise ValueError(
                f"Transaction {position} is missing the "
                f"{group_key_field!r} field required by the {mode_name} report"
            )
        try:
            amount = float(transaction['amount'])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                f"Transaction {position} has a non-numeric amount: "
                f"{transaction.get('amount')!r}"
            ) from None

        totals_by_group[group_key_of(transaction)] += amount

    return {
        'mode': mode_name,
        'data': dict(totals_by_group),
        'total': round(sum(totals_by_group.values()), 2),
    }


class SummaryByCategory(ReportMode):
    """Totals spending per category.

    Answers "where is the money going" — the report a user runs first. Groups on
    the ``category`` field and sums the amounts, leaving ordering and formatting
    to the presentation layer.

    Example:
        >>> SummaryByCategory().process_transactions(
        ...     [{'date': '2024-01-15', 'amount': 45.50, 'category': 'Food',
        ...       'description': 'Grocery'}]
        ... )
        {'mode': 'summary', 'data': {'Food': 45.5}, 'total': 45.5}
    """

    MODE_NAME = 'summary'

    def process_transactions(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Sum amounts per category.

        Args:
            transactions: Transaction dicts; an empty list yields a zero report.

        Returns:
            Dict with ``mode`` of ``"summary"``, ``data`` mapping each category
            to its total, and the overall ``total``.

        Raises:
            ValueError: If a transaction has no ``category`` or a non-numeric
                amount.
        """
        return _aggregate(
            transactions,
            mode_name=self.MODE_NAME,
            group_key_field='category',
            group_key_of=lambda transaction: transaction['category'],
        )

    def get_mode_name(self) -> str:
        """Return ``"summary"``."""
        return self.MODE_NAME


class MonthlyTotalReport(ReportMode):
    """Totals spending per calendar month.

    Answers "is spending trending up" — the report that needs several months of
    data to be interesting. Groups on the ``YYYY-MM`` prefix of the ISO ``date``
    field, which sorts chronologically as a plain string and therefore needs no
    date parsing.

    Example:
        >>> MonthlyTotalReport().process_transactions(
        ...     [{'date': '2024-01-15', 'amount': 45.50, 'category': 'Food',
        ...       'description': 'Grocery'}]
        ... )
        {'mode': 'monthly', 'data': {'2024-01': 45.5}, 'total': 45.5}
    """

    MODE_NAME = 'monthly'

    def process_transactions(
        self, transactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Sum amounts per month.

        Args:
            transactions: Transaction dicts whose ``date`` is an ISO
                ``YYYY-MM-DD`` string; an empty list yields a zero report.

        Returns:
            Dict with ``mode`` of ``"monthly"``, ``data`` mapping each
            ``YYYY-MM`` key to its total, and the overall ``total``.

        Raises:
            ValueError: If a transaction has no ``date``, a date that is not
                ISO-formatted, or a non-numeric amount.
        """
        return _aggregate(
            transactions,
            mode_name=self.MODE_NAME,
            group_key_field='date',
            group_key_of=self._month_key,
        )

    def get_mode_name(self) -> str:
        """Return ``"monthly"``."""
        return self.MODE_NAME

    @staticmethod
    def _month_key(transaction: Dict[str, Any]) -> str:
        """Extract the ``YYYY-MM`` month key from a transaction's date.

        Args:
            transaction: Transaction dict containing a ``date`` field.

        Returns:
            The first seven characters of the ISO date, e.g. ``"2024-01"``.

        Raises:
            ValueError: If the date is not an ISO ``YYYY-MM-DD`` string. Reported
                rather than silently bucketed, because a mis-parsed date puts
                real spending in the wrong month, which is invisible in output.
        """
        date_value = str(transaction['date']).strip()
        month_key = date_value[:MONTH_KEY_LENGTH]
        if len(month_key) < MONTH_KEY_LENGTH or month_key[4] != '-':
            raise ValueError(
                f"Date {date_value!r} is not in YYYY-MM-DD format, "
                f"so its month cannot be determined"
            )
        return month_key
