"""
File handling utility for data persistence.

This module demonstrates file I/O operations and error handling
patterns that students can learn from and extend.
"""

import json
from pathlib import Path
from typing import Any, Dict


class FileHandler:
    """Handle file operations for data persistence."""

    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    def resolve_path(self, filename: str) -> Path:
        """Resolve a filename to a path inside the data directory.

        Filenames reach this class from the command line, so a name such as
        ``../../etc/passwd`` would otherwise let a user read or write outside
        the data directory entirely.

        Args:
            filename: The name to resolve, relative to the data directory.

        Returns:
            The absolute path the filename refers to.

        Raises:
            ValueError: If the filename is empty, absolute, or resolves to a
                location outside the data directory.
        """
        if not filename.strip():
            raise ValueError("Filename must not be empty")

        root = self.data_dir.resolve()
        candidate = (root / filename).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(
                f"Invalid filename '{filename}': " "must stay inside the data directory"
            )
        return candidate

    def save_data(self, filename: str, data: Dict[str, Any]) -> None:
        """Save data to a JSON file inside the data directory.

        Raises:
            ValueError: If the filename escapes the data directory.
            RuntimeError: If the file cannot be written.
        """
        filepath = self.resolve_path(filename)
        try:
            with open(filepath, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
        except (IOError, TypeError) as e:
            raise RuntimeError(f"Failed to save data to {filename}: {e}")

    def load_data(self, filename: str) -> Dict[str, Any]:
        """Load data from a JSON file inside the data directory.

        Returns an empty dict when the file does not exist.

        Raises:
            ValueError: If the filename escapes the data directory.
            RuntimeError: If the file exists but cannot be read.
        """
        filepath = self.resolve_path(filename)
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                loaded: Dict[str, Any] = json.load(file)
                return loaded
        except FileNotFoundError:
            return {}
        except (IOError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to load data from {filename}: {e}")

    def file_exists(self, filename: str) -> bool:
        """Check if a file exists in the data directory.

        Raises:
            ValueError: If the filename escapes the data directory.
        """
        return self.resolve_path(filename).exists()

    def delete_file(self, filename: str) -> None:
        """Delete a file from the data directory.

        Raises:
            ValueError: If the filename escapes the data directory.
        """
        filepath = self.resolve_path(filename)
        if filepath.exists():
            filepath.unlink()

    def list_files(self) -> list[str]:
        """List all files in the data directory."""
        return [f.name for f in self.data_dir.iterdir() if f.is_file()]
