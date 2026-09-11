"""
Abstract interface for report generation strategies.

This module implements the Strategy pattern for different report types,
following the Open/Closed Principle for easy extensibility.

The Strategy pattern allows swapping report algorithms at runtime without
modifying client code. Each strategy encapsulates a specific way to analyze
and present transaction data.

Example Usage:
    >>> from expense_tracker.reports.report_mode import CategorySummaryReport
    >>> from expense_tracker.domain.models import Transaction
    >>> from datetime import date
    >>> from decimal import Decimal
    >>>
    >>> transactions = [
    ...     Transaction(date(2025, 1, 15), Decimal('42.50'), 'Food', 'Lunch'),
    ...     Transaction(date(2025, 1, 16), Decimal('120.00'), 'Transport', 'Metro pass'),
    ... ]
    >>>
    >>> report = CategorySummaryReport()
    >>> output = report.process_transactions(transactions)
    >>> print(output)
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from expense_tracker.domain.models import Transaction
from expense_tracker.domain.exceptions import EmptyDatasetError


class ReportMode(ABC):
    """
    Abstract base class for report generation strategies.

    This interface defines the contract for processing transactions and
    generating formatted reports. Each concrete implementation represents
    a different way to analyze and present expense data.

    The Strategy pattern allows:
        - Adding new report types without modifying existing code
        - Swapping report strategies at runtime
        - Independent testing of each report type
        - Reusable report logic across different interfaces (CLI, Web, etc.)

    Implementations must:
        1. Process transaction list
        2. Perform necessary aggregations/calculations
        3. Format results for display
        4. Return formatted string ready for terminal output

    Example implementations:
        - CategorySummaryReport: Group by category, show totals
        - MonthlyTotalsReport: Group by month, show trends
        - TopExpensesReport: Show largest N transactions
    """

    @abstractmethod
    def process_transactions(self, transactions: List[Transaction]) -> str:
        """
        Process transactions and generate formatted report.

        This method is the core of the Strategy pattern. Each implementation
        defines its own logic for analyzing transactions and formatting output.

        Processing typically involves:
            1. Validation (non-empty dataset)
            2. Aggregation (grouping, summing, sorting)
            3. Calculation (totals, averages, percentages)
            4. Formatting (tables, charts, summaries)

        Args:
            transactions: List of Transaction objects to analyze.
                         Must be non-empty.
                         Transactions may be pre-filtered by caller
                         (e.g., by date range or category).

        Returns:
            Formatted report as multi-line string ready for terminal display.

            Format requirements:
                - Human-readable plain text
                - Properly aligned columns (if tabular)
                - Clear section headers
                - Total/summary at end
                - Fits in standard terminal width (80-120 chars)

        Raises:
            EmptyDatasetError: When transactions list is empty.
                Raised before any processing to fail fast.

            ValueError: When transactions contain invalid data that prevents
                report generation (e.g., all amounts are zero).

        Example:
            >>> report = CategorySummaryReport()
            >>> transactions = [
            ...     Transaction(date(2025,1,15), Decimal('42.50'), 'Food', 'Lunch'),
            ...     Transaction(date(2025,1,16), Decimal('120.00'), 'Transport', 'Metro'),
            ...     Transaction(date(2025,1,17), Decimal('35.00'), 'Food', 'Groceries'),
            ... ]
            >>> output = report.process_transactions(transactions)
            >>> print(output)
            Category Summary Report
            =======================
            Category        Total      Count   Avg
            Food          $ 77.50          2   $ 38.75
            Transport     $120.00          1   $120.00
            -----------------------------------------
            TOTAL         $197.50          3   $ 65.83

            >>> # Empty dataset handling
            >>> try:
            ...     report.process_transactions([])
            ... except EmptyDatasetError:
            ...     print("No transactions to report")

        Implementation Notes:
            - Validate transactions list is not empty (raise EmptyDatasetError)
            - Use Decimal for all monetary calculations (avoid float rounding)
            - Sort output logically (by amount descending, alphabetically, etc.)
            - Include totals/summaries for context
            - Use consistent formatting (alignment, decimal places)
            - Consider terminal width constraints
            - Add visual separators (lines, spacing) for readability
        """
        pass

    @abstractmethod
    def get_report_name(self) -> str:
        """
        Return human-readable name for this report type.

        Used for:
            - CLI help text
            - Report headers
            - Logging and error messages

        Returns:
            Short descriptive name (e.g., "Category Summary", "Monthly Totals")

        Example:
            >>> report = CategorySummaryReport()
            >>> print(report.get_report_name())
            Category Summary
        """
        pass


class GroupedTotalsReport(ReportMode):
    """
    Template for reports that group transactions and tabulate their totals.

    CategorySummaryReport and MonthlyTotalsReport are the same report with two
    substitutions: how a transaction is keyed into a group, and how the
    resulting rows are ordered. Everything else - validation, aggregation,
    grand totals, column layout - is identical and lives here.

    Subclasses supply:
        TITLE           Heading printed above the table
        GROUP_HEADER    Column header for the grouping column
        GROUP_WIDTH     Character width of the grouping column
        group_key()     Maps a transaction to its group
        sort_groups()   Orders the aggregated rows for display

    Adding a new grouped report (by weekday, by payee, by quarter) means
    supplying those five things - not copying a 57-line method.
    """

    # Panel geometry, shared by every grouped report
    RULE_WIDTH = 50
    HEAVY_RULE = "="
    LIGHT_RULE = "-"
    TOTAL_LABEL = "TOTAL"

    # Column widths. Data and header widths differ because the original
    # layout right-aligns headers over left-padded currency values.
    AMOUNT_WIDTH = 11
    COUNT_WIDTH = 8
    AVERAGE_WIDTH = 9
    AMOUNT_HEADER_WIDTH = 12
    COUNT_HEADER_WIDTH = 8
    AVERAGE_HEADER_WIDTH = 10

    # Overridden by every concrete subclass
    TITLE: str = ""
    GROUP_HEADER: str = ""
    GROUP_WIDTH: int = 0

    @abstractmethod
    def group_key(self, transaction: Transaction) -> str:
        """Return the group a transaction belongs to (category, month, ...)."""

    @abstractmethod
    def sort_groups(
        self, group_stats: Dict[str, Dict[str, Any]]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Return (group, stats) pairs in display order."""

    def process_transactions(self, transactions: List[Transaction]) -> str:
        """
        Generate a grouped totals report.

        Args:
            transactions: List of Transaction objects to analyze

        Returns:
            Formatted report string with per-group totals and a grand total

        Raises:
            EmptyDatasetError: If transactions list is empty
        """
        if not transactions:
            raise EmptyDatasetError("Cannot generate report from empty transaction list")

        group_stats = self._aggregate(transactions)
        return '\n'.join(self._render(group_stats))

    def _aggregate(self, transactions: List[Transaction]) -> Dict[str, Dict[str, Any]]:
        """Group amounts by key, then reduce each group to total/count/average."""
        grouped = defaultdict(list)
        for transaction in transactions:
            grouped[self.group_key(transaction)].append(transaction.amount)

        group_stats = {}
        for key, amounts in grouped.items():
            total = sum(amounts)
            count = len(amounts)
            group_stats[key] = {
                'total': total,
                'count': count,
                'average': total / count,
            }
        return group_stats

    def _render(self, group_stats: Dict[str, Dict[str, Any]]) -> List[str]:
        """Assemble the full report as a list of lines."""
        return [
            self.TITLE,
            self.HEAVY_RULE * self.RULE_WIDTH,
            self._format_header_row(),
            self.LIGHT_RULE * self.RULE_WIDTH,
            *(self._format_data_row(key, stats)
              for key, stats in self.sort_groups(group_stats)),
            self.LIGHT_RULE * self.RULE_WIDTH,
            self._format_total_row(group_stats),
        ]

    def _format_header_row(self) -> str:
        """Format the column header line."""
        return (
            f"{self.GROUP_HEADER:<{self.GROUP_WIDTH}} "
            f"{'Total':>{self.AMOUNT_HEADER_WIDTH}} "
            f"{'Count':>{self.COUNT_HEADER_WIDTH}} "
            f"{'Avg':>{self.AVERAGE_HEADER_WIDTH}}"
        )

    def _format_data_row(self, label: str, stats: Dict[str, Any]) -> str:
        """Format one group's row of the table."""
        return (
            f"{label:<{self.GROUP_WIDTH}} "
            f"${stats['total']:>{self.AMOUNT_WIDTH},.2f} "
            f"{stats['count']:>{self.COUNT_WIDTH}} "
            f"${stats['average']:>{self.AVERAGE_WIDTH},.2f}"
        )

    def _format_total_row(self, group_stats: Dict[str, Dict[str, Any]]) -> str:
        """Format the grand total row summed across all groups."""
        grand_total = sum(stats['total'] for stats in group_stats.values())
        grand_count = sum(stats['count'] for stats in group_stats.values())
        grand_average = grand_total / grand_count if grand_count > 0 else 0

        return self._format_data_row(
            self.TOTAL_LABEL,
            {'total': grand_total, 'count': grand_count, 'average': grand_average},
        )


class CategorySummaryReport(GroupedTotalsReport):
    """
    Groups transactions by category and shows totals.

    This strategy aggregates all transactions by their category field,
    calculating total spending, transaction count, and average per category.
    Results are sorted by total amount to highlight biggest spending areas.

    Use cases:
        - Identify which expense categories consume most budget
        - Compare spending across different categories
        - Budget planning and allocation

    Output format:
        - One row per category
        - Columns: Category name, Total amount, Count, Average
        - Sorted by total amount (descending)
        - Grand total at bottom

    Example output:
        Category Summary Report
        =======================
        Category        Total      Count   Avg
        Food          $ 450.75         12   $ 37.56
        Transport     $ 320.00          8   $ 40.00
        Utilities     $ 215.50          3   $ 71.83
        -----------------------------------------
        TOTAL         $ 986.25         23   $ 42.88
    """

    TITLE = "Category Summary Report"
    GROUP_HEADER = "Category"
    GROUP_WIDTH = 20

    def group_key(self, transaction: Transaction) -> str:
        """Group by the transaction's category."""
        return transaction.category

    def sort_groups(
        self, group_stats: Dict[str, Dict[str, Any]]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Biggest spenders first: sort by total, descending."""
        return sorted(
            group_stats.items(),
            key=lambda item: item[1]['total'],
            reverse=True
        )

    def get_report_name(self) -> str:
        """Return 'Category Summary'."""
        return "Category Summary"


class MonthlyTotalsReport(GroupedTotalsReport):
    """
    Groups transactions by month and shows totals over time.

    This strategy aggregates transactions by month, allowing analysis of
    spending patterns over time. Useful for identifying seasonal trends,
    tracking monthly budgets, and comparing periods.

    Use cases:
        - Track monthly spending trends over time
        - Identify months with highest/lowest expenses
        - Budget vs. actual comparison by month
        - Seasonal spending analysis

    Output format:
        - One row per month
        - Columns: Month, Total amount, Count, Average
        - Sorted chronologically (oldest first)
        - Grand total at bottom

    Example output:
        Monthly Totals Report
        =====================
        Month           Total      Count   Avg
        2025-01       $1,234.56       45   $ 27.43
        2025-02       $1,089.23       38   $ 28.66
        2025-03       $1,456.78       52   $ 28.01
        -----------------------------------------
        TOTAL         $3,780.57      135   $ 28.00
    """

    TITLE = "Monthly Totals Report"
    GROUP_HEADER = "Month"
    GROUP_WIDTH = 15

    MONTH_KEY_FORMAT = '%Y-%m'

    def group_key(self, transaction: Transaction) -> str:
        """Group by calendar month in YYYY-MM form."""
        return transaction.date.strftime(self.MONTH_KEY_FORMAT)

    def sort_groups(
        self, group_stats: Dict[str, Dict[str, Any]]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Chronological order. YYYY-MM sorts correctly as a string."""
        return sorted(group_stats.items(), key=lambda item: item[0])

    def get_report_name(self) -> str:
        """Return 'Monthly Totals'."""
        return "Monthly Totals"


class TopExpensesReport(ReportMode):
    """
    Shows the N largest individual transactions.

    Output format:
        - Configurable number of top transactions (default: 10)
        - Columns: Date, Amount, Category, Description
        - Sorted by amount (descending)
        - Total of displayed transactions

    Example output:
        Top 10 Expenses Report
        ======================
        Date         Amount    Category        Description
        2025-01-15  $450.00   Electronics     New keyboard
        2025-01-22  $320.00   Transportation  Flight ticket
        2025-02-03  $215.50   Food            Restaurant dinner
        ...
        ---------------------------------------------------------
        TOTAL (top 10)  $1,892.75

    Implementation notes:
        - Sort transactions by amount descending
        - Take first N transactions
        - Truncate long descriptions (max 30 chars)
        - Include rank numbers (optional)
    """

    def __init__(self, top_n: int = 10):
        """
        Initialize report with configurable limit.

        Args:
            top_n: Number of top expenses to show (default: 10)

        Raises:
            ValueError: If top_n < 1
        """
        if top_n < 1:
            raise ValueError(f"top_n must be positive, got {top_n}")
        self.top_n = top_n

    def process_transactions(self, transactions: List[Transaction]) -> str:
        """
        Generate top expenses report showing largest transactions.

        Sorts transactions by amount descending and displays the top N
        with full details (date, amount, category, description).

        Args:
            transactions: List of Transaction objects to analyze

        Returns:
            Formatted report string with top N expenses

        Raises:
            EmptyDatasetError: If transactions list is empty

        Example:
            >>> from datetime import date
            >>> from decimal import Decimal
            >>> txns = [
            ...     Transaction(date(2025, 1, 15), Decimal('450.00'), 'Electronics', 'New keyboard'),
            ...     Transaction(date(2025, 1, 22), Decimal('320.00'), 'Transport', 'Flight ticket'),
            ... ]
            >>> report = TopExpensesReport(top_n=2)
            >>> print(report.process_transactions(txns))
        """
        # Validate non-empty dataset
        if not transactions:
            raise EmptyDatasetError("Cannot generate report from empty transaction list")

        # Sort transactions by amount (descending)
        sorted_transactions = sorted(
            transactions,
            key=lambda t: t.amount,
            reverse=True
        )

        # Take top N transactions (or all if fewer than N)
        top_transactions = sorted_transactions[:self.top_n]
        actual_count = len(top_transactions)

        # Calculate total of displayed transactions
        total_amount = sum(t.amount for t in top_transactions)

        # Format output
        lines = []
        lines.append(f"Top {self.top_n} Expenses Report")
        lines.append("=" * 80)
        lines.append(f"{'Date':<12} {'Amount':>12} {'Category':<20} {'Description':<30}")
        lines.append("-" * 80)

        for transaction in top_transactions:
            # Truncate long descriptions to fit in column
            description = transaction.description
            if len(description) > 30:
                description = description[:27] + "..."

            lines.append(
                f"{transaction.date} "
                f"${transaction.amount:>11,.2f} "
                f"{transaction.category:<20} "
                f"{description:<30}"
            )

        lines.append("-" * 80)
        lines.append(f"TOTAL (top {actual_count})  ${total_amount:>11,.2f}")

        # Add note if fewer transactions than requested
        if actual_count < self.top_n:
            lines.append("")
            lines.append(f"Note: Only {actual_count} transaction(s) available")

        return '\n'.join(lines)

    def get_report_name(self) -> str:
        """Return 'Top N Expenses' where N is the configured limit."""
        return f"Top {self.top_n} Expenses"
