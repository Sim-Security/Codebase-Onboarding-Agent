"""
Unit tests for all 8 codebase exploration tools.

Tests cover:
- list_directory_structure
- read_file
- search_code
- find_files_by_pattern
- get_imports
- find_entry_points
- analyze_dependencies
- get_function_signatures
"""

from pathlib import Path

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

# =============================================================================
# Test: list_directory_structure
# =============================================================================


class TestListDirectoryStructure:
    """Tests for list_directory_structure tool."""

    def test_lists_basic_structure(self, temp_repo: Path):
        """Should list files and directories in repo."""
        result = list_directory_structure.invoke({"repo_path": str(temp_repo)})

        assert "📁" in result  # Directory icon
        assert "src/" in result
        assert "main.py" in result
        assert "README.md" in result

    def test_respects_max_depth(self, temp_repo: Path):
        """Should respect max_depth parameter."""
        # Create deep nested structure
        deep_path = temp_repo / "a" / "b" / "c" / "d" / "e"
        deep_path.mkdir(parents=True)
        (deep_path / "deep.py").write_text("# Deep file")

        # With depth 2, should not see deep files
        result = list_directory_structure.invoke(
            {"repo_path": str(temp_repo), "max_depth": 2}
        )

        assert "deep.py" not in result

    def test_ignores_node_modules(self, temp_repo: Path):
        """Should ignore node_modules directory."""
        (temp_repo / "node_modules").mkdir()
        (temp_repo / "node_modules" / "express").mkdir()
        (temp_repo / "node_modules" / "express" / "index.js").write_text("")

        result = list_directory_structure.invoke({"repo_path": str(temp_repo)})

        assert "node_modules" not in result
        assert "express" not in result

    def test_ignores_git_directory(self, temp_repo: Path):
        """Should ignore .git directory."""
        (temp_repo / ".git").mkdir()
        (temp_repo / ".git" / "config").write_text("")

        result = list_directory_structure.invoke({"repo_path": str(temp_repo)})

        # .git should not appear
        lines = result.split("\n")
        git_lines = [l for l in lines if ".git" in l and ".github" not in l]
        assert len(git_lines) == 0

    def test_handles_nonexistent_path(self):
        """Should return error for nonexistent path."""
        result = list_directory_structure.invoke({"repo_path": "/nonexistent/path"})

        assert "Error" in result
        assert "does not exist" in result

    def test_marks_config_files(self, temp_repo: Path):
        """Should mark config files with gear icon."""
        result = list_directory_structure.invoke({"repo_path": str(temp_repo)})

        # package.json should have gear icon
        assert "⚙️" in result

    def test_marks_readme(self, temp_repo: Path):
        """Should mark README with book icon."""
        result = list_directory_structure.invoke({"repo_path": str(temp_repo)})

        assert "📖" in result  # Book icon for README


# =============================================================================
# Test: read_file
# =============================================================================


class TestReadFile:
    """Tests for read_file tool."""

    def test_reads_python_file(self, temp_repo: Path):
        """Should read Python file with line numbers."""
        result = read_file.invoke({"file_path": str(temp_repo / "src" / "main.py")})

        assert "main.py" in result
        assert "def main():" in result
        assert "1 |" in result or "   1 |" in result  # Line number format

    def test_respects_max_lines(self, temp_repo: Path):
        """Should respect max_lines parameter."""
        # Create file with many lines
        many_lines = "\n".join([f"line {i}" for i in range(100)])
        (temp_repo / "large.py").write_text(many_lines)

        result = read_file.invoke(
            {"file_path": str(temp_repo / "large.py"), "max_lines": 10}
        )

        assert "truncated" in result.lower()

    def test_handles_nonexistent_file(self, temp_repo: Path):
        """Should return error for nonexistent file."""
        result = read_file.invoke({"file_path": str(temp_repo / "nonexistent.py")})

        assert "Error" in result
        assert "does not exist" in result

    def test_blocks_env_file(self, temp_repo_with_sensitive_files: Path):
        """SEC-003: Should block .env files."""
        result = read_file.invoke(
            {"file_path": str(temp_repo_with_sensitive_files / ".env")}
        )

        assert "BLOCKED" in result
        assert "sensitive" in result.lower()
        # Should NOT contain actual secrets
        assert "super_secret" not in result

    def test_blocks_credentials_json(self, temp_repo_with_sensitive_files: Path):
        """SEC-003: Should block credentials files."""
        result = read_file.invoke(
            {"file_path": str(temp_repo_with_sensitive_files / "credentials.json")}
        )

        assert "BLOCKED" in result

    def test_allows_env_example(self, temp_repo_with_sensitive_files: Path):
        """SEC-003: Should allow .env.example files."""
        result = read_file.invoke(
            {"file_path": str(temp_repo_with_sensitive_files / ".env.example")}
        )

        # Should be readable
        assert "BLOCKED" not in result
        assert "your_secret_here" in result

    def test_filters_injection_patterns(self, temp_repo_with_injection: Path):
        """SEC-002: Should filter prompt injection patterns."""
        result = read_file.invoke(
            {"file_path": str(temp_repo_with_injection / "malicious.py")}
        )

        assert "FILTERED" in result
        assert "injection" in result.lower()

    def test_filters_llm_tokens(self, temp_repo_with_injection: Path):
        """SEC-002: Should filter LLM special tokens."""
        result = read_file.invoke(
            {"file_path": str(temp_repo_with_injection / "llm_tokens.txt")}
        )

        assert "FILTERED" in result

    def test_allows_safe_ignore_keyword(self, temp_repo_with_injection: Path):
        """SEC-002: Should allow safe usage of 'ignore' keyword."""
        result = read_file.invoke(
            {"file_path": str(temp_repo_with_injection / "safe_ignore.py")}
        )

        # Should NOT be filtered
        assert "FILTERED" not in result
        assert "def ignore_errors" in result


# =============================================================================
# Test: search_code
# =============================================================================


class TestSearchCode:
    """Tests for search_code tool."""

    def test_finds_pattern_in_files(self, temp_repo: Path):
        """Should find pattern matches across files."""
        result = search_code.invoke(
            {"repo_path": str(temp_repo), "pattern": "def main"}
        )

        assert "main" in result
        assert "Search results" in result

    def test_filters_by_extension(self, temp_repo: Path):
        """Should filter by file extension."""
        result = search_code.invoke(
            {"repo_path": str(temp_repo), "pattern": "def", "file_extension": ".py"}
        )

        assert "def" in result
        # Results should only be from .py files
        assert (
            ".js" not in result or "package.json" in result
        )  # package.json is config, not code search result

    def test_respects_max_results(self, temp_repo: Path):
        """Should respect max_results parameter."""
        result = search_code.invoke(
            {"repo_path": str(temp_repo), "pattern": "import", "max_results": 2}
        )

        # Should indicate truncation or have limited results
        lines = [l for l in result.split("\n") if ":" in l and "import" in l.lower()]
        assert len(lines) <= 3  # Allow some header lines

    def test_returns_no_matches_message(self, temp_repo: Path):
        """Should return message when no matches found."""
        result = search_code.invoke(
            {"repo_path": str(temp_repo), "pattern": "xyznonexistentpattern123"}
        )

        assert "No matches" in result

    def test_handles_regex_patterns(self, temp_repo: Path):
        """Should handle regex patterns."""
        result = search_code.invoke(
            {"repo_path": str(temp_repo), "pattern": r"def\s+\w+\("}
        )

        # Should match function definitions
        assert "def" in result


# =============================================================================
# Test: find_files_by_pattern
# =============================================================================


class TestFindFilesByPattern:
    """Tests for find_files_by_pattern tool."""

    def test_finds_python_files(self, temp_repo: Path):
        """Should find files matching glob pattern."""
        result = find_files_by_pattern.invoke(
            {"repo_path": str(temp_repo), "pattern": "**/*.py"}
        )

        assert "main.py" in result
        assert "utils.py" in result

    def test_finds_files_in_subdirectory(self, temp_repo: Path):
        """Should find files in subdirectories."""
        result = find_files_by_pattern.invoke(
            {"repo_path": str(temp_repo), "pattern": "src/*.py"}
        )

        assert "main.py" in result

    def test_respects_max_results(self, temp_repo: Path):
        """Should respect max_results parameter."""
        # Create many files
        for i in range(50):
            (temp_repo / f"file{i}.txt").write_text(f"content {i}")

        result = find_files_by_pattern.invoke(
            {"repo_path": str(temp_repo), "pattern": "*.txt", "max_results": 5}
        )

        # Count .txt files in result
        txt_count = result.count(".txt")
        assert txt_count <= 6  # 5 results + possible "showing first 5"

    def test_ignores_node_modules(self, temp_repo: Path):
        """Should ignore files in node_modules."""
        (temp_repo / "node_modules").mkdir()
        (temp_repo / "node_modules" / "test.js").write_text("")

        result = find_files_by_pattern.invoke(
            {"repo_path": str(temp_repo), "pattern": "**/*.js"}
        )

        # node_modules files should not appear
        assert "node_modules" not in result

    def test_returns_no_matches_message(self, temp_repo: Path):
        """Should return message when no files found."""
        result = find_files_by_pattern.invoke(
            {"repo_path": str(temp_repo), "pattern": "*.nonexistent"}
        )

        assert "No files found" in result


# =============================================================================
# Test: get_imports
# =============================================================================


class TestGetImports:
    """Tests for get_imports tool."""

    def test_extracts_python_imports(self, temp_repo: Path):
        """Should extract Python imports."""
        result = get_imports.invoke({"file_path": str(temp_repo / "src" / "main.py")})

        assert "Imports" in result
        assert "os" in result
        assert "json" in result
        assert "typing" in result

    def test_categorizes_stdlib_vs_thirdparty(self, temp_repo: Path):
        """Should categorize standard library vs third-party."""
        # Create file with mixed imports
        (temp_repo / "mixed_imports.py").write_text("""
import os
import sys
from pathlib import Path
import requests
from langchain import LLM
""")

        result = get_imports.invoke({"file_path": str(temp_repo / "mixed_imports.py")})

        assert "Standard Library" in result
        assert "Third-Party" in result

    def test_handles_typescript_imports(self, temp_repo_multilang: Path):
        """Should handle TypeScript imports."""
        result = get_imports.invoke(
            {"file_path": str(temp_repo_multilang / "src" / "app.ts")}
        )

        assert "express" in result

    def test_handles_relative_imports(self, temp_repo: Path):
        """Should identify relative imports."""
        (temp_repo / "with_relative.py").write_text("""
from .utils import helper
from ..config import settings
import os
""")

        result = get_imports.invoke({"file_path": str(temp_repo / "with_relative.py")})

        assert "Local/Relative" in result or ".utils" in result

    def test_handles_unsupported_extension(self, temp_repo: Path):
        """Should handle unsupported file types."""
        result = get_imports.invoke({"file_path": str(temp_repo / "README.md")})

        assert "Error" in result or "Unsupported" in result

    def test_handles_file_with_no_imports(self, temp_repo: Path):
        """Should handle file with no imports."""
        (temp_repo / "no_imports.py").write_text("x = 1\ny = 2\n")

        result = get_imports.invoke({"file_path": str(temp_repo / "no_imports.py")})

        assert "No imports" in result


# =============================================================================
# Test: find_entry_points
# =============================================================================


class TestFindEntryPoints:
    """Tests for find_entry_points tool."""

    def test_finds_python_main(self, temp_repo: Path):
        """Should find main.py as entry point."""
        result = find_entry_points.invoke({"repo_path": str(temp_repo)})

        assert "Entry Points" in result
        assert "main.py" in result
        assert "python" in result.lower()

    def test_finds_package_json_scripts(self, temp_repo: Path):
        """Should find package.json scripts."""
        result = find_entry_points.invoke({"repo_path": str(temp_repo)})

        assert "npm start" in result or "index.js" in result

    def test_finds_go_main(self, temp_repo_multilang: Path):
        """Should find Go entry points."""
        result = find_entry_points.invoke({"repo_path": str(temp_repo_multilang)})

        assert "main.go" in result
        assert "go" in result.lower()

    def test_ignores_venv_entries(self, temp_repo: Path):
        """Should ignore entry points in virtual environments."""
        (temp_repo / "venv").mkdir()
        (temp_repo / "venv" / "main.py").write_text("")

        result = find_entry_points.invoke({"repo_path": str(temp_repo)})

        # Should only list the real main.py, not the one in venv
        lines = result.split("\n")
        main_lines = [l for l in lines if "main.py" in l]
        # Should not include venv/main.py
        venv_entries = [l for l in main_lines if "venv" in l]
        assert len(venv_entries) == 0


# =============================================================================
# Test: analyze_dependencies
# =============================================================================


class TestAnalyzeDependencies:
    """Tests for analyze_dependencies tool."""

    def test_reads_requirements_txt(self, temp_repo: Path):
        """Should read requirements.txt."""
        result = analyze_dependencies.invoke({"repo_path": str(temp_repo)})

        assert "Python" in result
        assert "requirements.txt" in result
        assert "langchain" in result
        assert "gradio" in result

    def test_reads_package_json(self, temp_repo: Path):
        """Should read package.json dependencies."""
        result = analyze_dependencies.invoke({"repo_path": str(temp_repo)})

        assert "Node.js" in result
        assert "express" in result

    def test_reads_package_json_devdeps(self, temp_repo: Path):
        """Should read devDependencies from package.json."""
        result = analyze_dependencies.invoke({"repo_path": str(temp_repo)})

        assert "devDependencies" in result
        assert "nodemon" in result

    def test_reads_cargo_toml(self, temp_repo_multilang: Path):
        """Should read Rust Cargo.toml."""
        result = analyze_dependencies.invoke({"repo_path": str(temp_repo_multilang)})

        assert "Rust" in result
        assert "serde" in result
        assert "tokio" in result

    def test_handles_repo_without_deps(self, temp_repo: Path):
        """Should handle repo without dependency files."""
        # Remove dependency files
        (temp_repo / "requirements.txt").unlink()
        (temp_repo / "package.json").unlink()

        result = analyze_dependencies.invoke({"repo_path": str(temp_repo)})

        assert "No dependency files found" in result or "Dependency Analysis" in result


# =============================================================================
# Test: get_function_signatures
# =============================================================================


class TestGetFunctionSignatures:
    """Tests for get_function_signatures tool."""

    def test_extracts_python_functions(self, temp_repo: Path):
        """Should extract Python function signatures."""
        result = get_function_signatures.invoke(
            {"file_path": str(temp_repo / "src" / "main.py")}
        )

        assert "Signatures" in result
        assert "main" in result
        assert "helper" in result

    def test_extracts_python_classes(self, temp_repo: Path):
        """Should extract Python class definitions."""
        result = get_function_signatures.invoke(
            {"file_path": str(temp_repo / "src" / "utils.py")}
        )

        assert "class" in result
        assert "DataProcessor" in result

    def test_includes_line_numbers(self, temp_repo: Path):
        """Should include line numbers."""
        result = get_function_signatures.invoke(
            {"file_path": str(temp_repo / "src" / "main.py")}
        )

        # Should have L<number> format
        assert "L" in result

    def test_extracts_typescript_functions(self, temp_repo_multilang: Path):
        """Should extract TypeScript functions."""
        result = get_function_signatures.invoke(
            {"file_path": str(temp_repo_multilang / "src" / "app.ts")}
        )

        assert "createApp" in result

    def test_extracts_go_functions(self, temp_repo_multilang: Path):
        """Should extract Go function signatures."""
        result = get_function_signatures.invoke(
            {"file_path": str(temp_repo_multilang / "main.go")}
        )

        assert "main" in result
        assert "Server" in result

    def test_handles_file_without_functions(self, temp_repo: Path):
        """Should handle file with no functions."""
        (temp_repo / "empty.py").write_text("X = 1\nY = 2\n")

        result = get_function_signatures.invoke(
            {"file_path": str(temp_repo / "empty.py")}
        )

        assert "No functions" in result


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_permission_error(self, temp_repo: Path):
        """Should handle permission errors gracefully."""
        # Create a file we can't read (on Unix)
        import os

        if os.name == "posix":
            restricted = temp_repo / "restricted.py"
            restricted.write_text("secret")
            restricted.chmod(0o000)

            result = read_file.invoke({"file_path": str(restricted)})

            # Restore permissions for cleanup
            restricted.chmod(0o644)

            assert "Error" in result

    def test_handles_binary_files(self, temp_repo: Path):
        """Should handle binary files gracefully."""
        (temp_repo / "binary.bin").write_bytes(b"\x00\x01\x02\x03")

        result = read_file.invoke({"file_path": str(temp_repo / "binary.bin")})

        # Should not crash, may have replacement characters
        assert result is not None

    def test_handles_empty_file(self, temp_repo: Path):
        """Should handle empty files."""
        (temp_repo / "empty.py").write_text("")

        result = read_file.invoke({"file_path": str(temp_repo / "empty.py")})

        assert "empty.py" in result
