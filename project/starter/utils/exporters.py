"""
Export tasks to different file formats.

Implements the Factory pattern. The caller names a format and receives an
exporter that satisfies a common interface, so adding a format means adding
one class and one registry entry rather than editing every call site.
"""

import csv
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Type

# Columns written by the tabular exporters, in display order. Fixed rather than
# derived from the data so that an empty export still produces a valid header,
# and so that tasks with differing keys cannot produce ragged rows.
_COLUMNS = ("id", "description", "priority", "completed", "created_at")


class DataExporter(ABC):
    """Interface for writing a list of tasks to a file."""

    #: File extension this exporter produces, without the leading dot.
    extension: str = ""

    @abstractmethod
    def export(self, tasks: List[Dict[str, Any]], filepath: Path) -> None:
        """Write ``tasks`` to ``filepath``.

        Raises:
            RuntimeError: If the file cannot be written.
        """

    @staticmethod
    def _rows(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Project tasks onto the fixed column set, filling gaps with ''."""
        return [{column: task.get(column, "") for column in _COLUMNS} for task in tasks]


class JSONExporter(DataExporter):
    """Write tasks as a JSON array."""

    extension = "json"

    def export(self, tasks: List[Dict[str, Any]], filepath: Path) -> None:
        try:
            with open(filepath, "w", encoding="utf-8") as file:
                json.dump(tasks, file, indent=2, ensure_ascii=False)
        except (IOError, TypeError) as error:
            raise RuntimeError(f"Failed to export JSON to {filepath}: {error}")


class CSVExporter(DataExporter):
    """Write tasks as CSV, always including a header row."""

    extension = "csv"

    def export(self, tasks: List[Dict[str, Any]], filepath: Path) -> None:
        try:
            with open(filepath, "w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(_COLUMNS))
                writer.writeheader()
                writer.writerows(self._rows(tasks))
        except (IOError, csv.Error) as error:
            raise RuntimeError(f"Failed to export CSV to {filepath}: {error}")


class MarkdownExporter(DataExporter):
    """Write tasks as a Markdown table."""

    extension = "md"

    def export(self, tasks: List[Dict[str, Any]], filepath: Path) -> None:
        header = "| " + " | ".join(_COLUMNS) + " |"
        divider = "| " + " | ".join("---" for _ in _COLUMNS) + " |"
        lines = [header, divider]
        for row in self._rows(tasks):
            # Escape pipes so a description cannot break the table layout.
            cells = [str(row[column]).replace("|", "\\|") for column in _COLUMNS]
            lines.append("| " + " | ".join(cells) + " |")

        try:
            with open(filepath, "w", encoding="utf-8") as file:
                file.write("\n".join(lines) + "\n")
        except IOError as error:
            raise RuntimeError(f"Failed to export Markdown to {filepath}: {error}")


_EXPORTERS: Dict[str, Type[DataExporter]] = {
    "json": JSONExporter,
    "csv": CSVExporter,
    "markdown": MarkdownExporter,
}

EXPORT_CHOICES = tuple(_EXPORTERS)


class ExporterFactory:
    """Creates exporters by format name."""

    @staticmethod
    def create(format_name: str) -> DataExporter:
        """Return an exporter for ``format_name``.

        Raises:
            ValueError: If the format is not supported.
        """
        exporter_class = _EXPORTERS.get(format_name.strip().lower())
        if exporter_class is None:
            raise ValueError(
                f"Unsupported format '{format_name}'. "
                f"Expected one of: {', '.join(EXPORT_CHOICES)}"
            )
        return exporter_class()
