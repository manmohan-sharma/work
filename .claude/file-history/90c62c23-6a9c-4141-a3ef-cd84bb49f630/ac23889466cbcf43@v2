"""
Report generation orchestrator.

Coordinates the two collaborators needed to turn a data file into a report:
a loader (reads and validates transactions) and a report mode (analyses and
formats them). The engine owns no analysis logic of its own -- it wires the
two together, which keeps each piece independently testable.
"""

from typing import Any, Dict


class ReportEngine:
    """Turns a transaction file into a report using a pluggable strategy."""

    def __init__(self, loader):
        """
        Args:
            loader: Any object exposing ``load(source)`` and returning a list
                of transactions. Duck-typed rather than annotated so tests can
                substitute a Mock without importing the real loader.
        """
        self.loader = loader

    def generate_report(self, filepath: str, mode) -> Dict[str, Any]:
        """
        Load a transaction file and process it with the given report mode.

        Args:
            filepath: Path handed straight to the loader.
            mode: Any object exposing ``process_transactions(transactions)``.

        Returns:
            Whatever the mode produces, returned unmodified.

        Raises:
            Nothing of its own. Failures from the loader (missing file, invalid
            data) and from the mode (empty dataset) propagate to the caller
            untouched, so the originating error keeps its context.
        """
        transactions = self.loader.load(filepath)
        return mode.process_transactions(transactions)
