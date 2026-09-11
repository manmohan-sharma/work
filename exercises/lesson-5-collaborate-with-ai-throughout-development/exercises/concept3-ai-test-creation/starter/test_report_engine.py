"""
Tests for ReportEngine.

ReportEngine owns no analysis logic -- it wires a loader to a report mode.
So these tests cover two things: that the wiring is correct (the right
collaborator is called, with the right argument, in the right order), and
that failures from either collaborator reach the caller intact.

Unit tests mock both collaborators to isolate the engine. TestIntegration
drops the mocks and runs the real loader and real report modes against a
fixture CSV.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest

from report_engine import ReportEngine
from expense_tracker.data.transaction_loader import CSVTransactionLoader
from expense_tracker.domain.exceptions import DataLoadError
from expense_tracker.domain.models import Transaction
from expense_tracker.reports.report_mode import (
    CategorySummaryReport,
    MonthlyTotalsReport,
)

FIXTURE_CSV = Path(__file__).parent / "tests" / "fixtures" / "valid_expenses.csv"


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def sample_transactions():
    """Two transactions in different categories -- enough to prove data flow."""
    return [
        Transaction(date(2025, 1, 15), Decimal("42.50"), "Food", "Lunch at cafe"),
        Transaction(date(2025, 1, 16), Decimal("120.00"), "Transportation", "Metro pass"),
    ]


@pytest.fixture
def mock_loader(sample_transactions):
    """A loader stand-in that succeeds, returning the sample transactions."""
    loader = Mock()
    loader.load.return_value = sample_transactions
    return loader


@pytest.fixture
def mock_mode():
    """A report mode stand-in that succeeds, returning a recognisable report."""
    mode = Mock()
    mode.process_transactions.return_value = "REPORT BODY"
    return mode


@pytest.fixture
def engine(mock_loader):
    """A ReportEngine wired to the mock loader."""
    return ReportEngine(mock_loader)


# --------------------------------------------------------------------------
# Basics
# --------------------------------------------------------------------------

class TestReportEngineBasics:
    """Instantiation and the basic shape of generate_report."""

    def test_engine_keeps_the_loader_it_was_constructed_with(self, mock_loader):
        """The loader passed in is the loader the engine uses."""
        assert ReportEngine(mock_loader).loader is mock_loader, \
            "engine did not retain the loader it was given"

    def test_generate_report_returns_mode_output_unchanged(self, engine, mock_mode):
        """The engine is a pass-through: it must not reshape the mode's output."""
        sentinel = {"mode": "summary", "total": Decimal("162.50")}
        mock_mode.process_transactions.return_value = sentinel

        result = engine.generate_report("expenses.csv", mock_mode)

        assert result is sentinel, "engine altered or rewrapped the mode's return value"


# --------------------------------------------------------------------------
# Happy path
# --------------------------------------------------------------------------

class TestReportGenerationHappyPath:
    """Successful generation, and the data flow loader -> mode -> caller."""

    def test_generates_report_from_valid_input(self, engine, mock_mode):
        """A valid file and mode produce the mode's report."""
        assert engine.generate_report("expenses.csv", mock_mode) == "REPORT BODY", \
            "engine did not return the report the mode produced"

    def test_loader_is_called_once_with_the_requested_filepath(self, engine, mock_loader, mock_mode):
        """The filepath reaches the loader verbatim, and the file is read once."""
        engine.generate_report("expenses.csv", mock_mode)

        mock_loader.load.assert_called_once_with("expenses.csv")

    def test_mode_receives_the_transactions_the_loader_returned(self, engine, mock_mode, sample_transactions):
        """Transactions are handed to the mode untouched -- no filtering or copying."""
        engine.generate_report("expenses.csv", mock_mode)

        mock_mode.process_transactions.assert_called_once_with(sample_transactions)

    @pytest.mark.parametrize(
        "mode_name, expected_output",
        [
            ("summary", "Category Summary Report"),
            ("monthly", "Monthly Totals Report"),
            ("top", "Top Expenses Report"),
        ],
    )
    def test_generates_report_for_each_mode(self, engine, mode_name, expected_output):
        """Any mode honouring the interface works -- the engine is strategy-agnostic."""
        mode = Mock()
        mode.process_transactions.return_value = expected_output

        assert engine.generate_report("expenses.csv", mode) == expected_output, \
            f"engine mishandled the {mode_name} mode"

    def test_loading_happens_before_processing(self, engine, mock_loader, mock_mode):
        """Order matters: you cannot process transactions you have not loaded."""
        recorder = Mock()
        recorder.attach_mock(mock_loader.load, "load")
        recorder.attach_mock(mock_mode.process_transactions, "process")

        engine.generate_report("expenses.csv", mock_mode)

        assert [name for name, _, _ in recorder.mock_calls] == ["load", "process"], \
            "engine processed transactions before loading them"


# --------------------------------------------------------------------------
# Errors and edge cases
# --------------------------------------------------------------------------

class TestReportGenerationErrors:
    """Failure propagation, plus the awkward-but-legal inputs."""

    def test_file_not_found_error_propagates_from_loader(self, engine, mock_loader, mock_mode):
        """A missing file surfaces to the caller rather than being swallowed."""
        mock_loader.load.side_effect = FileNotFoundError("no such file")

        with pytest.raises(FileNotFoundError, match="no such file"):
            engine.generate_report("missing.csv", mock_mode)

    def test_value_error_propagates_for_invalid_data(self, engine, mock_loader, mock_mode):
        """Invalid CSV content surfaces with its original message intact."""
        mock_loader.load.side_effect = ValueError("malformed row 3")

        with pytest.raises(ValueError, match="malformed row 3"):
            engine.generate_report("broken.csv", mock_mode)

    def test_mode_is_not_called_when_the_loader_fails(self, engine, mock_loader, mock_mode):
        """A failed load must short-circuit -- never process a half-read file."""
        mock_loader.load.side_effect = FileNotFoundError("no such file")

        with pytest.raises(FileNotFoundError):
            engine.generate_report("missing.csv", mock_mode)

        mock_mode.process_transactions.assert_not_called()

    def test_error_raised_inside_the_mode_propagates(self, engine, mock_mode):
        """Strategy failures are the caller's to handle, not the engine's to hide."""
        mock_mode.process_transactions.side_effect = RuntimeError("aggregation failed")

        with pytest.raises(RuntimeError, match="aggregation failed"):
            engine.generate_report("expenses.csv", mock_mode)

    def test_empty_transaction_list_is_handed_to_the_mode(self, engine, mock_loader, mock_mode):
        """An empty file is not an engine-level error; the mode decides what it means."""
        mock_loader.load.return_value = []

        engine.generate_report("empty.csv", mock_mode)

        mock_mode.process_transactions.assert_called_once_with([])

    def test_single_transaction_is_processed(self, engine, mock_loader, mock_mode):
        """A one-row file is a normal case, not a degenerate one."""
        only = [Transaction(date(2025, 1, 15), Decimal("42.50"), "Food", "Lunch")]
        mock_loader.load.return_value = only

        engine.generate_report("one.csv", mock_mode)

        mock_mode.process_transactions.assert_called_once_with(only)

    def test_large_transaction_set_passes_through_intact(self, engine, mock_loader, mock_mode):
        """Volume changes nothing: no truncation, batching or reordering."""
        many = [
            Transaction(date(2025, 1, 1), Decimal("1.00"), "Cat" + str(i % 7), "Item " + str(i))
            for i in range(1000)
        ]
        mock_loader.load.return_value = many

        engine.generate_report("big.csv", mock_mode)

        delivered = mock_mode.process_transactions.call_args[0][0]
        assert len(delivered) == 1000, "engine dropped transactions on a large input"

    def test_special_characters_survive_the_pipeline(self, engine, mock_loader, mock_mode):
        """Unicode and punctuation must not be mangled in transit."""
        odd = [Transaction(date(2025, 1, 15), Decimal("9.99"), "Cafe", "Creme brulee & <tags>")]
        mock_loader.load.return_value = odd

        engine.generate_report("unicode.csv", mock_mode)

        delivered = mock_mode.process_transactions.call_args[0][0]
        assert delivered[0].description == "Creme brulee & <tags>", \
            "special characters were altered in transit"

    def test_repeated_category_is_not_deduplicated(self, engine, mock_loader, mock_mode):
        """Grouping belongs to the mode; the engine must not collapse duplicates."""
        repeated = [
            Transaction(date(2025, 1, 15), Decimal("10.00"), "Food", "Breakfast"),
            Transaction(date(2025, 1, 16), Decimal("20.00"), "Food", "Lunch"),
            Transaction(date(2025, 1, 17), Decimal("30.00"), "Food", "Dinner"),
        ]
        mock_loader.load.return_value = repeated

        engine.generate_report("repeats.csv", mock_mode)

        assert len(mock_mode.process_transactions.call_args[0][0]) == 3, \
            "engine collapsed duplicate categories that the mode should group"

    def test_none_from_loader_reaches_the_mode_and_its_error_propagates(self, engine, mock_loader, mock_mode):
        """A loader returning None is not caught here; the mode's TypeError surfaces.

        The engine deliberately does no validation, so a buggy loader is
        diagnosed by whichever mode tries to iterate the result.
        """
        mock_loader.load.return_value = None

        def realistic_mode(transactions):
            if transactions is None:
                raise TypeError("'NoneType' object is not iterable")
            return "REPORT BODY"

        mock_mode.process_transactions.side_effect = realistic_mode

        with pytest.raises(TypeError, match="not iterable"):
            engine.generate_report("broken_loader.csv", mock_mode)

        mock_mode.process_transactions.assert_called_once_with(None)

    def test_permission_error_propagates_from_loader(self, engine, mock_loader, mock_mode):
        """An unreadable file surfaces as PermissionError, not a generic failure."""
        mock_loader.load.side_effect = PermissionError("permission denied")

        with pytest.raises(PermissionError, match="permission denied"):
            engine.generate_report("locked.csv", mock_mode)

    def test_unexpected_loader_exception_propagates_unchanged(self, engine, mock_loader, mock_mode):
        """The engine catches nothing, so even unforeseen errors reach the caller."""
        mock_loader.load.side_effect = OSError("disk failure")

        with pytest.raises(OSError, match="disk failure"):
            engine.generate_report("expenses.csv", mock_mode)

    def test_filepath_with_special_characters_reaches_loader_unchanged(self, engine, mock_loader, mock_mode):
        """Spaces and punctuation in a path are the loader's problem, not the engine's."""
        awkward = "my reports/2025 Q1 (final) & draft.csv"

        engine.generate_report(awkward, mock_mode)

        mock_loader.load.assert_called_once_with(awkward)

    def test_decimal_precision_is_preserved_through_the_pipeline(self, engine, mock_loader, mock_mode):
        """Amounts must arrive as exact Decimals -- no float rounding in transit."""
        precise = [Transaction(date(2025, 1, 15), Decimal("0.01"), "Food", "Sweet")]
        mock_loader.load.return_value = precise

        engine.generate_report("precise.csv", mock_mode)

        delivered = mock_mode.process_transactions.call_args[0][0]
        assert delivered[0].amount == Decimal("0.01"), "amount lost precision in transit"


# --------------------------------------------------------------------------
# Integration
# --------------------------------------------------------------------------

class TestIntegration:
    """End-to-end with the real loader, real modes and a real CSV file."""

    @pytest.fixture
    def real_engine(self):
        """An engine wired to the genuine CSV loader -- no mocks."""
        return ReportEngine(CSVTransactionLoader())

    def test_generates_report_end_to_end_from_a_real_file(self, real_engine):
        """The full path file -> loader -> mode -> report produces real output."""
        report = real_engine.generate_report(str(FIXTURE_CSV), CategorySummaryReport())

        assert "Category Summary Report" in report, \
            "end-to-end run did not produce a category summary"

    def test_same_engine_generates_multiple_reports_successfully(self, real_engine):
        """The engine is stateless: a second call is unaffected by the first."""
        first = real_engine.generate_report(str(FIXTURE_CSV), CategorySummaryReport())
        second = real_engine.generate_report(str(FIXTURE_CSV), CategorySummaryReport())

        assert first == second, "engine carried state between reports"

    def test_same_data_works_with_different_modes(self, real_engine):
        """One file, two strategies, two genuinely different reports."""
        summary = real_engine.generate_report(str(FIXTURE_CSV), CategorySummaryReport())
        monthly = real_engine.generate_report(str(FIXTURE_CSV), MonthlyTotalsReport())

        assert summary != monthly, \
            "two different modes produced identical reports"

    def test_missing_file_raises_data_load_error_end_to_end(self, real_engine, tmp_path):
        """The real loader signals a missing file as DataLoadError, not FileNotFoundError."""
        absent = tmp_path / "does_not_exist.csv"

        with pytest.raises(DataLoadError):
            real_engine.generate_report(str(absent), CategorySummaryReport())
