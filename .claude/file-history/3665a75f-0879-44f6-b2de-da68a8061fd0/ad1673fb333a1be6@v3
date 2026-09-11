"""
Unit tests for the TaskManager class.

These tests demonstrate proper testing practices and serve as
examples for students to follow when writing their own tests.
"""

import pytest

from utils.task_manager import TaskManager


class TestTaskManager:
    """Test suite for TaskManager functionality."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.task_manager = TaskManager()

    def test_add_task_returns_id(self):
        """Test that adding a task returns a valid ID."""
        task_id = self.task_manager.add_task("Test task")
        assert isinstance(task_id, int)
        assert task_id > 0

    def test_add_task_with_priority(self):
        """Test adding a task with a specific priority."""
        task_id = self.task_manager.add_task("High priority task", priority="high")
        task = self.task_manager.get_task(task_id)
        assert task["priority"] == "high"

    def test_get_task_by_id(self):
        """Test retrieving a task by its ID."""
        task_id = self.task_manager.add_task("Test task")
        task = self.task_manager.get_task(task_id)
        assert task["id"] == task_id
        assert task["description"] == "Test task"
        assert task["completed"] is False

    def test_get_nonexistent_task_raises_error(self):
        """Test that getting a non-existent task raises ValueError."""
        with pytest.raises(ValueError, match="Task with ID 999 not found"):
            self.task_manager.get_task(999)

    def test_get_all_tasks(self):
        """Test retrieving all tasks."""
        self.task_manager.add_task("Task 1")
        self.task_manager.add_task("Task 2")
        tasks = self.task_manager.get_all_tasks()
        assert len(tasks) == 2
        assert tasks[0]["description"] == "Task 1"
        assert tasks[1]["description"] == "Task 2"

    def test_complete_task(self):
        """Test marking a task as completed."""
        task_id = self.task_manager.add_task("Complete me")
        self.task_manager.complete_task(task_id)
        task = self.task_manager.get_task(task_id)
        assert task["completed"] is True
        assert "completed_at" in task

    def test_delete_task(self):
        """Test deleting a task."""
        task_id = self.task_manager.add_task("Delete me")
        self.task_manager.delete_task(task_id)
        with pytest.raises(ValueError):
            self.task_manager.get_task(task_id)

    def test_to_dict(self):
        """Test converting TaskManager to dictionary."""
        self.task_manager.add_task("Test task")
        data = self.task_manager.to_dict()
        assert "tasks" in data
        assert "next_id" in data
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["description"] == "Test task"


class TestTaskValidation:
    """Input validation added on top of the starter's CRUD operations."""

    def setup_method(self):
        self.task_manager = TaskManager()

    def test_empty_description_is_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            self.task_manager.add_task("")

    def test_whitespace_only_description_is_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            self.task_manager.add_task("   \t  ")

    def test_description_whitespace_is_stripped(self):
        task_id = self.task_manager.add_task("  Padded  ")
        assert self.task_manager.get_task(task_id)["description"] == "Padded"

    def test_invalid_priority_is_rejected_with_valid_options_listed(self):
        with pytest.raises(ValueError, match="Invalid priority 'urgent'"):
            self.task_manager.add_task("Task", priority="urgent")

    def test_priority_is_normalized_to_lowercase(self):
        task_id = self.task_manager.add_task("Task", priority="HIGH")
        assert self.task_manager.get_task(task_id)["priority"] == "high"

    @pytest.mark.parametrize("priority", ["low", "medium", "high"])
    def test_every_valid_priority_is_accepted(self, priority):
        task_id = self.task_manager.add_task("Task", priority=priority)
        assert self.task_manager.get_task(task_id)["priority"] == priority


class TestTaskRestoration:
    """Operations that exist to support undo."""

    def setup_method(self):
        self.task_manager = TaskManager()

    def test_delete_returns_the_removed_task(self):
        task_id = self.task_manager.add_task("Delete me")
        removed = self.task_manager.delete_task(task_id)
        assert removed["description"] == "Delete me"

    def test_deleting_a_missing_task_raises(self):
        """The starter deleted silently, which hid typos from the user."""
        with pytest.raises(ValueError, match="Task with ID 99 not found"):
            self.task_manager.delete_task(99)

    def test_index_of_returns_the_list_position(self):
        self.task_manager.add_task("First")
        second = self.task_manager.add_task("Second")
        assert self.task_manager.index_of(second) == 1

    def test_index_of_missing_task_raises(self):
        with pytest.raises(ValueError, match="not found"):
            self.task_manager.index_of(99)

    def test_insert_task_restores_at_a_given_position(self):
        first = self.task_manager.add_task("First")
        self.task_manager.add_task("Second")
        removed = self.task_manager.delete_task(first)
        self.task_manager.insert_task(removed, 0)
        assert [t["id"] for t in self.task_manager.get_all_tasks()] == [first, 2]

    def test_insert_task_appends_when_no_index_is_given(self):
        first = self.task_manager.add_task("First")
        removed = self.task_manager.delete_task(first)
        self.task_manager.insert_task(removed)
        assert self.task_manager.get_all_tasks()[-1]["id"] == first

    def test_insert_task_rejects_a_duplicate_id(self):
        task_id = self.task_manager.add_task("Original")
        duplicate = self.task_manager.get_task(task_id).copy()
        with pytest.raises(ValueError, match="already exists"):
            self.task_manager.insert_task(duplicate)

    def test_reopen_task_clears_completion(self):
        task_id = self.task_manager.add_task("Task")
        self.task_manager.complete_task(task_id)
        self.task_manager.reopen_task(task_id)
        task = self.task_manager.get_task(task_id)
        assert task["completed"] is False
        assert "completed_at" not in task

    def test_reopening_a_pending_task_is_harmless(self):
        task_id = self.task_manager.add_task("Task")
        self.task_manager.reopen_task(task_id)
        assert self.task_manager.get_task(task_id)["completed"] is False

    def test_reopening_a_missing_task_raises(self):
        with pytest.raises(ValueError, match="not found"):
            self.task_manager.reopen_task(99)


class TestSerialization:
    """Round-tripping through to_dict and from_dict."""

    def setup_method(self):
        self.task_manager = TaskManager()

    def test_from_dict_round_trips_to_dict(self):
        self.task_manager.add_task("First", "high")
        self.task_manager.add_task("Second", "low")
        restored = TaskManager.from_dict(self.task_manager.to_dict())
        assert restored.to_dict() == self.task_manager.to_dict()

    def test_from_dict_continues_the_id_sequence(self):
        self.task_manager.add_task("First")
        restored = TaskManager.from_dict(self.task_manager.to_dict())
        assert restored.add_task("Second") == 2

    def test_from_dict_of_empty_dict_gives_an_empty_manager(self):
        restored = TaskManager.from_dict({})
        assert restored.get_all_tasks() == []
        assert restored.add_task("First") == 1

    def test_from_dict_ignores_a_non_list_tasks_value(self):
        """A corrupt save file should degrade, not raise."""
        assert TaskManager.from_dict({"tasks": "not-a-list"}).get_all_tasks() == []

    def test_from_dict_skips_entries_that_are_not_dictionaries(self):
        restored = TaskManager.from_dict({"tasks": [{"id": 1}, "junk", None]})
        assert len(restored.get_all_tasks()) == 1

    def test_from_dict_repairs_a_next_id_that_would_collide(self):
        """Trusting a stale counter would hand out a duplicate ID."""
        restored = TaskManager.from_dict({"tasks": [{"id": 5}], "next_id": 2})
        assert restored.add_task("New") == 6

    def test_from_dict_ignores_a_non_integer_next_id(self):
        restored = TaskManager.from_dict({"tasks": [{"id": 3}], "next_id": "four"})
        assert restored.add_task("New") == 4
