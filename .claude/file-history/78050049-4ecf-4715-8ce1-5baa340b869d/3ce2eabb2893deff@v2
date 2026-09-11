"""
CLI Interface Module - Version 2

Displays reports in terminal with formatting and color.

Refactored from v1 with no change to observable output:
  - magic values extracted into overridable class constants
  - the duplicated summary/monthly branches collapsed behind REPORT_TITLES
  - the three duplicated error branches collapsed behind ERROR_CATEGORIES
  - panel chrome, row formatting and dispatch separated
  - complete type annotations
"""

from __future__ import annotations

from typing import Any, ClassVar, Iterable, Mapping, Sequence, Tuple

# A report as produced by ReportEngine.generate_report: keys 'mode', 'data', 'total'.
ReportData = Mapping[str, Any]

# (matching keywords, panel heading)
ErrorCategory = Tuple[Tuple[str, ...], str]


class CLIInterface:
    """Terminal interface for displaying expense reports."""

    # Panel geometry
    LINE_WIDTH: ClassVar[int] = 50
    HEAVY_RULE: ClassVar[str] = "="
    LIGHT_RULE: ClassVar[str] = "-"
    ERROR_RULE: ClassVar[str] = "!"
    INDENT: ClassVar[str] = "  "

    # Amount row layout
    LABEL_WIDTH: ClassVar[int] = 20
    AMOUNT_WIDTH: ClassVar[int] = 10
    AMOUNT_PRECISION: ClassVar[int] = 2
    CURRENCY_SYMBOL: ClassVar[str] = "$"
    TOTAL_LABEL: ClassVar[str] = "TOTAL"

    # Report defaults
    DEFAULT_MODE: ClassVar[str] = "unknown"
    DEFAULT_TOTAL: ClassVar[float] = 0.0

    # Report mode -> panel heading. Adding a mode is a one-line change here.
    REPORT_TITLES: ClassVar[Mapping[str, str]] = {
        'summary': "EXPENSE SUMMARY BY CATEGORY",
        'monthly': "MONTHLY EXPENSE TOTALS",
    }

    UNKNOWN_MODE_TEMPLATE: ClassVar[str] = "\nError: Unknown report mode '{mode}'\n"

    # Ordered: first matching keyword set wins. See _classify_error.
    ERROR_CATEGORIES: ClassVar[Tuple[ErrorCategory, ...]] = (
        (('file', 'not found'), "ERROR: File Not Found"),
        (('invalid', 'value'), "ERROR: Invalid Data"),
    )
    DEFAULT_ERROR_HEADING: ClassVar[str] = "ERROR"

    def display_report(self, report_data: ReportData) -> None:
        """Display formatted report to terminal.

        Args:
            report_data: Report mapping with 'mode', 'data' and 'total' keys.
                An unrecognized or missing 'mode' prints a one-line notice.
        """
        mode = report_data.get('mode', self.DEFAULT_MODE)
        title = self.REPORT_TITLES.get(mode)

        if title is None:
            print(self.UNKNOWN_MODE_TEMPLATE.format(mode=mode))
            return

        self._print_panel(self._build_report_body(title, report_data),
                          self.HEAVY_RULE)

    def display_error(self, error: BaseException) -> None:
        """Display error message to terminal.

        Args:
            error: The exception to report. Its str() is shown verbatim and
                also decides which heading the panel carries.
        """
        error_str = str(error)
        heading = self._classify_error(error_str)

        self._print_panel(
            [f"{self.INDENT}{heading}", self.INDENT + error_str],
            self.ERROR_RULE,
        )

    def _build_report_body(self, title: str,
                           report_data: ReportData) -> Sequence[str]:
        """Build the panel body: heading, one row per entry, then the total."""
        data: Mapping[str, float] = report_data.get('data', {})
        total: float = report_data.get('total', self.DEFAULT_TOTAL)

        return [
            f"{self.INDENT}{title}",
            self.HEAVY_RULE * self.LINE_WIDTH,
            *(self._format_amount_row(label, amount)
              for label, amount in sorted(data.items())),
            self.LIGHT_RULE * self.LINE_WIDTH,
            self._format_amount_row(self.TOTAL_LABEL, total),
        ]

    def _classify_error(self, error_str: str) -> str:
        """Return the panel heading for an error message.

        Categories are matched in declaration order, which is significant:
        'value' also appears in many file-related messages, so the file
        category must be tested first to preserve v1 behavior.
        """
        lowered = error_str.lower()

        for keywords, heading in self.ERROR_CATEGORIES:
            if any(keyword in lowered for keyword in keywords):
                return heading

        return self.DEFAULT_ERROR_HEADING

    def _format_amount_row(self, label: str, amount: float) -> str:
        """Format a single label/amount row of a report panel."""
        return (
            f"{self.INDENT}{label:<{self.LABEL_WIDTH}s} "
            f"{self.CURRENCY_SYMBOL}"
            f"{amount:>{self.AMOUNT_WIDTH}.{self.AMOUNT_PRECISION}f}"
        )

    def _print_panel(self, body_lines: Iterable[str], rule: str) -> None:
        """Print body_lines framed by a full-width rule, blank-line padded."""
        border = rule * self.LINE_WIDTH
        print("\n" + border)
        for line in body_lines:
            print(line)
        print(border + "\n")
