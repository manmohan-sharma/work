"""
Unit tests for the command objects and the undo/redo history.

Covers each command's execute and undo behaviour, the stack semantics of
CommandHistory, and the edge cases where naive undo implementations break.
"""

import pytest

from utils.commands import (
    AddTaskCommand,
    CommandHistory,
    CompleteTaskCommand,
    DeleteTaskCommand,
)
from utils.task_manager import TaskManager


@pytest.fixture
def manager():
    """An empty TaskManager."""
    return TaskManager()


@pytest.fixture
def history():
    """An empty command history."""
    return CommandHistory()


class TestAddTaskCommand:
    """Adding a task is reversed by deleting it."""

    def test_execute_adds_the_task(self, manager):
        command = AddTaskCommand(manager, "Write tests", "high")
        command.execute()
        assert len(manager.get_all_tasks()) == 1
        assert manager.get_task(command.task_id)["description"] == "Write tests"

    def test_undo_removes_the_task(self, manager):
        command = AddTaskCommand(manager, "Write tests")
        command.execute()
        command.undo()
        assert manager.get_all_tasks() == []

    def test_undo_before_execute_is_a_no_op(self, manager):
        AddTaskCommand(manager, "Never run").undo()
        assert manager.get_all_tasks() == []

    def test_invalid_priority_propagates_from_the_manager(self, manager):
        with pytest.raises(ValueError, match="Invalid priority"):
            AddTaskCommand(manager, "Bad", "urgent").execute()

    def test_describe_mentions_the_description(self, manager):
        assert "Write tests" in AddTaskCommand(manager, "Write tests").describe()


class TestCompleteTaskCommand:
    """Completing a task is reversed by restoring its prior state."""

    def test_execute_marks_the_task_complete(self, manager):
        task_id = manager.add_task("Finish me")
        CompleteTaskCommand(manager, task_id).execute()
        assert manager.get_task(task_id)["completed"] is True

    def test_undo_reopens_a_previously_pending_task(self, manager):
        task_id = manager.add_task("Finish me")
        command = CompleteTaskCommand(manager, task_id)
        command.execute()
        command.undo()
        task = manager.get_task(task_id)
        assert task["completed"] is False
        assert "completed_at" not in task

    def test_undo_leaves_an_already_completed_task_completed(self, manager):
        """Undo must restore the prior state, not blindly reopen the task."""
        task_id = manager.add_task("Already done")
        manager.complete_task(task_id)
        original_timestamp = manager.get_task(task_id)["completed_at"]

        command = CompleteTaskCommand(manager, task_id)
        command.execute()
        command.undo()

        task = manager.get_task(task_id)
        assert task["completed"] is True
        assert task["completed_at"] == original_timestamp

    def test_execute_on_missing_task_raises(self, manager):
        with pytest.raises(ValueError, match="Task with ID 99 not found"):
            CompleteTaskCommand(manager, 99).execute()


class TestDeleteTaskCommand:
    """Deleting a task is reversed by restoring it where it was."""

    def test_execute_removes_the_task(self, manager):
        task_id = manager.add_task("Delete me")
        DeleteTaskCommand(manager, task_id).execute()
        assert manager.get_all_tasks() == []

    def test_undo_restores_the_task_with_its_original_data(self, manager):
        task_id = manager.add_task("Delete me", "high")
        command = DeleteTaskCommand(manager, task_id)
        command.execute()
        command.undo()
        restored = manager.get_task(task_id)
        assert restored["description"] == "Delete me"
        assert restored["priority"] == "high"

    def test_undo_restores_the_task_to_its_original_position(self, manager):
        """Appending on undo would silently reorder the user's list."""
        first = manager.add_task("First")
        manager.add_task("Second")
        manager.add_task("Third")

        command = DeleteTaskCommand(manager, first)
        command.execute()
        command.undo()

        assert [task["id"] for task in manager.get_all_tasks()] == [first, 2, 3]

    def test_execute_on_missing_task_raises(self, manager):
        with pytest.raises(ValueError, match="Task with ID 42 not found"):
            DeleteTaskCommand(manager, 42).execute()


class TestCommandHistory:
    """The invoker maintains undo and redo stacks."""

    def test_execute_runs_the_command_and_enables_undo(self, manager, history):
        history.execute(AddTaskCommand(manager, "Task"))
        assert len(manager.get_all_tasks()) == 1
        assert history.can_undo is True
        assert history.can_redo is False

    def test_undo_then_redo_restores_the_change(self, manager, history):
        history.execute(AddTaskCommand(manager, "Task"))
        history.undo()
        assert manager.get_all_tasks() == []
        history.redo()
        assert len(manager.get_all_tasks()) == 1

    def test_undo_returns_a_description_of_what_was_undone(self, manager, history):
        history.execute(AddTaskCommand(manager, "Task"))
        assert "Task" in history.undo()

    def test_undo_unwinds_commands_in_reverse_order(self, manager, history):
        history.execute(AddTaskCommand(manager, "First"))
        history.execute(AddTaskCommand(manager, "Second"))
        history.undo()
        remaining = [task["description"] for task in manager.get_all_tasks()]
        assert remaining == ["First"]

    def test_new_command_clears_the_redo_stack(self, manager, history):
        """Redoing after a divergent edit would reapply an abandoned branch."""
        history.execute(AddTaskCommand(manager, "First"))
        history.undo()
        assert history.can_redo is True

        history.execute(AddTaskCommand(manager, "Second"))
        assert history.can_redo is False
        with pytest.raises(IndexError, match="Nothing to redo"):
            history.redo()

    def test_undo_on_empty_history_raises(self, history):
        with pytest.raises(IndexError, match="Nothing to undo"):
            history.undo()

    def test_redo_on_empty_history_raises(self, history):
        with pytest.raises(IndexError, match="Nothing to redo"):
            history.redo()

    def test_full_undo_of_a_mixed_sequence_returns_to_the_start(self, manager, history):
        add = AddTaskCommand(manager, "Task", "low")
        history.execute(add)
        task_id = add.task_id
        assert task_id is not None
        history.execute(CompleteTaskCommand(manager, task_id))
        history.execute(DeleteTaskCommand(manager, task_id))

        while history.can_undo:
            history.undo()

        assert manager.get_all_tasks() == []
