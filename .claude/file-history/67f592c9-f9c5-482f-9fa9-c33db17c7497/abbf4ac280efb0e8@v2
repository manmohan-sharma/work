"""
Core interfaces for the expense tracker application.

These definitions are the contracts agreed during architectural planning. They are
intentionally minimal (Interface Segregation) and are what the orchestration layer
depends on rather than any concrete implementation (Dependency Inversion), so that
new report modes and new data sources can be added without modifying existing code.
"""
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Protocol, runtime_checkable


class ExpenseTrackerError(Exception):
    """Base class for every error raised by the expense tracker.

    Callers that only want to distinguish "our failure" from "unexpected crash"
    can catch this single type at the CLI boundary.
    """


class TransactionValidationError(ExpenseTrackerError):
    """Raised when a source row cannot be parsed into a valid Transaction.

    Carries the offending row number and reason so the CLI can report precisely
    which line of the input file is at fault.
    """


class ReportModeNotFoundError(ExpenseTrackerError):
    """Raised when a requested report mode name is not present in the registry."""


class Transaction(Protocol):
    """Structural contract for a single expense record.

    Implemented in practice by a frozen dataclass. Declared here as a Protocol so
    that interface consumers depend on the shape of a transaction rather than on
    the concrete model module.

    Attributes:
        date: Calendar date on which the transaction occurred.
        description: Free-text merchant or memo field.
        category: Category label used for grouping in reports.
        amount: Signed monetary value; negative for expenses, positive for income.
            Decimal is used rather than float to avoid rounding drift in totals.
    """

    date: date
    description: str
    category: str
    amount: Decimal


class TransactionLoader(ABC):
    """Interface for loading and validating transactions from a data source.

    Implementations own all knowledge of a specific file format. Adding support
    for JSON or OFX means adding an implementation here, not changing the engine.
    """

    @abstractmethod
    def load(self, filepath: str) -> List[Transaction]:
        """Load and validate all transactions from the given file.

        Args:
            filepath: Path to the source data file.

        Returns:
            Transactions in file order. An empty list is a valid result for an
            input file that contains only a header.

        Raises:
            FileNotFoundError: If ``filepath`` does not exist or is unreadable.
            TransactionValidationError: If a row is present but cannot be parsed
                into a valid transaction.
        """
        ...


class ReportMode(ABC):
    """Strategy interface for turning transactions into report data.

    Each concrete report type is one implementation of this interface. This is the
    system's primary extension point: a new report is a new subclass plus a
    registry entry, satisfying the Open/Closed Principle.

    Implementations must be pure — no I/O, no printing, no mutation of the input
    list — which is what keeps report tests fast and free of mocking.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short mode identifier used on the command line, e.g. ``"by-category"``."""
        ...

    @abstractmethod
    def process_transactions(self, transactions: List[Transaction]) -> Dict[str, Any]:
        """Aggregate transactions into structured report data.

        Args:
            transactions: Validated transactions to summarise. Must not be mutated.

        Returns:
            A report structure containing at minimum a ``title`` string, a ``rows``
            sequence of label/value pairs, and a ``total`` Decimal. Returning data
            rather than a formatted string keeps presentation choices out of the
            report logic.

        Raises:
            Nothing. An empty input must yield an empty report, not an error.
        """
        ...


class ReportFormatter(Protocol):
    """Interface for rendering report data for display.

    Kept separate from ReportMode so that output format and report logic vary
    independently: a plain-text formatter and a CSV formatter can render the same
    report data with no change to any strategy.
    """

    def format(self, report_data: Dict[str, Any]) -> str:
        """Render report data as a display-ready string.

        Args:
            report_data: The structure returned by ``ReportMode.process_transactions``.

        Returns:
            Text ready to write to the terminal. Never writes to stdout itself, so
            that formatting can be asserted in tests without capturing output.
        """
        ...


@runtime_checkable
class ReportRegistry(Protocol):
    """Interface for looking up report strategies by name.

    This is the single component that must change when a report type is added, and
    the seam at which explicit registration could later be swapped for runtime
    plugin discovery.
    """

    def available_modes(self) -> List[str]:
        """Return the registered mode names, for use in CLI help and error messages."""
        ...

    def create(self, mode_name: str) -> ReportMode:
        """Instantiate the strategy registered under ``mode_name``.

        Args:
            mode_name: Identifier supplied by the user on the command line.

        Returns:
            A ready-to-use report strategy.

        Raises:
            ReportModeNotFoundError: If no strategy is registered under that name.
        """
        ...
