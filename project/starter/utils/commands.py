"""
Undoable task operations.

Implements the Command pattern. Each mutating operation is an object that
knows how to perform itself and how to reverse itself, which is what makes
undo and redo possible without the TaskManager needing to track history.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from utils.task_manager import TaskManager


class Command(ABC):
    """Interface for a reversible operation on a TaskManager."""

    @abstractmethod
    def execute(self) -> None:
        """Perform the operation."""

    @abstractmethod
    def undo(self) -> None:
        """Reverse the operation, restoring the prior state."""

    @abstractmethod
    def describe(self) -> str:
        """Return a short human-readable label, for CLI feedback."""


class AddTaskCommand(Command):
    """Add a task; undo deletes it again."""

    def __init__(
        self, manager: TaskManager, description: str, priority: str = "medium"
    ) -> None:
        self._manager = manager
        self._description = description
        self._priority = priority
        self._task_id: Optional[int] = None

    def execute(self) -> None:
        self._task_id = self._manager.add_task(self._description, self._priority)

    def undo(self) -> None:
        if self._task_id is not None:
            self._manager.delete_task(self._task_id)
            self._task_id = None

    def describe(self) -> str:
        return f"add task '{self._description}'"

    @property
    def task_id(self) -> Optional[int]:
        """The ID assigned on execute, or None before it runs."""
        return self._task_id


class CompleteTaskCommand(Command):
    """Complete a task; undo restores its previous completion state."""

    def __init__(self, manager: TaskManager, task_id: int) -> None:
        self._manager = manager
        self._task_id = task_id
        self._was_completed: bool = False
        self._previous_completed_at: Optional[str] = None

    def execute(self) -> None:
        # Snapshot before mutating, so undo can restore an already-complete
        # task rather than wrongly reopening it.
        task = self._manager.get_task(self._task_id)
        self._was_completed = bool(task.get("completed", False))
        self._previous_completed_at = task.get("completed_at")
        self._manager.complete_task(self._task_id)

    def undo(self) -> None:
        if self._was_completed:
            task = self._manager.get_task(self._task_id)
            task["completed"] = True
            if self._previous_completed_at is not None:
                task["completed_at"] = self._previous_completed_at
        else:
            self._manager.reopen_task(self._task_id)

    def describe(self) -> str:
        return f"complete task {self._task_id}"


class DeleteTaskCommand(Command):
    """Delete a task; undo restores it at its original position."""

    def __init__(self, manager: TaskManager, task_id: int) -> None:
        self._manager = manager
        self._task_id = task_id
        self._deleted_task: Optional[Dict[str, Any]] = None
        self._index: Optional[int] = None

    def execute(self) -> None:
        self._index = self._manager.index_of(self._task_id)
        self._deleted_task = self._manager.delete_task(self._task_id)

    def undo(self) -> None:
        if self._deleted_task is not None:
            self._manager.insert_task(self._deleted_task, self._index)
            self._deleted_task = None

    def describe(self) -> str:
        return f"delete task {self._task_id}"


class CommandHistory:
    """Invoker that runs commands and maintains undo and redo stacks."""

    def __init__(self) -> None:
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []

    def execute(self, command: Command) -> None:
        """Run a command and record it.

        A newly executed command invalidates the redo stack, matching the
        behaviour users expect from editors.
        """
        command.execute()
        self._undo_stack.append(command)
        self._redo_stack.clear()

    def undo(self) -> str:
        """Reverse the most recent command.

        Returns:
            A description of what was undone.

        Raises:
            IndexError: If there is nothing left to undo.
        """
        if not self._undo_stack:
            raise IndexError("Nothing to undo")
        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)
        return command.describe()

    def redo(self) -> str:
        """Re-run the most recently undone command.

        Returns:
            A description of what was redone.

        Raises:
            IndexError: If there is nothing left to redo.
        """
        if not self._redo_stack:
            raise IndexError("Nothing to redo")
        command = self._redo_stack.pop()
        command.execute()
        self._undo_stack.append(command)
        return command.describe()

    @property
    def can_undo(self) -> bool:
        """True if at least one command can be undone."""
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        """True if at least one command can be redone."""
        return bool(self._redo_stack)
