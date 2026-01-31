"""
Code analysis tools for understanding codebase structure.
Deterministic operations - parsing, not AI inference.
"""

import json
import re
from pathlib import Path

from langchain_core.tools import tool

# CLI framework detection patterns by language
CLI_FRAMEWORK_PATTERNS = {
    "python": {
        "click": r"@click\.(command|group|option|argument)",
        "typer": r"@app\.(command|callback)",
        "argparse": r"ArgumentParser\(\)",
        "fire": r"fire\.Fire\(",
        "docopt": r"docopt\(__doc__",
    },
    "rust": {
        "clap": r"#\[derive\(.*(?:Parser|Args|Subcommand)",
        "structopt": r"#\[structopt",
    },
    "go": {
        "cobra": r"cobra\.Command\{",
        "urfave_cli": r"cli\.App\{",
    },
}

# Entry point patterns by language
ENTRY_POINT_PATTERNS = {
    "python": [
        "main.py",
        "app.py",
        "__main__.py",
        "run.py",
        "server.py",
        "cli.py",
        "manage.py",  # Django
        "wsgi.py",
        "asgi.py",
    ],
    "javascript": [
        "index.js",
        "index.ts",
        "index.tsx",
        "main.js",
        "main.ts",
        "app.js",
        "app.ts",
        "server.js",
        "server.ts",
    ],
    "go": ["main.go", "cmd/main.go"],
    "rust": ["main.rs", "lib.rs"],
    "java": ["Main.java", "Application.java"],
}

# Import patterns by language
IMPORT_PATTERNS = {
    ".py": [
        r"^import\s+(\S+)",
        r"^from\s+(\S+)\s+import",
    ],
    ".ts": [
        r"^import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
        r"^import\s+['\"]([^'\"]+)['\"]",
        r"^export\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
    ],
    ".tsx": [
        r"^import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
        r"^import\s+['\"]([^'\"]+)['\"]",
    ],
    ".js": [
        r"^import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
        r"^const\s+\w+\s*=\s*require\(['\"]([^'\"]+)['\"]\)",
        r"^require\(['\"]([^'\"]+)['\"]\)",
    ],
    ".jsx": [
        r"^import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
    ],
    ".go": [
        r"^import\s+['\"]([^'\"]+)['\"]",
        r"^\s+['\"]([^'\"]+)['\"]",  # Multi-line import
    ],
    ".rs": [
        r"^use\s+(\S+)",
        r"^extern\s+crate\s+(\S+)",
    ],
}


@tool
def get_imports(file_path: str) -> str:
    """
    Extract import statements from a source file.

    Args:
        file_path: Path to the source file

    Returns:
        List of imports categorized by type (standard library, third-party, local)
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File '{file_path}' does not exist"

    suffix = path.suffix.lower()
    if suffix not in IMPORT_PATTERNS:
        return f"Error: Unsupported file type '{suffix}'"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return f"Error reading file: {e}"

    patterns = IMPORT_PATTERNS[suffix]
    imports = set()

    for line in content.split("\n"):
        line = line.strip()
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                imports.add(match.group(1))

    if not imports:
        return f"No imports found in {path.name}"

    # Categorize imports
    stdlib = []
    third_party = []
    local = []

    for imp in sorted(imports):
        if imp.startswith(".") or imp.startswith("./") or imp.startswith("../"):
            local.append(imp)
        elif suffix == ".py":
            # Python standard library check (simplified)
            if imp.split(".")[0] in {
                "os",
                "sys",
                "re",
                "json",
                "typing",
                "pathlib",
                "collections",
                "datetime",
                "time",
                "logging",
                "subprocess",
                "asyncio",
                "functools",
                "itertools",
                "dataclasses",
                "abc",
                "enum",
                "copy",
                "io",
                "math",
                "random",
                "string",
                "tempfile",
                "shutil",
                "glob",
                "argparse",
                "unittest",
                "threading",
                "multiprocessing",
                "socket",
                "http",
                "urllib",
                "email",
                "html",
                "xml",
                "sqlite3",
                "hashlib",
                "secrets",
            }:
                stdlib.append(imp)
            else:
                third_party.append(imp)
        elif imp.startswith("@") or "/" not in imp:
            third_party.append(imp)
        else:
            local.append(imp)

    result = [f"📦 Imports in {path.name}:", "─" * 50]

    if stdlib:
        result.append("\n🔧 Standard Library:")
        result.extend(f"  - {imp}" for imp in stdlib)

    if third_party:
        result.append("\n📚 Third-Party:")
        result.extend(f"  - {imp}" for imp in third_party)

    if local:
        result.append("\n📁 Local/Relative:")
        result.extend(f"  - {imp}" for imp in local)

    return "\n".join(result)


@tool
def find_entry_points(repo_path: str) -> str:
    """
    Identify main entry points in the codebase.

    Args:
        repo_path: Path to the repository root

    Returns:
        List of likely entry points with their purposes
    """
    repo = Path(repo_path)
    if not repo.exists():
        return f"Error: Path '{repo_path}' does not exist"

    found_entries = []

    # Check for common entry points
    for lang, patterns in ENTRY_POINT_PATTERNS.items():
        for pattern in patterns:
            matches = list(repo.glob(f"**/{pattern}"))
            for match in matches:
                # Skip if in ignored directories
                parts = match.relative_to(repo).parts
                if any(
                    p in {"node_modules", ".git", "__pycache__", "venv", ".venv"}
                    for p in parts
                ):
                    continue
                found_entries.append((str(match.relative_to(repo)), lang, pattern))

    # Check package.json for scripts
    package_json = repo / "package.json"
    if package_json.exists():
        try:
            with open(package_json) as f:
                pkg = json.load(f)
            if "main" in pkg:
                found_entries.append((pkg["main"], "javascript", "package.json main"))
            if "scripts" in pkg:
                scripts = pkg["scripts"]
                if "start" in scripts:
                    found_entries.append(
                        ("npm start", "javascript", f"runs: {scripts['start']}")
                    )
                if "dev" in scripts:
                    found_entries.append(
                        ("npm run dev", "javascript", f"runs: {scripts['dev']}")
                    )
        except Exception:
            pass

    # Check pyproject.toml for entry points
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        try:
            with open(pyproject) as f:
                content = f.read()
            # Simple regex for scripts
            matches = re.findall(
                r"\[project\.scripts\]\s*\n((?:\s*\w+\s*=.*\n?)+)", content
            )
            for match in matches:
                for line in match.strip().split("\n"):
                    if "=" in line:
                        name, target = line.split("=", 1)
                        found_entries.append(
                            (name.strip(), "python", f"CLI: {target.strip()}")
                        )
        except Exception:
            pass

    # Search for CLI framework patterns in source files
    ignored_dirs = {"node_modules", ".git", "__pycache__", "venv", ".venv", "vendor"}

    # Python CLI patterns
    for py_file in repo.glob("**/*.py"):
        parts = py_file.relative_to(repo).parts
        if any(p in ignored_dirs for p in parts):
            continue
        try:
            with open(py_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            for framework, pattern in CLI_FRAMEWORK_PATTERNS["python"].items():
                if re.search(pattern, content):
                    rel_path = str(py_file.relative_to(repo))
                    found_entries.append(
                        (rel_path, "python", f"CLI: {framework} decorator")
                    )
                    break  # Only report first CLI framework match per file
        except Exception:
            pass

    # Rust CLI patterns
    for rs_file in repo.glob("**/*.rs"):
        parts = rs_file.relative_to(repo).parts
        if any(p in ignored_dirs for p in parts):
            continue
        try:
            with open(rs_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            for framework, pattern in CLI_FRAMEWORK_PATTERNS["rust"].items():
                if re.search(pattern, content):
                    rel_path = str(rs_file.relative_to(repo))
                    found_entries.append((rel_path, "rust", f"CLI: {framework} derive"))
                    break
        except Exception:
            pass

    # Go CLI patterns
    for go_file in repo.glob("**/*.go"):
        parts = go_file.relative_to(repo).parts
        if any(p in ignored_dirs for p in parts):
            continue
        try:
            with open(go_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            for framework, pattern in CLI_FRAMEWORK_PATTERNS["go"].items():
                if re.search(pattern, content):
                    rel_path = str(go_file.relative_to(repo))
                    found_entries.append((rel_path, "go", f"CLI: {framework} command"))
                    break
        except Exception:
            pass

    # Check setup.py for console_scripts
    setup_py = repo / "setup.py"
    if setup_py.exists():
        try:
            with open(setup_py, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            console_scripts_match = re.search(
                r"console_scripts.*?=.*?\[(.*?)\]", content, re.DOTALL
            )
            if console_scripts_match:
                scripts_text = console_scripts_match.group(1)
                script_entries = re.findall(
                    r"['\"]([^'\"=]+)=([^'\"]+)['\"]", scripts_text
                )
                for script_name, target in script_entries:
                    found_entries.append(
                        (
                            script_name.strip(),
                            "python",
                            f"console_script: {target.strip()}",
                        )
                    )
        except Exception:
            pass

    # Check __main__.py files that import CLI frameworks
    for main_file in repo.glob("**/__main__.py"):
        parts = main_file.relative_to(repo).parts
        if any(p in ignored_dirs for p in parts):
            continue
        try:
            with open(main_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            cli_imports = []
            if re.search(r"import\s+click|from\s+click", content):
                cli_imports.append("click")
            if re.search(r"import\s+typer|from\s+typer", content):
                cli_imports.append("typer")
            if re.search(r"import\s+fire|from\s+fire", content):
                cli_imports.append("fire")
            if re.search(r"import\s+argparse|from\s+argparse", content):
                cli_imports.append("argparse")
            if cli_imports:
                rel_path = str(main_file.relative_to(repo))
                found_entries.append(
                    (rel_path, "python", f"CLI entry: imports {', '.join(cli_imports)}")
                )
        except Exception:
            pass

    if not found_entries:
        return (
            "No obvious entry points found. Check for main functions or start scripts."
        )

    result = ["🚀 Entry Points Found:", "─" * 50]
    for path, lang, note in found_entries:
        result.append(f"  [{lang}] {path}")
        if note != path:
            result.append(f"         └── {note}")

    return "\n".join(result)


@tool
def analyze_dependencies(repo_path: str) -> str:
    """
    Analyze project dependencies from package files.

    Args:
        repo_path: Path to the repository root

    Returns:
        Summary of dependencies categorized by type
    """
    repo = Path(repo_path)
    if not repo.exists():
        return f"Error: Path '{repo_path}' does not exist"

    results = ["📦 Dependency Analysis:", "─" * 50]

    # Python - requirements.txt
    req_txt = repo / "requirements.txt"
    if req_txt.exists():
        results.append("\n🐍 Python (requirements.txt):")
        try:
            with open(req_txt) as f:
                deps = [
                    line.strip().split("==")[0].split(">=")[0].split("<=")[0]
                    for line in f
                    if line.strip()
                    and not line.startswith("#")
                    and not line.startswith("-")
                ]
            for dep in deps[:20]:
                results.append(f"  - {dep}")
            if len(deps) > 20:
                results.append(f"  ... and {len(deps) - 20} more")
        except Exception as e:
            results.append(f"  Error reading: {e}")

    # Python - pyproject.toml
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        results.append("\n🐍 Python (pyproject.toml):")
        try:
            with open(pyproject) as f:
                content = f.read()
            # Extract dependencies section (simplified)
            if "dependencies" in content:
                match = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
                if match:
                    deps = re.findall(r'"([^"]+)"', match.group(1))
                    for dep in deps[:20]:
                        dep_name = (
                            dep.split(">=")[0].split("==")[0].split("<")[0].strip()
                        )
                        results.append(f"  - {dep_name}")
        except Exception as e:
            results.append(f"  Error reading: {e}")

    # JavaScript - package.json
    package_json = repo / "package.json"
    if package_json.exists():
        try:
            with open(package_json) as f:
                pkg = json.load(f)

            if "dependencies" in pkg:
                results.append("\n📦 Node.js (dependencies):")
                for dep in list(pkg["dependencies"].keys())[:15]:
                    results.append(f"  - {dep}")
                if len(pkg["dependencies"]) > 15:
                    results.append(f"  ... and {len(pkg['dependencies']) - 15} more")

            if "devDependencies" in pkg:
                results.append("\n🔧 Node.js (devDependencies):")
                for dep in list(pkg["devDependencies"].keys())[:10]:
                    results.append(f"  - {dep}")
                if len(pkg["devDependencies"]) > 10:
                    results.append(f"  ... and {len(pkg['devDependencies']) - 10} more")
        except Exception as e:
            results.append(f"  Error reading package.json: {e}")

    # Go - go.mod
    go_mod = repo / "go.mod"
    if go_mod.exists():
        results.append("\n🐹 Go (go.mod):")
        try:
            with open(go_mod) as f:
                for line in f:
                    if line.strip().startswith("require"):
                        continue
                    match = re.match(r"\s+(\S+)\s+v", line)
                    if match:
                        results.append(f"  - {match.group(1)}")
        except Exception as e:
            results.append(f"  Error reading: {e}")

    # Rust - Cargo.toml
    cargo_toml = repo / "Cargo.toml"
    if cargo_toml.exists():
        results.append("\n🦀 Rust (Cargo.toml):")
        try:
            with open(cargo_toml) as f:
                in_deps = False
                for line in f:
                    if "[dependencies]" in line:
                        in_deps = True
                        continue
                    if in_deps:
                        if line.startswith("["):
                            break
                        if "=" in line:
                            dep = line.split("=")[0].strip()
                            if dep:
                                results.append(f"  - {dep}")
        except Exception as e:
            results.append(f"  Error reading: {e}")

    if len(results) == 2:
        results.append(
            "\nNo dependency files found (requirements.txt, package.json, go.mod, Cargo.toml)"
        )

    return "\n".join(results)


@tool
def get_function_signatures(file_path: str) -> str:
    """
    Extract function/method signatures from a source file.

    Args:
        file_path: Path to the source file

    Returns:
        List of function signatures with line numbers
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File '{file_path}' does not exist"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading file: {e}"

    suffix = path.suffix.lower()
    signatures = []

    # Python patterns
    if suffix == ".py":
        class_pattern = re.compile(r"^class\s+(\w+)(?:\(.*?\))?:")
        func_pattern = re.compile(
            r"^(\s*)(?:async\s+)?def\s+(\w+)\s*\((.*?)\)(?:\s*->.*?)?:"
        )

        current_class = None
        for i, line in enumerate(lines, 1):
            class_match = class_pattern.match(line)
            if class_match:
                current_class = class_match.group(1)
                signatures.append((i, f"class {current_class}"))
                continue

            func_match = func_pattern.match(line)
            if func_match:
                indent, name, params = func_match.groups()
                if indent and current_class:
                    signatures.append(
                        (
                            i,
                            f"  {current_class}.{name}({params[:50]}{'...' if len(params) > 50 else ''})",
                        )
                    )
                else:
                    current_class = None
                    signatures.append(
                        (
                            i,
                            f"def {name}({params[:50]}{'...' if len(params) > 50 else ''})",
                        )
                    )

    # TypeScript/JavaScript patterns
    elif suffix in {".ts", ".tsx", ".js", ".jsx"}:
        patterns = [
            re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\((.*?)\)"),
            re.compile(r"^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\("),
            re.compile(r"^(?:export\s+)?class\s+(\w+)"),
            re.compile(r"^\s+(?:async\s+)?(\w+)\s*\(.*?\)\s*(?::\s*\w+)?\s*{"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                match = pattern.match(line)
                if match:
                    signatures.append((i, line.strip()[:80]))
                    break

    # Go patterns
    elif suffix == ".go":
        func_pattern = re.compile(r"^func\s+(?:\(.*?\)\s*)?(\w+)\s*\(")
        type_pattern = re.compile(r"^type\s+(\w+)\s+(?:struct|interface)")

        for i, line in enumerate(lines, 1):
            for pattern in [func_pattern, type_pattern]:
                if pattern.match(line):
                    signatures.append((i, line.strip()[:80]))
                    break

    if not signatures:
        return f"No functions/classes found in {path.name}"

    result = [f"📋 Signatures in {path.name}:", "─" * 50]
    for line_num, sig in signatures:
        result.append(f"  L{line_num:4d}: {sig}")

    return "\n".join(result)
