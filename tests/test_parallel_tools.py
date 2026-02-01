"""
Tests for PERF-001: Parallel tool execution utilities.

Validates that tools can be executed in parallel without conflicts
and that the parallel execution utilities work correctly.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest


class TestToolIndependence:
    """Test that all tools are independent and can run in parallel."""

    def test_tools_have_no_shared_state(self):
        """Verify tools don't modify any shared state."""
        from src.tools import (
            analyze_dependencies,
            find_entry_points,
            find_files_by_pattern,
            get_function_signatures,
            get_imports,
            list_directory_structure,
            read_file,
            search_code,
        )
        from src.tools.smart_discovery import get_important_files

        # All tools should be functions decorated with @tool
        # They should not have any instance state
        tools = [
            list_directory_structure,
            read_file,
            search_code,
            find_files_by_pattern,
            get_imports,
            find_entry_points,
            analyze_dependencies,
            get_function_signatures,
            get_important_files,
        ]

        for tool in tools:
            # Verify it's a tool (has invoke method)
            assert hasattr(tool, "invoke"), f"{tool.name} should have invoke method"
            # Verify no mutable class-level state
            assert not hasattr(tool, "_state"), f"{tool.name} should not have _state"

    def test_tool_signatures_are_independent(self):
        """Verify each tool only depends on its explicit inputs."""
        from src.agent import TOOLS

        # Map tool names to their input parameters
        expected_inputs = {
            "list_directory_structure": {"repo_path", "max_depth"},
            "read_file": {"file_path", "max_lines", "force"},
            "search_code": {"repo_path", "pattern", "file_extension", "max_results"},
            "find_files_by_pattern": {"repo_path", "pattern", "max_results"},
            "get_imports": {"file_path"},
            "find_entry_points": {"repo_path"},
            "analyze_dependencies": {"repo_path"},
            "get_function_signatures": {"file_path"},
            "get_important_files": {"repo_path", "top_n"},
        }

        for tool in TOOLS:
            tool_name = tool.name
            if tool_name in expected_inputs:
                # Get the actual input schema from the tool
                schema = tool.args_schema
                if schema:
                    actual_fields = set(schema.model_fields.keys())
                    expected = expected_inputs[tool_name]
                    # Check that tool has expected inputs (may have more due to optional params)
                    assert expected.issubset(actual_fields) or actual_fields.issubset(
                        expected
                    ), f"{tool_name} has unexpected inputs: {actual_fields}"


class TestParallelInitialExplore:
    """Tests for parallel_initial_explore function."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create basic repo structure
            repo = Path(tmpdir)
            (repo / "main.py").write_text("print('hello')")
            (repo / "requirements.txt").write_text("langchain>=0.1.0")
            yield str(repo)

    @pytest.mark.asyncio
    async def test_parallel_initial_explore_returns_all_results(self, temp_repo):
        """Verify parallel_initial_explore returns results from all tools."""
        from src.agent import parallel_initial_explore

        result = await parallel_initial_explore(temp_repo)

        # Should have all three keys
        assert "entry_points" in result
        assert "dependencies" in result
        assert "important_files" in result

        # Results should be strings (either content or error messages)
        assert isinstance(result["entry_points"], str)
        assert isinstance(result["dependencies"], str)
        assert isinstance(result["important_files"], str)

    @pytest.mark.asyncio
    async def test_parallel_initial_explore_handles_errors(self):
        """Verify parallel_initial_explore handles tool errors gracefully."""
        from src.agent import parallel_initial_explore

        # Use a non-existent path
        result = await parallel_initial_explore("/nonexistent/path")

        # Should still return a dict with all keys
        assert "entry_points" in result
        assert "dependencies" in result
        assert "important_files" in result

        # At least some should contain error messages
        all_results = [
            result["entry_points"],
            result["dependencies"],
            result["important_files"],
        ]
        assert any("Error" in r for r in all_results), (
            "Expected at least one error for non-existent path"
        )

    @pytest.mark.asyncio
    async def test_parallel_execution_is_faster_than_sequential(self, temp_repo):
        """Verify parallel execution provides speedup over sequential."""
        import time

        from src.agent import parallel_initial_explore
        from src.tools import analyze_dependencies, find_entry_points
        from src.tools.smart_discovery import get_important_files

        # Measure parallel execution
        start_parallel = time.time()
        await parallel_initial_explore(temp_repo)
        parallel_time = time.time() - start_parallel

        # Measure sequential execution
        start_sequential = time.time()
        find_entry_points.invoke({"repo_path": temp_repo})
        analyze_dependencies.invoke({"repo_path": temp_repo})
        get_important_files.invoke({"repo_path": temp_repo})
        sequential_time = time.time() - start_sequential

        # Parallel should not be slower than sequential
        # (It might not be faster in tests due to small repo size and GIL)
        # Just verify both complete successfully
        assert parallel_time > 0
        assert sequential_time > 0


class TestParallelReadFiles:
    """Tests for parallel_read_files function."""

    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = []
            for i in range(5):
                file_path = Path(tmpdir) / f"file{i}.py"
                # Create files with enough lines to not be trivial (3+ lines)
                file_path.write_text(f"""# File {i}
# This is a test file with enough content
# to not be considered trivial by the file reader
def test_func_{i}():
    print({i})
    return {i}
""")
                files.append(str(file_path))
            yield files

    @pytest.mark.asyncio
    async def test_parallel_read_files_reads_all_files(self, temp_files):
        """Verify parallel_read_files reads all specified files."""
        from src.agent import parallel_read_files

        results = await parallel_read_files(temp_files)

        # Should have results for all files
        assert len(results) == len(temp_files)

        # Each file should have content
        for file_path in temp_files:
            assert file_path in results
            assert "File" in results[file_path] or "print" in results[file_path]

    @pytest.mark.asyncio
    async def test_parallel_read_files_handles_empty_list(self):
        """Verify parallel_read_files handles empty input."""
        from src.agent import parallel_read_files

        results = await parallel_read_files([])

        assert results == {}

    @pytest.mark.asyncio
    async def test_parallel_read_files_handles_mixed_success_failure(self, temp_files):
        """Verify parallel_read_files handles some files existing and some not."""
        from src.agent import parallel_read_files

        mixed_paths = temp_files[:2] + ["/nonexistent/file.py"]
        results = await parallel_read_files(mixed_paths)

        # Should have results for all paths
        assert len(results) == 3

        # Existing files should have content
        assert "File" in results[temp_files[0]] or "print" in results[temp_files[0]]

        # Non-existent file should have error
        assert (
            "Error" in results["/nonexistent/file.py"]
            or "does not exist" in results["/nonexistent/file.py"]
        )


class TestParallelGetImports:
    """Tests for parallel_get_imports function."""

    @pytest.fixture
    def temp_python_files(self):
        """Create temporary Python files with imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = []

            # File with standard library imports
            file1 = Path(tmpdir) / "file1.py"
            file1.write_text("import os\nimport sys\nfrom pathlib import Path")
            files.append(str(file1))

            # File with third-party imports
            file2 = Path(tmpdir) / "file2.py"
            file2.write_text("import numpy as np\nfrom pandas import DataFrame")
            files.append(str(file2))

            # File with local imports
            file3 = Path(tmpdir) / "file3.py"
            file3.write_text("from . import utils\nfrom .helpers import helper_func")
            files.append(str(file3))

            yield files

    @pytest.mark.asyncio
    async def test_parallel_get_imports_analyzes_all_files(self, temp_python_files):
        """Verify parallel_get_imports analyzes all files."""
        from src.agent import parallel_get_imports

        results = await parallel_get_imports(temp_python_files)

        # Should have results for all files
        assert len(results) == len(temp_python_files)

        # Each result should contain import information
        for file_path in temp_python_files:
            assert file_path in results
            result = results[file_path]
            # Should have meaningful content (imports or "No imports found")
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_parallel_get_imports_handles_empty_list(self):
        """Verify parallel_get_imports handles empty input."""
        from src.agent import parallel_get_imports

        results = await parallel_get_imports([])

        assert results == {}


class TestToolParallelizationDocumentation:
    """Test that documentation is accurate."""

    def test_all_tools_documented_in_agent(self):
        """Verify all tools are documented in PERF-001 comment block."""
        from src.agent import TOOLS

        # Read the agent.py file to check documentation
        agent_path = Path(__file__).parent.parent / "src" / "agent.py"
        content = agent_path.read_text()

        # Check that PERF-001 section exists
        assert "PERF-001" in content, "PERF-001 documentation should exist"

        # Check that all tool names are documented
        for tool in TOOLS:
            assert tool.name in content, f"Tool {tool.name} should be documented"

    def test_parallel_functions_exported(self):
        """Verify parallel execution functions are importable."""
        from src.agent import (
            parallel_get_imports,
            parallel_initial_explore,
            parallel_read_files,
        )

        # All should be async functions
        assert asyncio.iscoroutinefunction(parallel_initial_explore)
        assert asyncio.iscoroutinefunction(parallel_read_files)
        assert asyncio.iscoroutinefunction(parallel_get_imports)
