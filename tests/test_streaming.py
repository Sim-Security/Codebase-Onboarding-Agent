"""
Tests for streaming functionality in app.py.

Phase-05: Performance and Streaming Improvements
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import _get_tool_status_indicator


class TestToolStatusIndicator:
    """Tests for _get_tool_status_indicator function."""

    def test_read_file_shows_filename(self):
        """Test that read_file shows the filename being read."""
        result = _get_tool_status_indicator(
            "read_file", {"file_path": "/some/path/to/main.py"}
        )
        assert "📖" in result
        assert "Reading" in result
        assert "main.py" in result

    def test_read_file_handles_empty_path(self):
        """Test that read_file handles empty file_path gracefully."""
        result = _get_tool_status_indicator("read_file", {"file_path": ""})
        assert "📖" in result
        assert "Reading" in result

    def test_read_file_handles_missing_path(self):
        """Test that read_file handles missing file_path key."""
        result = _get_tool_status_indicator("read_file", {})
        assert "📖" in result
        assert "Reading" in result

    def test_search_code_shows_pattern(self):
        """Test that search_code shows the search pattern."""
        result = _get_tool_status_indicator("search_code", {"pattern": "def main"})
        assert "🔎" in result
        assert "Searching" in result
        assert "def main" in result

    def test_search_code_handles_empty_pattern(self):
        """Test that search_code handles empty pattern."""
        result = _get_tool_status_indicator("search_code", {"pattern": ""})
        assert "🔎" in result
        assert "Searching" in result

    def test_find_files_by_pattern_shows_pattern(self):
        """Test that find_files_by_pattern shows the file pattern."""
        result = _get_tool_status_indicator(
            "find_files_by_pattern", {"pattern": "*.py"}
        )
        assert "🔎" in result
        assert "Finding files" in result
        assert "*.py" in result

    def test_list_directory_structure(self):
        """Test that list_directory_structure shows exploration message."""
        result = _get_tool_status_indicator("list_directory_structure", {})
        assert "📂" in result
        assert "Exploring" in result

    def test_get_imports_shows_filename(self):
        """Test that get_imports shows the filename being analyzed."""
        result = _get_tool_status_indicator(
            "get_imports", {"file_path": "/path/to/utils.py"}
        )
        assert "📦" in result
        assert "Analyzing imports" in result
        assert "utils.py" in result

    def test_find_entry_points(self):
        """Test that find_entry_points shows appropriate message."""
        result = _get_tool_status_indicator("find_entry_points", {})
        assert "🚀" in result
        assert "Finding entry points" in result

    def test_analyze_dependencies(self):
        """Test that analyze_dependencies shows appropriate message."""
        result = _get_tool_status_indicator("analyze_dependencies", {})
        assert "🔗" in result
        assert "Analyzing dependencies" in result

    def test_get_function_signatures_shows_filename(self):
        """Test that get_function_signatures shows the filename."""
        result = _get_tool_status_indicator(
            "get_function_signatures", {"file_path": "/path/to/handlers.py"}
        )
        assert "📝" in result
        assert "function signatures" in result
        assert "handlers.py" in result

    def test_get_important_files(self):
        """Test that get_important_files shows appropriate message."""
        result = _get_tool_status_indicator("get_important_files", {})
        assert "⭐" in result
        assert "Identifying important files" in result

    def test_unknown_tool_shows_generic_message(self):
        """Test that unknown tools show a generic message."""
        result = _get_tool_status_indicator("some_unknown_tool", {})
        assert "🔍" in result
        assert "some_unknown_tool" in result

    def test_all_indicators_have_backticks(self):
        """Test that all indicators are wrapped in backticks for markdown."""
        tools = [
            ("read_file", {"file_path": "test.py"}),
            ("search_code", {"pattern": "test"}),
            ("find_files_by_pattern", {"pattern": "*.py"}),
            ("list_directory_structure", {}),
            ("get_imports", {"file_path": "test.py"}),
            ("find_entry_points", {}),
            ("analyze_dependencies", {}),
            ("get_function_signatures", {"file_path": "test.py"}),
            ("get_important_files", {}),
            ("unknown_tool", {}),
        ]

        for tool_name, tool_input in tools:
            result = _get_tool_status_indicator(tool_name, tool_input)
            # Should start with newlines and backtick, end with backtick
            assert result.startswith("\n\n`"), f"Failed for {tool_name}"
            assert result.endswith("`"), f"Failed for {tool_name}"
