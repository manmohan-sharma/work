"""
Unit tests for the sorting and filtering strategies.

Covers each strategy's ordering, the filter predicates, the chaining
behaviour of TaskQuery, and the error paths for invalid user input.
"""

import pytest

from utils.sorting import (
    SORT_CHOICES,
    CreatedDateSort,
    DescriptionSort,
    KeywordFilter,
    PriorityFilter,
    PrioritySort,
    StatusFilter,
    TaskQuery,
    get_sort_strategy,
)


def make_task(
    task_id,
    description="task",
    priority="medium",
    completed=False,
    created_at="2026-01-01T00:00:00",
):
    """Build a task dictionary for use as test data."""
    return {
        "id": task_id,
        "description": description,
        "priority": priority,
        "completed": completed,
        "created_at": created_at,
    }


@pytest.fixture
def tasks():
    """Three tasks that differ in priority, description, and creation time."""
    return [
        make_task(1, "banana", "low", created_at="2026-01-03T00:00:00"),
        make_task(2, "Apple", "high", created_at="2026-01-01T00:00:00"),
        make_task(
            3, "cherry", "medium", completed=True, created_at="2026-01-02T00:00:00"
        ),
    ]


class TestSortStrategies:
    """Each strategy orders tasks by its own key."""

    def test_priority_sort_puts_high_first(self, tasks):
        result = PrioritySort().sort(tasks)
        assert [task["priority"] for task in result] == ["high", "medium", "low"]

    def test_priority_sort_breaks_ties_by_id(self):
        tied = [make_task(3, priority="high"), make_task(1, priority="high")]
        assert [task["id"] for task in PrioritySort().sort(tied)] == [1, 3]

    def test_created_date_sort_puts_oldest_first(self, tasks):
        result = CreatedDateSort().sort(tasks)
        assert [task["id"] for task in result] == [2, 3, 1]

    def test_description_sort_ignores_case(self, tasks):
        result = DescriptionSort().sort(tasks)
        assert [task["description"] for task in result] == ["Apple", "banana", "cherry"]

    def test_sorting_does_not_mutate_the_input_list(self, tasks):
        original = [task["id"] for task in tasks]
        PrioritySort().sort(tasks)
        assert [task["id"] for task in tasks] == original

    def test_sort_handles_empty_list(self):
        assert PrioritySort().sort([]) == []

    def test_sort_handles_task_missing_priority_key(self):
        """A task loaded from an older save file must not crash sorting."""
        result = PrioritySort().sort([{"id": 1}, make_task(2, priority="high")])
        assert [task["id"] for task in result] == [2, 1]


class TestFilterStrategies:
    """Filters select subsets without altering the tasks themselves."""

    def test_status_filter_keeps_only_completed(self, tasks):
        result = StatusFilter(completed=True).filter(tasks)
        assert [task["id"] for task in result] == [3]

    def test_status_filter_keeps_only_pending(self, tasks):
        result = StatusFilter(completed=False).filter(tasks)
        assert [task["id"] for task in result] == [1, 2]

    def test_priority_filter_selects_matching_priority(self, tasks):
        assert [task["id"] for task in PriorityFilter("high").filter(tasks)] == [2]

    def test_priority_filter_normalizes_case_and_whitespace(self, tasks):
        assert [task["id"] for task in PriorityFilter("  HIGH ").filter(tasks)] == [2]

    def test_priority_filter_rejects_invalid_priority(self):
        with pytest.raises(ValueError, match="Invalid priority 'urgent'"):
            PriorityFilter("urgent")

    def test_keyword_filter_is_case_insensitive(self, tasks):
        assert [task["id"] for task in KeywordFilter("APP").filter(tasks)] == [2]

    def test_keyword_filter_with_empty_string_keeps_everything(self, tasks):
        assert len(KeywordFilter("   ").filter(tasks)) == 3

    def test_keyword_filter_with_no_match_returns_empty(self, tasks):
        assert KeywordFilter("zzz").filter(tasks) == []


class TestTaskQuery:
    """The context object combines filters with an ordering."""

    def test_applies_sort_with_no_filters(self, tasks):
        result = TaskQuery(PrioritySort()).apply(tasks)
        assert [task["id"] for task in result] == [2, 3, 1]

    def test_combines_multiple_filters_with_and(self, tasks):
        result = (
            TaskQuery(PrioritySort())
            .add_filter(StatusFilter(False))
            .add_filter(KeywordFilter("an"))
            .apply(tasks)
        )
        assert [task["id"] for task in result] == [1]

    def test_sort_strategy_can_be_swapped_at_runtime(self, tasks):
        query = TaskQuery(PrioritySort())
        assert [task["id"] for task in query.apply(tasks)] == [2, 3, 1]
        query.set_sort_strategy(CreatedDateSort())
        assert [task["id"] for task in query.apply(tasks)] == [2, 3, 1]

    def test_apply_does_not_mutate_the_input_list(self, tasks):
        TaskQuery(DescriptionSort()).add_filter(StatusFilter(True)).apply(tasks)
        assert len(tasks) == 3

    def test_filters_that_exclude_everything_yield_empty_list(self, tasks):
        query = TaskQuery(PrioritySort()).add_filter(KeywordFilter("nothing"))
        assert query.apply(tasks) == []


class TestGetSortStrategy:
    """The lookup helper resolves CLI input to a strategy object."""

    @pytest.mark.parametrize("name", SORT_CHOICES)
    def test_every_advertised_choice_resolves(self, name):
        assert get_sort_strategy(name) is not None

    def test_lookup_normalizes_case(self):
        assert isinstance(get_sort_strategy("PRIORITY"), PrioritySort)

    def test_unknown_name_raises_with_valid_options_listed(self):
        with pytest.raises(ValueError, match="Unknown sort 'sideways'"):
            get_sort_strategy("sideways")
