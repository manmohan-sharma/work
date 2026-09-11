"""Tests for the reviewed data processing function.

Updated alongside the review of data_processor.py:
- Assertions use the named constants instead of re-typing 1.2 and 100.
- The error-handling tests now assert graceful skipping (the behavior the
  original file described in comments) instead of asserting the KeyError.
- Non-list input is expected to raise TypeError, the Python convention for a
  wrong-type argument.
- Added boundary, non-numeric, and log-output coverage.

The original pre-review suite is preserved in `test_data_processor.py.orig`.
"""

import logging

import pytest
from data_processor import (
    ACTIVE_STATUS,
    MAX_PROCESSED_VALUE,
    VALUE_MULTIPLIER,
    process_data,
)


class TestDataProcessorBasic:
    """Tests for basic functionality."""

    def test_processes_active_items(self):
        """Only active items are processed, and values are scaled and capped."""
        test_data = [
            {'id': 1, 'status': ACTIVE_STATUS, 'value': 50},
            {'id': 2, 'status': 'inactive', 'value': 75},
            {'id': 3, 'status': ACTIVE_STATUS, 'value': 120},
        ]

        result = process_data(test_data)

        assert len(result) == 2
        assert result[0]['id'] == 1
        assert result[0]['processed_value'] == 50 * VALUE_MULTIPLIER
        assert result[1]['id'] == 3
        assert result[1]['processed_value'] == MAX_PROCESSED_VALUE

    def test_empty_list_returns_empty(self):
        """Test with empty input."""
        assert process_data([]) == []

    def test_no_active_items_returns_empty(self):
        """Test when no items are active."""
        test_data = [
            {'id': 1, 'status': 'inactive', 'value': 50},
            {'id': 2, 'status': 'pending', 'value': 75},
        ]

        assert process_data(test_data) == []

    def test_preserves_input_order(self):
        """Output order matches input order."""
        test_data = [
            {'id': 3, 'status': ACTIVE_STATUS, 'value': 10},
            {'id': 1, 'status': ACTIVE_STATUS, 'value': 20},
            {'id': 2, 'status': ACTIVE_STATUS, 'value': 30},
        ]

        result = process_data(test_data)

        assert [item['id'] for item in result] == [3, 1, 2]


class TestDataProcessorErrorHandling:
    """One bad record must not destroy the batch."""

    def test_missing_required_fields_handled_gracefully(self):
        """Records missing required fields are skipped, good ones survive."""
        problematic_data = [
            {'id': 1, 'status': ACTIVE_STATUS, 'value': 50},  # Good item
            {'id': 5, 'status': ACTIVE_STATUS},               # Missing 'value'
            {'id': 6, 'value': 30},                           # Missing 'status'
            {'status': ACTIVE_STATUS, 'value': 30},           # Missing 'id'
        ]

        result = process_data(problematic_data)

        assert len(result) == 1
        assert result[0]['id'] == 1

    def test_invalid_input_type_raises_clear_error(self):
        """Non-list input raises TypeError naming the type it got."""
        with pytest.raises(TypeError, match="records must be a list, got str"):
            process_data("not a list")

    def test_none_input_raises_clear_error(self):
        """None input raises TypeError rather than failing inside the loop."""
        with pytest.raises(TypeError, match="records must be a list, got NoneType"):
            process_data(None)

    def test_skipped_records_are_logged(self, caplog):
        """Skipping must be visible to an operator, not silent."""
        with caplog.at_level(logging.WARNING, logger='data_processor'):
            result = process_data([
                {'id': 1, 'status': ACTIVE_STATUS, 'value': 50},
                {'id': 2, 'status': ACTIVE_STATUS},
                None,
            ])

        assert len(result) == 1
        assert len(caplog.records) == 2
        assert "missing ['value']" in caplog.text
        assert "non-dict record" in caplog.text


class TestDataProcessorConstants:
    """Constants make the business rules testable."""

    def test_multiplier_is_applied(self):
        """The scaling rule is asserted through its name, not a literal."""
        result = process_data([{'id': 1, 'status': ACTIVE_STATUS, 'value': 10}])

        assert result[0]['processed_value'] == 10 * VALUE_MULTIPLIER

    def test_value_is_capped_at_maximum(self):
        """Anything above the ceiling comes back as the ceiling."""
        result = process_data([{'id': 1, 'status': ACTIVE_STATUS, 'value': 200}])

        assert result[0]['processed_value'] == MAX_PROCESSED_VALUE

    def test_exactly_at_max_after_scaling(self):
        """The input that scales to exactly the ceiling is capped, not overshot."""
        input_value = MAX_PROCESSED_VALUE / VALUE_MULTIPLIER
        result = process_data([{'id': 1, 'status': ACTIVE_STATUS, 'value': input_value}])

        assert result[0]['processed_value'] == MAX_PROCESSED_VALUE

    def test_just_below_max_is_not_capped(self):
        """Values under the ceiling pass through scaled, uncapped."""
        input_value = MAX_PROCESSED_VALUE / VALUE_MULTIPLIER - 1
        result = process_data([{'id': 1, 'status': ACTIVE_STATUS, 'value': input_value}])

        assert result[0]['processed_value'] == pytest.approx(input_value * VALUE_MULTIPLIER)
        assert result[0]['processed_value'] < MAX_PROCESSED_VALUE


class TestDataProcessorRobustness:
    """Edge cases and mixed-quality input."""

    def test_zero_value_handled(self):
        """Zero values are processed, not treated as missing."""
        result = process_data([{'id': 1, 'status': ACTIVE_STATUS, 'value': 0}])

        assert len(result) == 1
        assert result[0]['processed_value'] == 0.0

    def test_negative_value_handled(self):
        """Negative values scale normally; the cap is one-sided."""
        result = process_data([{'id': 1, 'status': ACTIVE_STATUS, 'value': -10}])

        assert len(result) == 1
        assert result[0]['processed_value'] == -10 * VALUE_MULTIPLIER

    def test_non_numeric_value_skipped(self):
        """A string value is skipped instead of raising from the multiply."""
        result = process_data([
            {'id': 1, 'status': ACTIVE_STATUS, 'value': '50'},
            {'id': 2, 'status': ACTIVE_STATUS, 'value': None},
            {'id': 3, 'status': ACTIVE_STATUS, 'value': 50},
        ])

        assert len(result) == 1
        assert result[0]['id'] == 3

    def test_boolean_value_skipped(self):
        """True is an int in Python; it must not silently scale to 1.2."""
        result = process_data([{'id': 1, 'status': ACTIVE_STATUS, 'value': True}])

        assert result == []

    def test_mixed_valid_and_invalid_data(self):
        """The good records are returned even when bad ones are interleaved."""
        mixed_data = [
            {'id': 1, 'status': ACTIVE_STATUS, 'value': 50},  # Valid
            {'id': 2, 'status': ACTIVE_STATUS},               # Missing value
            {'id': 3, 'status': ACTIVE_STATUS, 'value': 30},  # Valid
            None,                                             # Invalid item
            {'id': 4, 'value': 40},                           # Missing status
        ]

        result = process_data(mixed_data)

        assert len(result) == 2
        assert result[0]['id'] == 1
        assert result[1]['id'] == 3
