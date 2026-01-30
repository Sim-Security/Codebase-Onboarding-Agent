"""
File exploration tools for codebase analysis.
Deterministic, CLI-first operations - no AI, just file system operations.
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool


# =============================================================================
# SEC-001: Symlink Escape Prevention
# Prevents reading files outside repo via symlinks
# =============================================================================
def is_path_safe(file_path: str, repo_path: str) -> tuple[bool, str]:
    """
    Check if a file path is safe to read (within repo boundaries).

    Prevents symlink escape attacks where symlinks point outside the repo.

    Args:
        file_path: Path to check
        repo_path: Repository root path

    Returns:
        (is_safe, error_message)
    """
    try:
        # Resolve symlinks and normalize path
        resolved = Path(file_path).resolve()
        repo_resolved = Path(repo_path).resolve()

        # Check if resolved path is within repo
        try:
            resolved.relative_to(repo_resolved)
            return True, ""
        except ValueError:
            return (
                False,
                f"Path escapes repository: {resolved} is not within {repo_resolved}",
            )
    except Exception as e:
        return False, f"Path resolution error: {e}"


# =============================================================================
# SEC-002: Prompt Injection Patterns
# Patterns that could be used for prompt injection attacks in malicious repos
# =============================================================================
# Enhanced injection patterns
INJECTION_PATTERNS = [
    # Original patterns
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(all\s+)?(your\s+)?previous",
    r"disregard\s+(all\s+)?prior",
    r"system\s*:\s*you\s+are",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<\|system\|>",
    r"<\|user\|>",
    r"<\|assistant\|>",
    # New patterns for V3
    r"ignore\s+(?:the\s+)?(?:above|previous|prior)\s+(?:instructions?|prompts?|context)",
    r"new\s+instructions?\s*:",
    r"override\s+(?:all\s+)?(?:previous\s+)?(?:instructions?|settings?)",
    r"you\s+are\s+now\s+(?:a|an)\s+",
    r"act\s+as\s+(?:if\s+you\s+are|a|an)\s+",
    r"pretend\s+(?:you\s+are|to\s+be)\s+",
    r"roleplay\s+as\s+",
    r"jailbreak",
    r"bypass\s+(?:all\s+)?(?:restrictions?|filters?|rules?)",
    r"do\s+not\s+follow\s+(?:your\s+)?(?:instructions?|guidelines?)",
]

# Unicode homoglyphs that could be used to bypass filters
HOMOGLYPH_MAP = {
    "а": "a",
    "е": "e",
    "і": "i",
    "о": "o",
    "р": "p",
    "с": "c",
    "у": "y",
    "х": "x",
    "А": "A",
    "В": "B",
    "С": "C",
    "Е": "E",
    "Н": "H",
    "К": "K",
    "М": "M",
    "О": "O",
    "Р": "P",
    "Т": "T",
    "Х": "X",
    "０": "0",
    "１": "1",
    "２": "2",
    "３": "3",
    "４": "4",
    "５": "5",
    "６": "6",
    "７": "7",
    "８": "8",
    "９": "9",
    "ⅰ": "i",
    "ⅿ": "m",
    "ⅾ": "d",
}

# L33t speak substitutions
LEET_MAP = {
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "@": "a",
    "$": "s",
    "!": "i",
    "|": "l",
}


def normalize_text(text: str) -> str:
    """
    Normalize text by replacing homoglyphs and l33t speak.

    Args:
        text: Input text that may contain obfuscated characters

    Returns:
        Normalized text with standard ASCII characters
    """
    result = text

    # Replace homoglyphs
    for homoglyph, replacement in HOMOGLYPH_MAP.items():
        result = result.replace(homoglyph, replacement)

    # Replace l33t speak
    for leet, replacement in LEET_MAP.items():
        result = result.replace(leet, replacement)

    return result


def detect_base64_injection(content: str) -> bool:
    """
    Detect potential base64-encoded injection attempts.

    Args:
        content: File content to check

    Returns:
        True if base64-encoded injection detected
    """
    import base64

    # Look for base64-like strings
    base64_pattern = r"[A-Za-z0-9+/]{40,}={0,2}"
    matches = re.findall(base64_pattern, content)

    for match in matches[:10]:  # Check first 10 matches
        try:
            decoded = base64.b64decode(match).decode("utf-8", errors="ignore").lower()
            # Check if decoded content contains injection patterns
            for pattern in INJECTION_PATTERNS[:5]:  # Check main patterns
                if re.search(pattern, decoded, re.IGNORECASE):
                    return True
        except Exception:
            pass

    return False


def sanitize_content(content: str, file_path: str = "") -> tuple[str, bool]:
    """
    Check content for prompt injection patterns.

    Enhanced for V3 with:
    - Unicode homoglyph detection
    - Base64 encoded injection detection
    - L33t speak normalization

    Args:
        content: The file content to check
        file_path: Optional path for logging

    Returns:
        (content, was_filtered) - If filtered, content is replacement message
    """
    # Normalize text to catch obfuscation
    normalized = normalize_text(content.lower())

    # Check normalized content against patterns
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            logging.warning(f"Injection pattern detected in {file_path}: {pattern}")
            return "[CONTENT FILTERED - Potential injection pattern detected]", True

    # Check for base64 encoded injections
    if detect_base64_injection(content):
        logging.warning(f"Base64 encoded injection detected in {file_path}")
        return "[CONTENT FILTERED - Potential encoded injection detected]", True

    return content, False


# =============================================================================
# SEC-003: Sensitive File Blocklist
# Files that typically contain secrets or credentials
# =============================================================================
SENSITIVE_FILES = {
    # Environment files
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    ".env.staging",
    # Credential files
    "credentials.json",
    "credentials.yaml",
    "credentials.yml",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "service-account.json",
    "service_account.json",
    # SSH/Auth keys
    "id_rsa",
    "id_rsa.pub",
    "id_ed25519",
    "id_ed25519.pub",
    "id_dsa",
    "id_ecdsa",
    # Package manager auth
    ".npmrc",
    ".pypirc",
    ".netrc",
    # Cloud credentials
    ".aws/credentials",
    ".gcloud/credentials",
}

SENSITIVE_EXTENSIONS = {".pem", ".key", ".p12", ".pfx"}

# =============================================================================
# SMART-003: Trivial File Skip List
# Files that typically waste context and should be skipped
# =============================================================================
TRIVIAL_FILE_PATTERNS = {
    "__init__.py": lambda content: len(content.strip()) == 0
    or len(content.strip().split("\n")) < 5,
    "index.ts": lambda content: _is_reexport_only(content),
    "index.js": lambda content: _is_reexport_only(content),
    "index.tsx": lambda content: _is_reexport_only(content),
}

GENERATED_FILE_MARKERS = [
    "DO NOT EDIT",
    "AUTO-GENERATED",
    "AUTOGENERATED",
    "@generated",
    "Generated by",
    "This file was automatically generated",
    "This file is auto-generated",
    "Code generated by",
]


def _is_reexport_only(content: str) -> bool:
    """Check if file only contains export/re-export statements."""
    lines = [
        l.strip()
        for l in content.split("\n")
        if l.strip() and not l.strip().startswith("//")
    ]
    if len(lines) == 0:
        return True

    # All lines are exports
    export_patterns = [
        r"^export\s+",
        r"^export\s*\{",
        r"^export\s*\*",
        r"^module\.exports",
    ]

    for line in lines:
        if not any(re.match(p, line) for p in export_patterns):
            return False
    return True


def is_trivial_file(file_path: str, content: str) -> tuple[bool, str]:
    """
    Check if a file is trivial and should be skipped.

    Returns:
        (is_trivial, reason)
    """
    filename = Path(file_path).name

    # Check filename patterns
    if filename in TRIVIAL_FILE_PATTERNS:
        if TRIVIAL_FILE_PATTERNS[filename](content):
            return True, f"Trivial {filename} (empty or minimal)"

    # Check for generated file markers in header
    header = content[:1000]
    for marker in GENERATED_FILE_MARKERS:
        if marker.lower() in header.lower():
            return True, f"Generated file (contains '{marker}')"

    # Check for very small files
    lines = [l for l in content.split("\n") if l.strip()]
    if len(lines) < 3:
        return True, f"Minimal content ({len(lines)} lines)"

    return False, ""


def is_generated_file(content: str) -> bool:
    """Check if file appears to be auto-generated."""
    header = content[:1000]
    return any(marker.lower() in header.lower() for marker in GENERATED_FILE_MARKERS)


def is_sensitive_file(file_path: str) -> bool:
    """
    Check if a file should be blocked from reading due to sensitive content.

    Args:
        file_path: Path to the file

    Returns:
        True if the file should be blocked
    """
    path = Path(file_path)
    name = path.name

    # Check exact filename match
    if name in SENSITIVE_FILES:
        return True

    # Check extension
    if path.suffix in SENSITIVE_EXTENSIONS:
        return True

    # Check parent directories for credential paths
    parts = path.parts
    if ".aws" in parts or ".gcloud" in parts or ".ssh" in parts:
        return True

    return False


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
            entries = sorted(
                current.iterdir(), key=lambda x: (x.is_file(), x.name.lower())
            )
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
def read_file(file_path: str, max_lines: int = 500, force: bool = False) -> str:
    """
    Read the contents of a file.

    Args:
        file_path: Path to the file to read
        max_lines: Maximum number of lines to read (default: 500)
        force: If True, read even if file is trivial/low-importance

    Returns:
        The file contents with line numbers, or an error/skip message
    """
    path = Path(file_path)

    # SEC-003: Block sensitive files
    if is_sensitive_file(file_path):
        return f"[BLOCKED] Cannot read '{file_path}' - potential sensitive file containing secrets"

    # SEC-001: Symlink escape prevention
    # We need repo_path to validate, but read_file doesn't have it
    # For now, resolve and check the path doesn't go to sensitive system directories
    try:
        resolved_path = path.resolve()
        # Block if resolved path is in sensitive system directories
        sensitive_dirs = ["/etc", "/root", "/home", "/var", "/usr", "/bin", "/sbin"]
        resolved_str = str(resolved_path)

        # Only block if it's clearly outside a code repository context
        if any(
            resolved_str.startswith(sd)
            and "/Projects/" not in resolved_str
            and "/repos/" not in resolved_str
            for sd in sensitive_dirs
        ):
            # Check if this might be a symlink escape
            if path.is_symlink():
                return (
                    f"[BLOCKED] Symlink escape detected: {file_path} -> {resolved_path}"
                )
    except Exception as e:
        logging.warning(f"Path resolution error for {file_path}: {e}")

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
            content = f.read()
    except Exception as e:
        return f"Error reading file: {e}"

    # Check if trivial (unless forced)
    if not force:
        is_triv, reason = is_trivial_file(file_path, content)
        if is_triv:
            logging.info(f"Skipping trivial file {file_path}: {reason}")
            return f"[SKIPPED] {path.name} - {reason}\nUse force=True to read anyway."

    # Format with line numbers
    lines = content.split("\n")
    total_lines = len(lines)
    lines = lines[:max_lines]

    numbered_lines = []
    for i, line in enumerate(lines, 1):
        numbered_lines.append(f"{i:4d} | {line.rstrip()}")

    formatted_content = "\n".join(numbered_lines)

    # SEC-002: Check for prompt injection patterns
    formatted_content, was_filtered = sanitize_content(formatted_content, file_path)

    if was_filtered:
        result = f"[SECURITY] File {path.name} contained potentially unsafe content\n"
        result += formatted_content
        return result

    result = f"📄 {path.name} ({total_lines} lines)\n"
    result += "─" * 50 + "\n"
    result += formatted_content

    if total_lines > max_lines:
        result += f"\n\n... truncated ({total_lines - max_lines} more lines)"

    return result


def safe_read_file(
    file_path: str, repo_path: str, max_lines: int = 500, force: bool = False
) -> str:
    """
    Safely read a file, ensuring it's within the repository.

    Args:
        file_path: Path to the file to read
        repo_path: Repository root path for safety validation
        max_lines: Maximum number of lines to read
        force: If True, read even if file is trivial

    Returns:
        File contents or error message
    """
    # SEC-001: Validate path is within repo
    is_safe, error = is_path_safe(file_path, repo_path)
    if not is_safe:
        return f"[BLOCKED] {error}"

    # Delegate to regular read_file
    return read_file.invoke(
        {"file_path": file_path, "max_lines": max_lines, "force": force}
    )


@tool
def search_code(
    repo_path: str,
    pattern: str,
    file_extension: Optional[str] = None,
    max_results: int = 20,
) -> str:
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
        cmd = [
            "rg",
            "--line-number",
            "--no-heading",
            "--color=never",
            "-m",
            str(max_results),
        ]
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
