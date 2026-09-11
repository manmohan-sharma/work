"""
Unit tests for the export factory and its exporters.

Covers the factory's lookup and error path, the content each exporter
produces, and edge cases such as empty exports and awkward characters.
"""

import csv
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from utils.exporters import (
    EXPORT_CHOICES,
    CSVExporter,
    ExporterFactory,
    JSONExporter,
    MarkdownExporter,
)


@pytest.fixture
def temp_dir():
    """A temporary directory removed after each test."""
    path = Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def tasks():
    """Two tasks covering both completion states."""
    return [
        {
            "id": 1,
            "description": "Write tests",
            "priority": "high",
            "completed": False,
            "created_at": "2026-01-01T00:00:00",
        },
        {
            "id": 2,
            "description": "Ship it",
            "priority": "low",
            "completed": True,
            "created_at": "2026-01-02T00:00:00",
        },
    ]


class TestExporterFactory:
    """The factory maps format names to exporter instances."""

    @pytest.mark.parametrize("name", EXPORT_CHOICES)
    def test_every_advertised_format_can_be_created(self, name):
        assert ExporterFactory.create(name) is not None

    def test_create_returns_the_matching_exporter_type(self):
        assert isinstance(ExporterFactory.create("json"), JSONExporter)
        assert isinstance(ExporterFactory.create("csv"), CSVExporter)
        assert isinstance(ExporterFactory.create("markdown"), MarkdownExporter)

    def test_create_normalizes_case_and_whitespace(self):
        assert isinstance(ExporterFactory.create("  JSON "), JSONExporter)

    def test_unsupported_format_raises_listing_valid_options(self):
        with pytest.raises(ValueError, match="Unsupported format 'xml'"):
            ExporterFactory.create("xml")

    def test_each_exporter_declares_a_file_extension(self):
        for name in EXPORT_CHOICES:
            assert ExporterFactory.create(name).extension


class TestJSONExporter:
    """JSON export round-trips the task data."""

    def test_export_writes_readable_json(self, temp_dir, tasks):
        target = temp_dir / "out.json"
        JSONExporter().export(tasks, target)
        assert json.loads(target.read_text(encoding="utf-8")) == tasks

    def test_export_of_empty_list_writes_empty_array(self, temp_dir):
        target = temp_dir / "out.json"
        JSONExporter().export([], target)
        assert json.loads(target.read_text(encoding="utf-8")) == []

    def test_unwritable_path_raises_runtime_error(self, temp_dir, tasks):
        with pytest.raises(RuntimeError, match="Failed to export JSON"):
            JSONExporter().export(tasks, temp_dir / "missing" / "out.json")


class TestCSVExporter:
    """CSV export always produces a header and one row per task."""

    def test_export_writes_header_and_rows(self, temp_dir, tasks):
        target = temp_dir / "out.csv"
        CSVExporter().export(tasks, target)
        with open(target, newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        assert len(rows) == 2
        assert rows[0]["description"] == "Write tests"
        assert rows[1]["completed"] == "True"

    def test_empty_export_still_writes_a_header(self, temp_dir):
        """An empty CSV without a header would be unreadable by consumers."""
        target = temp_dir / "out.csv"
        CSVExporter().export([], target)
        assert target.read_text(encoding="utf-8").strip() == (
            "id,description,priority,completed,created_at"
        )

    def test_task_with_missing_keys_does_not_produce_a_ragged_row(self, temp_dir):
        target = temp_dir / "out.csv"
        CSVExporter().export([{"id": 7}], target)
        with open(target, newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        assert rows[0]["id"] == "7"
        assert rows[0]["priority"] == ""

    def test_unwritable_path_raises_runtime_error(self, temp_dir, tasks):
        with pytest.raises(RuntimeError, match="Failed to export CSV"):
            CSVExporter().export(tasks, temp_dir / "missing" / "out.csv")


class TestMarkdownExporter:
    """Markdown export produces a valid table."""

    def test_export_writes_a_table_with_divider(self, temp_dir, tasks):
        target = temp_dir / "out.md"
        MarkdownExporter().export(tasks, target)
        lines = target.read_text(encoding="utf-8").strip().split("\n")
        assert lines[0].startswith("| id |")
        assert set(lines[1]) <= set("| -")
        assert len(lines) == 4

    def test_pipe_in_description_is_escaped(self, temp_dir):
        """An unescaped pipe would silently break the table layout."""
        target = temp_dir / "out.md"
        MarkdownExporter().export([{"id": 1, "description": "a | b"}], target)
        assert "a \\| b" in target.read_text(encoding="utf-8")

    def test_empty_export_still_writes_a_header(self, temp_dir):
        target = temp_dir / "out.md"
        MarkdownExporter().export([], target)
        assert len(target.read_text(encoding="utf-8").strip().split("\n")) == 2

    def test_unwritable_path_raises_runtime_error(self, temp_dir, tasks):
        with pytest.raises(RuntimeError, match="Failed to export Markdown"):
            MarkdownExporter().export(tasks, temp_dir / "missing" / "out.md")
