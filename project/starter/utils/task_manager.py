"""
Task management with validated CRUD operations.

This module holds the application's core data model. It deliberately knows
nothing about sorting, exporting, undo, or the command line; those concerns
live in their own modules so that each can be tested and changed in isolation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

VALID_PRIORITIES = ("low", "medium", "high")


class TaskManager:
    """An in-memory store of tasks with validation and serialization.

    Attributes:
        VALID_PRIORITIES: The priority values a task is allowed to take.
    """

    def __init__(self) -> None:
        self._tasks: List[Dict[str, Any]] = []
        self._next_id: int = 1

    def add_task(self, description: str, priority: str = "medium") -> int:
        """Add a new task.

        Args:
            description: Human-readable text describing the task. Leading and
                trailing whitespace is stripped.
            priority: One of ``VALID_PRIORITIES``. Case-insensitive.

        Returns:
            The ID assigned to the new task.

        Raises:
            ValueError: If the description is empty or the priority is invalid.
        """
        cleaned = description.strip()
        if not cleaned:
            raise ValueError("Task description must not be empty")

        normalized = priority.strip().lower()
        if normalized not in VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority '{priority}'. "
                f"Expected one of: {', '.join(VALID_PRIORITIES)}"
            )

        task_id = self._next_id
        task: Dict[str, Any] = {
            "id": task_id,
            "description": cleaned,
            "priority": normalized,
            "completed": False,
            "created_at": datetime.now().isoformat(),
        }
        self._tasks.append(task)
        self._next_id += 1
        return task_id

    def get_task(self, task_id: int) -> Dict[str, Any]:
        """Return the task with the given ID.

        Raises:
            ValueError: If no task has that ID.
        """
        for task in self._tasks:
            if task["id"] == task_id:
                return task
        raise ValueError(f"Task with ID {task_id} not found")

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Return a shallow copy of the task list."""
        return self._tasks.copy()

    def complete_task(self, task_id: int) -> None:
        """Mark a task as completed and stamp the completion time.

        Raises:
            ValueError: If no task has that ID.
        """
        task = self.get_task(task_id)
        task["completed"] = True
        task["completed_at"] = datetime.now().isoformat()

    def reopen_task(self, task_id: int) -> None:
        """Mark a completed task as not completed, clearing its timestamp.

        Raises:
            ValueError: If no task has that ID.
        """
        task = self.get_task(task_id)
        task["completed"] = False
        task.pop("completed_at", None)

    def index_of(self, task_id: int) -> int:
        """Return the list position of a task, for callers that must restore it.

        Raises:
            ValueError: If no task has that ID.
        """
        for index, task in enumerate(self._tasks):
            if task["id"] == task_id:
                return index
        raise ValueError(f"Task with ID {task_id} not found")

    def delete_task(self, task_id: int) -> Dict[str, Any]:
        """Delete a task and return it, so the caller can undo the deletion.

        Raises:
            ValueError: If no task has that ID.
        """
        index = self.index_of(task_id)
        return self._tasks.pop(index)

    def insert_task(self, task: Dict[str, Any], index: Optional[int] = None) -> None:
        """Re-insert a previously removed task at its original position.

        This exists to support undo. It does not assign a new ID, because the
        point is to restore the task exactly as it was.

        Args:
            task: The task dictionary to restore.
            index: Where to place it. Appends when omitted.

        Raises:
            ValueError: If a task with the same ID is already present.
        """
        if any(existing["id"] == task["id"] for existing in self._tasks):
            raise ValueError(f"Task with ID {task['id']} already exists")

        if index is None:
            self._tasks.append(task)
        else:
            self._tasks.insert(index, task)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary suitable for JSON serialization."""
        return {"tasks": self._tasks, "next_id": self._next_id}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskManager":
        """Rebuild a TaskManager from ``to_dict`` output.

        Unknown or missing keys degrade gracefully to an empty manager, so a
        missing or truncated save file does not crash the application.
        """
        manager = cls()
        tasks = data.get("tasks") or []
        if not isinstance(tasks, list):
            return manager

        manager._tasks = [task for task in tasks if isinstance(task, dict)]
        highest = max((task.get("id", 0) for task in manager._tasks), default=0)
        stored_next = data.get("next_id")
        # Trust the stored counter only if it cannot collide with an existing ID.
        if isinstance(stored_next, int) and stored_next > highest:
            manager._next_id = stored_next
        else:
            manager._next_id = highest + 1
        return manager
