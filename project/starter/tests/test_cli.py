"""
Unit tests for the command-line interface.

Uses Click's CliRunner so the entry point is exercised the way a user would
run it, including the interactive shell, rather than left untested.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from main import cli, render_tasks


@pytest.fixture
def data_dir():
    """A temporary data directory removed after each test."""
    path = Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def runner():
    """Click's test runner."""
    return CliRunner()


def invoke(runner, data_dir, *args, stdin=None):
    """Run the CLI against an isolated data directory."""
    return runner.invoke(cli, ["--data-dir", str(data_dir), *args], input=stdin)


class TestRenderTasks:
    """The table renderer handles empty and populated task lists."""

    def test_empty_list_renders_a_friendly_message(self):
        assert render_tasks([]) == "No tasks match."

    def test_pending_and_completed_tasks_render_different_markers(self):
        output = render_tasks(
            [
                {"id": 1, "description": "A", "priority": "high", "completed": False},
                {"id": 2, "description": "B", "priority": "low", "completed": True},
            ]
        )
        assert "[ ]" in output and "[done]" in output

    def test_task_with_missing_keys_renders_without_crashing(self):
        assert "?" in render_tasks([{}])


class TestAddCommand:
    """Adding tasks through the CLI."""

    def test_add_reports_the_new_task_id(self, runner, data_dir):
        result = invoke(runner, data_dir, "add", "Write tests")
        assert result.exit_code == 0
        assert "Added task 1" in result.output

    def test_add_persists_the_task_to_disk(self, runner, data_dir):
        invoke(runner, data_dir, "add", "Write tests", "--priority", "high")
        saved = json.loads((data_dir / "tasks.json").read_text(encoding="utf-8"))
        assert saved["tasks"][0]["priority"] == "high"

    def test_invalid_priority_is_rejected_by_click(self, runner, data_dir):
        result = invoke(runner, data_dir, "add", "Task", "--priority", "urgent")
        assert result.exit_code != 0

    def test_empty_description_is_reported_as_an_error(self, runner, data_dir):
        result = invoke(runner, data_dir, "add", "   ")
        assert result.exit_code != 0
        assert "must not be empty" in result.output


class TestListCommand:
    """Listing, sorting, and filtering through the CLI."""

    def test_list_with_no_tasks_reports_no_matches(self, runner, data_dir):
        assert "No tasks match." in invoke(runner, data_dir, "list").output

    def test_list_sorts_by_priority_by_default(self, runner, data_dir):
        invoke(runner, data_dir, "add", "Low one", "--priority", "low")
        invoke(runner, data_dir, "add", "High one", "--priority", "high")
        output = invoke(runner, data_dir, "list").output
        assert output.index("High one") < output.index("Low one")

    def test_list_filters_by_status(self, runner, data_dir):
        invoke(runner, data_dir, "add", "Pending one")
        invoke(runner, data_dir, "add", "Done one")
        invoke(runner, data_dir, "complete", "2")
        output = invoke(runner, data_dir, "list", "--status", "pending").output
        assert "Pending one" in output and "Done one" not in output

    def test_list_filters_by_keyword(self, runner, data_dir):
        invoke(runner, data_dir, "add", "Write the report")
        invoke(runner, data_dir, "add", "Buy milk")
        output = invoke(runner, data_dir, "list", "--keyword", "milk").output
        assert "Buy milk" in output and "report" not in output

    def test_list_accepts_an_alternative_sort(self, runner, data_dir):
        invoke(runner, data_dir, "add", "Zebra")
        invoke(runner, data_dir, "add", "Apple")
        output = invoke(runner, data_dir, "list", "--sort", "description").output
        assert output.index("Apple") < output.index("Zebra")


class TestCompleteAndDeleteCommands:
    """State-changing commands and their failure paths."""

    def test_complete_marks_the_task_done(self, runner, data_dir):
        invoke(runner, data_dir, "add", "Finish me")
        result = invoke(runner, data_dir, "complete", "1")
        assert "Completed task 1" in result.output
        assert "[done]" in invoke(runner, data_dir, "list").output

    def test_delete_removes_the_task(self, runner, data_dir):
        invoke(runner, data_dir, "add", "Delete me")
        invoke(runner, data_dir, "delete", "1")
        assert "No tasks match." in invoke(runner, data_dir, "list").output

    def test_completing_a_missing_task_fails_cleanly(self, runner, data_dir):
        result = invoke(runner, data_dir, "complete", "99")
        assert result.exit_code != 0
        assert "Task with ID 99 not found" in result.output

    def test_deleting_a_missing_task_fails_cleanly(self, runner, data_dir):
        result = invoke(runner, data_dir, "delete", "99")
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_non_numeric_id_is_rejected_by_click(self, runner, data_dir):
        assert invoke(runner, data_dir, "complete", "abc").exit_code != 0


class TestExportCommand:
    """Exporting through the CLI."""

    def test_export_writes_the_default_filename(self, runner, data_dir):
        invoke(runner, data_dir, "add", "Task")
        result = invoke(runner, data_dir, "export", "csv")
        assert result.exit_code == 0
        assert (data_dir / "tasks.csv").exists()

    def test_export_honours_a_custom_output_name(self, runner, data_dir):
        invoke(runner, data_dir, "add", "Task")
        invoke(runner, data_dir, "export", "json", "--output", "custom.json")
        assert (data_dir / "custom.json").exists()

    def test_unsupported_format_is_rejected_by_click(self, runner, data_dir):
        assert invoke(runner, data_dir, "export", "xml").exit_code != 0


class TestPersistence:
    """Tasks survive across separate CLI invocations."""

    def test_tasks_reload_from_disk(self, runner, data_dir):
        invoke(runner, data_dir, "add", "Persisted task")
        assert "Persisted task" in invoke(runner, data_dir, "list").output

    def test_ids_continue_after_a_reload(self, runner, data_dir):
        invoke(runner, data_dir, "add", "First")
        result = invoke(runner, data_dir, "add", "Second")
        assert "Added task 2" in result.output

    def test_corrupt_save_file_does_not_crash_the_cli(self, runner, data_dir):
        """A truncated file should degrade to an empty list, not a traceback."""
        (data_dir / "tasks.json").write_text('{"tasks": "not-a-list"}')
        result = invoke(runner, data_dir, "list")
        assert result.exit_code == 0
        assert "No tasks match." in result.output


class TestInteractiveShell:
    """The shell is where undo and redo are meaningful."""

    def test_shell_greets_and_exits_on_quit(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin="quit\n")
        assert result.exit_code == 0
        assert "Task Manager." in result.output
        assert "Goodbye." in result.output

    def test_shell_adds_and_lists_tasks(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin="add Buy milk\nlist\nquit\n")
        assert "Added task 1" in result.output
        assert "Buy milk" in result.output

    def test_shell_treats_a_trailing_priority_word_as_the_priority(
        self, runner, data_dir
    ):
        result = invoke(runner, data_dir, stdin="add Write the report high\nquit\n")
        assert "Added task 1: Write the report" in result.output
        saved = json.loads((data_dir / "tasks.json").read_text(encoding="utf-8"))
        assert saved["tasks"][0]["priority"] == "high"

    def test_shell_keeps_a_non_priority_last_word_in_the_description(
        self, runner, data_dir
    ):
        result = invoke(runner, data_dir, stdin="add Buy milk\nquit\n")
        assert "Added task 1: Buy milk" in result.output

    def test_shell_undo_reverses_the_last_change(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin="add Task\nundo\nlist\nquit\n")
        assert "Undid: add task 'Task'" in result.output
        assert "No tasks match." in result.output

    def test_shell_redo_reapplies_an_undone_change(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin="add Task\nundo\nredo\nlist\nquit\n")
        assert "Redid:" in result.output
        assert "Task" in result.output

    def test_shell_undo_restores_a_deleted_task_in_place(self, runner, data_dir):
        stdin = "add First\nadd Second\ndelete 1\nundo\nlist\nquit\n"
        output = invoke(runner, data_dir, stdin=stdin).output
        assert output.index("First") < output.index("Second")

    def test_shell_undo_with_empty_history_reports_an_error(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin="undo\nquit\n")
        assert "Nothing to undo" in result.output

    def test_shell_reports_unknown_commands(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin="bogus\nquit\n")
        assert "Unknown command 'bogus'" in result.output

    def test_shell_reports_a_non_numeric_id(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin="complete abc\nquit\n")
        assert "must be a number" in result.output

    def test_shell_reports_missing_arguments(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin="add\ndelete\nexport\nquit\n")
        assert result.output.count("Usage:") == 3

    def test_shell_ignores_blank_lines(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin="\n   \nquit\n")
        assert result.exit_code == 0

    def test_shell_reports_unbalanced_quotes(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin='add "unclosed\nquit\n')
        assert "could not parse input" in result.output

    def test_shell_help_lists_the_commands(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin="help\nquit\n")
        assert "undo / redo" in result.output

    def test_shell_list_accepts_sort_and_filter_arguments(self, runner, data_dir):
        stdin = (
            "add Zebra low\nadd Apple high\n"
            "list description\nlist priority=high\nlist keyword=zeb\nquit\n"
        )
        result = invoke(runner, data_dir, stdin=stdin)
        assert result.exit_code == 0
        assert "Apple" in result.output

    def test_shell_export_writes_a_file(self, runner, data_dir):
        invoke(runner, data_dir, stdin="add Task\nexport json report.json\nquit\n")
        assert (data_dir / "report.json").exists()

    def test_shell_saves_on_exit(self, runner, data_dir):
        invoke(runner, data_dir, stdin="add Persisted\nquit\n")
        assert "Persisted" in invoke(runner, data_dir, "list").output

    def test_shell_exits_cleanly_when_input_ends_without_quit(self, runner, data_dir):
        result = invoke(runner, data_dir, stdin="add Task\n")
        assert result.exit_code == 0


class TestExportPathSafety:
    """Export filenames must not escape the data directory."""

    def test_export_rejects_a_traversing_output_name(self, runner, data_dir):
        invoke(runner, data_dir, "add", "Task")
        result = invoke(
            runner, data_dir, "export", "json", "--output", "../escaped.json"
        )
        assert result.exit_code != 0
        assert "must stay inside the data directory" in result.output
        assert not (data_dir.parent / "escaped.json").exists()

    def test_shell_export_rejects_a_traversing_filename(self, runner, data_dir):
        result = invoke(
            runner, data_dir, stdin="add Task\nexport json ../escaped.json\nquit\n"
        )
        assert "must stay inside the data directory" in result.output
        assert not (data_dir.parent / "escaped.json").exists()
