"""
File exploration tools for codebase analysis.
Deterministic, CLI-first operations - no AI, just file system operations.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool

# Directories to always skip
IGNORE_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "eggs",
    "*.egg-info",
    ".idea",
    ".vscode",
    "vendor",
    "target",  # Rust/Java
    "out",
    "bin",
    "obj",  # C#
}

# File extensions to prioritize
CODE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".php",
    ".cs",
    ".cpp",
    ".c",
    ".h",
    ".swift",
    ".kt",
    ".scala",
    ".vue",
    ".svelte",
}

CONFIG_FILES = {
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Gemfile",
    "composer.json",
    "Makefile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env.example",
    "tsconfig.json",
    "vite.config.ts",
    "next.config.js",
    "webpack.config.js",
}


def should_ignore(path: Path) -> bool:
    """Check if a path should be ignored."""
    parts = path.parts
    for part in parts:
        if part in IGNORE_DIRS:
            return True
        if part.startswith(".") and part not in {".github", ".env.example"}:
            return True
    return False


@tool
def list_directory_structure(repo_path: str, max_depth: int = 4) -> str:
    """
    List the directory structure of a repository, filtering out noise.

    Args:
        repo_path: Path to the repository root
        max_depth: Maximum depth to traverse (default: 4)

    Returns:
        A formatted tree structure of the codebase
    """
    repo = Path(repo_path)
    if not repo.exists():
        return f"Error: Path '{repo_path}' does not exist"

    lines = [f"📁 {repo.name}/"]

    def walk(current: Path, prefix: str = "", depth: int = 0):
        if depth >= max_depth:
            return

        try:
            entries = sorted(current.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            return

        # Filter entries
        entries = [e for e in entries if not should_ignore(e)]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "

            if entry.is_dir():
                lines.append(f"{prefix}{connector}📁 {entry.name}/")
                extension = "    " if is_last else "│   "
                walk(entry, prefix + extension, depth + 1)
            else:
                # Mark important files
                icon = "📄"
                if entry.name in CONFIG_FILES:
                    icon = "⚙️"
                elif entry.suffix in CODE_EXTENSIONS:
                    icon = "📝"
                elif entry.name == "README.md":
                    icon = "📖"

                lines.append(f"{prefix}{connector}{icon} {entry.name}")

    walk(repo)

    return "\n".join(lines)


@tool
def read_file(file_path: str, max_lines: int = 500) -> str:
    """
    Read the contents of a file.

    Args:
        file_path: Path to the file to read
        max_lines: Maximum number of lines to read (default: 500)

    Returns:
        The file contents with line numbers, or an error message
    """
    path = Path(file_path)

    if not path.exists():
        return f"Error: File '{file_path}' does not exist"

    if not path.is_file():
        return f"Error: '{file_path}' is not a file"

    # Check file size (skip very large files)
    size = path.stat().st_size
    if size > 1_000_000:  # 1MB
        return f"Error: File too large ({size:,} bytes). Consider reading a specific section."

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading file: {e}"

    total_lines = len(lines)
    lines = lines[:max_lines]

    # Format with line numbers
    numbered_lines = []
    for i, line in enumerate(lines, 1):
        numbered_lines.append(f"{i:4d} | {line.rstrip()}")

    result = f"📄 {path.name} ({total_lines} lines)\n"
    result += "─" * 50 + "\n"
    result += "\n".join(numbered_lines)

    if total_lines > max_lines:
        result += f"\n\n... truncated ({total_lines - max_lines} more lines)"

    return result


@tool
def search_code(repo_path: str, pattern: str, file_extension: Optional[str] = None, max_results: int = 20) -> str:
    """
    Search for a pattern in the codebase using grep/ripgrep.

    Args:
        repo_path: Path to the repository root
        pattern: Regex pattern to search for
        file_extension: Optional file extension filter (e.g., ".py", ".ts")
        max_results: Maximum number of results (default: 20)

    Returns:
        Matching lines with file paths and line numbers
    """
    repo = Path(repo_path)
    if not repo.exists():
        return f"Error: Path '{repo_path}' does not exist"

    # Build grep command
    # Try ripgrep first, fall back to grep
    try:
        # Check if rg is available
        subprocess.run(["rg", "--version"], capture_output=True, check=True)
        use_rg = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        use_rg = False

    exclude_args = []
    for d in IGNORE_DIRS:
        if use_rg:
            exclude_args.extend(["--glob", f"!{d}/**"])
        else:
            exclude_args.extend(["--exclude-dir", d])

    if use_rg:
        cmd = ["rg", "--line-number", "--no-heading", "--color=never", "-m", str(max_results)]
        cmd.extend(exclude_args)
        if file_extension:
            cmd.extend(["--glob", f"*{file_extension}"])
        cmd.extend([pattern, str(repo)])
    else:
        cmd = ["grep", "-rn", "--include=*"]
        if file_extension:
            cmd = ["grep", "-rn", f"--include=*{file_extension}"]
        cmd.extend(exclude_args)
        cmd.extend([pattern, str(repo)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "Error: Search timed out"
    except Exception as e:
        return f"Error running search: {e}"

    if not output:
        return f"No matches found for pattern: '{pattern}'"

    # Format output
    lines = output.split("\n")[:max_results]
    formatted = [f"🔍 Search results for '{pattern}':", "─" * 50]

    for line in lines:
        # Make paths relative
        line = line.replace(str(repo) + "/", "")
        formatted.append(line)

    if len(lines) >= max_results:
        formatted.append(f"\n... showing first {max_results} results")

    return "\n".join(formatted)


@tool
def find_files_by_pattern(repo_path: str, pattern: str, max_results: int = 30) -> str:
    """
    Find files matching a glob pattern.

    Args:
        repo_path: Path to the repository root
        pattern: Glob pattern (e.g., "*.py", "**/*test*.py", "src/**/*.ts")
        max_results: Maximum number of results (default: 30)

    Returns:
        List of matching file paths
    """
    repo = Path(repo_path)
    if not repo.exists():
        return f"Error: Path '{repo_path}' does not exist"

    matches = []
    for path in repo.glob(pattern):
        if should_ignore(path):
            continue
        if path.is_file():
            matches.append(str(path.relative_to(repo)))
        if len(matches) >= max_results:
            break

    if not matches:
        return f"No files found matching pattern: '{pattern}'"

    result = [f"📁 Files matching '{pattern}':", "─" * 50]
    result.extend(matches)

    if len(matches) >= max_results:
        result.append(f"\n... showing first {max_results} results")

    return "\n".join(result)
