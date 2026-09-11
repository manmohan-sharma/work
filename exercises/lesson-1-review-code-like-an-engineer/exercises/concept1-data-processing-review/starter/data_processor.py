"""
Code Review Exercise 1: Data Processing Function (post-review)

This is the reviewed version of the starter function. Changes applied from the
review, in the order the review ranked them:

Blocking fixes
1. Input validation      -> non-list input raises TypeError naming the bad type
2. Per-record guards     -> malformed records are logged and skipped, so one bad
                            row no longer aborts the batch with a KeyError
3. Magic numbers         -> named module constants (1.2, 100, 'active')

Clarity fixes
4. `temp`                -> `scaled_value`; `data`/`result` -> `records`/`processed_items`
5. if/assign capping     -> min(), so one name no longer holds two meanings
6. Silent failures       -> logging.warning (routable and capturable, unlike print)
7. No contract           -> type hints and a docstring stating shape and raises

The original pre-review function is preserved in `data_processor.py.orig`.
"""

import logging

logger = logging.getLogger(__name__)

ACTIVE_STATUS = 'active'
VALUE_MULTIPLIER = 1.2      # 20% uplift applied to active records
MAX_PROCESSED_VALUE = 100   # business ceiling on a processed value
REQUIRED_FIELDS = ('id', 'status', 'value')


def process_data(records: list[dict]) -> list[dict]:
    """Return {'id', 'processed_value'} for each active, well-formed record.

    Each active record's value is scaled by VALUE_MULTIPLIER and capped at
    MAX_PROCESSED_VALUE. Malformed records are logged and skipped rather than
    aborting the batch.

    Args:
        records: List of dicts, each expected to carry 'id', 'status', 'value'.

    Returns:
        List of dicts with 'id' and 'processed_value', in input order.

    Raises:
        TypeError: if `records` is not a list.
    """
    if not isinstance(records, list):
        raise TypeError(f"records must be a list, got {type(records).__name__}")

    processed_items = []
    for record in records:
        if not isinstance(record, dict):
            logger.warning("Skipping non-dict record: %r", record)
            continue

        missing = [field for field in REQUIRED_FIELDS if field not in record]
        if missing:
            logger.warning("Skipping record missing %s: %r", missing, record)
            continue

        value = record['value']
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            logger.warning("Skipping record with non-numeric value: %r", record)
            continue

        if record['status'] == ACTIVE_STATUS:
            scaled_value = min(value * VALUE_MULTIPLIER, MAX_PROCESSED_VALUE)
            processed_items.append({'id': record['id'], 'processed_value': scaled_value})

    return processed_items
