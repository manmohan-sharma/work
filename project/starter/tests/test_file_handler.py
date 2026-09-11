"""
Unit tests for the FileHandler class.

These tests demonstrate file I/O testing patterns and proper
cleanup of test artifacts.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from utils.file_handler import FileHandler


class TestFileHandler:
    """Test suite for FileHandler functionality."""

    def setup_method(self):
        """Set up test fixtures with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.file_handler = FileHandler(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        shutil.rmtree(self.temp_dir)

    def test_save_data_creates_file(self):
        """Test that save_data creates a file with correct content."""
        data = {"test": "data", "number": 42}
        self.file_handler.save_data("test.json", data)

        assert self.file_handler.file_exists("test.json")
        loaded_data = self.file_handler.load_data("test.json")
        assert loaded_data == data

    def test_load_nonexistent_file_returns_empty_dict(self):
        """Test that loading a non-existent file returns empty dict."""
        result = self.file_handler.load_data("nonexistent.json")
        assert result == {}

    def test_save_invalid_data_raises_error(self):
        """Test that saving invalid JSON data raises RuntimeError."""
        # Create data that can't be serialized to JSON
        invalid_data = {"function": lambda x: x}
        with pytest.raises(RuntimeError, match="Failed to save data"):
            self.file_handler.save_data("invalid.json", invalid_data)

    def test_file_exists(self):
        """Test file existence checking."""
        assert not self.file_handler.file_exists("test.json")
        self.file_handler.save_data("test.json", {"test": "data"})
        assert self.file_handler.file_exists("test.json")

    def test_delete_file(self):
        """Test file deletion."""
        self.file_handler.save_data("test.json", {"test": "data"})
        assert self.file_handler.file_exists("test.json")

        self.file_handler.delete_file("test.json")
        assert not self.file_handler.file_exists("test.json")

    def test_delete_nonexistent_file_no_error(self):
        """Test that deleting non-existent file doesn't raise error."""
        self.file_handler.delete_file("nonexistent.json")  # Should not raise

    def test_list_files(self):
        """Test listing files in data directory."""
        self.file_handler.save_data("file1.json", {"data": 1})
        self.file_handler.save_data("file2.json", {"data": 2})

        files = self.file_handler.list_files()
        assert len(files) == 2
        assert "file1.json" in files
        assert "file2.json" in files


class TestPathTraversalProtection:
    """Filenames come from the command line, so they must stay contained.

    These tests were added during final review, after a manual check showed
    that `export json ../../../tmp/x.json` wrote outside the data directory.
    """

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.file_handler = FileHandler(self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_plain_filename_resolves_inside_the_data_directory(self):
        resolved = self.file_handler.resolve_path("tasks.json")
        assert resolved.parent == Path(self.temp_dir).resolve()

    def test_nested_filename_is_allowed(self):
        resolved = self.file_handler.resolve_path("reports/tasks.json")
        assert Path(self.temp_dir).resolve() in resolved.parents

    def test_parent_traversal_is_rejected(self):
        with pytest.raises(ValueError, match="must stay inside the data directory"):
            self.file_handler.resolve_path("../escaped.json")

    def test_deep_parent_traversal_is_rejected(self):
        with pytest.raises(ValueError, match="must stay inside"):
            self.file_handler.resolve_path("../../../../tmp/escaped.json")

    def test_traversal_hidden_mid_path_is_rejected(self):
        with pytest.raises(ValueError, match="must stay inside"):
            self.file_handler.resolve_path("reports/../../escaped.json")

    def test_absolute_path_is_rejected(self):
        with pytest.raises(ValueError, match="must stay inside"):
            self.file_handler.resolve_path("/tmp/escaped.json")

    def test_empty_filename_is_rejected(self):
        with pytest.raises(ValueError, match="must not be empty"):
            self.file_handler.resolve_path("   ")

    def test_save_data_rejects_a_traversing_filename(self):
        with pytest.raises(ValueError, match="must stay inside"):
            self.file_handler.save_data("../escaped.json", {"a": 1})

    def test_load_data_rejects_a_traversing_filename(self):
        with pytest.raises(ValueError, match="must stay inside"):
            self.file_handler.load_data("../escaped.json")

    def test_delete_file_rejects_a_traversing_filename(self):
        with pytest.raises(ValueError, match="must stay inside"):
            self.file_handler.delete_file("../escaped.json")

    def test_file_exists_rejects_a_traversing_filename(self):
        with pytest.raises(ValueError, match="must stay inside"):
            self.file_handler.file_exists("../escaped.json")
