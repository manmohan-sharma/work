"""
Sorting and filtering strategies for tasks.

Implements the Strategy pattern. Each ordering and each filter is its own
small class behind a common interface, so the CLI can select one at runtime
without a growing chain of if/elif branches, and new orderings can be added
without touching existing code.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List

from utils.task_manager import VALID_PRIORITIES

# Rank priorities so that "high" sorts above "medium" above "low".
_PRIORITY_RANK: Dict[str, int] = {
    name: rank for rank, name in enumerate(VALID_PRIORITIES)
}


class SortStrategy(ABC):
    """Interface for an ordering that can be applied to a list of tasks."""

    @abstractmethod
    def sort(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return a new list of tasks in this strategy's order."""


class PrioritySort(SortStrategy):
    """Order by priority, highest first, then by ID for a stable tie-break."""

    def sort(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            tasks,
            key=lambda task: (
                -_PRIORITY_RANK.get(task.get("priority", ""), -1),
                task.get("id", 0),
            ),
        )


class CreatedDateSort(SortStrategy):
    """Order by creation time, oldest first."""

    def sort(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(tasks, key=lambda task: str(task.get("created_at", "")))


class DescriptionSort(SortStrategy):
    """Order alphabetically by description, case-insensitively."""

    def sort(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(tasks, key=lambda task: str(task.get("description", "")).lower())


class FilterStrategy(ABC):
    """Interface for a predicate that selects a subset of tasks."""

    @abstractmethod
    def matches(self, task: Dict[str, Any]) -> bool:
        """Return True if the task belongs in the filtered result."""

    def filter(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply this filter across a list of tasks."""
        return [task for task in tasks if self.matches(task)]


class StatusFilter(FilterStrategy):
    """Keep only tasks whose completion state matches ``completed``."""

    def __init__(self, completed: bool) -> None:
        self._completed = completed

    def matches(self, task: Dict[str, Any]) -> bool:
        return bool(task.get("completed", False)) is self._completed


class PriorityFilter(FilterStrategy):
    """Keep only tasks of a given priority.

    Raises:
        ValueError: If the priority is not a recognised value.
    """

    def __init__(self, priority: str) -> None:
        normalized = priority.strip().lower()
        if normalized not in VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority '{priority}'. "
                f"Expected one of: {', '.join(VALID_PRIORITIES)}"
            )
        self._priority = normalized

    def matches(self, task: Dict[str, Any]) -> bool:
        return str(task.get("priority", "")) == self._priority


class KeywordFilter(FilterStrategy):
    """Keep tasks whose description contains a keyword, ignoring case."""

    def __init__(self, keyword: str) -> None:
        self._keyword = keyword.strip().lower()

    def matches(self, task: Dict[str, Any]) -> bool:
        if not self._keyword:
            return True
        return self._keyword in str(task.get("description", "")).lower()


class TaskQuery:
    """Context object that applies an optional filter chain then an ordering.

    Filters are combined with AND. Both the filters and the ordering can be
    swapped at runtime, which is the point of the Strategy pattern here.
    """

    def __init__(self, sort_strategy: SortStrategy) -> None:
        self._sort_strategy = sort_strategy
        self._filters: List[FilterStrategy] = []

    def set_sort_strategy(self, sort_strategy: SortStrategy) -> "TaskQuery":
        """Replace the ordering. Returns self so calls can be chained."""
        self._sort_strategy = sort_strategy
        return self

    def add_filter(self, filter_strategy: FilterStrategy) -> "TaskQuery":
        """Add a filter to the chain. Returns self so calls can be chained."""
        self._filters.append(filter_strategy)
        return self

    def apply(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter then sort, leaving the input list untouched."""
        result = list(tasks)
        for filter_strategy in self._filters:
            result = filter_strategy.filter(result)
        return self._sort_strategy.sort(result)


_SORT_STRATEGIES: Dict[str, Callable[[], SortStrategy]] = {
    "priority": PrioritySort,
    "created": CreatedDateSort,
    "description": DescriptionSort,
}

SORT_CHOICES = tuple(_SORT_STRATEGIES)


def get_sort_strategy(name: str) -> SortStrategy:
    """Look up a sort strategy by name, for the CLI to resolve user input.

    Raises:
        ValueError: If the name is not a known strategy.
    """
    factory = _SORT_STRATEGIES.get(name.strip().lower())
    if factory is None:
        raise ValueError(
            f"Unknown sort '{name}'. Expected one of: {', '.join(SORT_CHOICES)}"
        )
    return factory()
