# Implementation Backlog
# Codebase Onboarding Agent v3.0

**Generated:** 2026-01-29
**Updated:** 2026-01-29
**Total Story Points:** 124
**Estimated Duration:** 6 sprints (6 weeks)

---

## How to Use This Backlog

Each task includes:
1. **Description** - What needs to be done
2. **Acceptance Criteria** - Checkboxes for each requirement
3. **Technical Details** - Code snippets for implementation
4. **VERIFICATION** - Commands to run to confirm task is complete

**IMPORTANT:** Do NOT mark a task complete until ALL verification commands pass.

---

## Backlog Overview

| Epic | Priority | Story Points | Tasks |
|------|----------|--------------|-------|
| Smart File Discovery | P0 | 26 | 6 |
| Intelligent Tool Orchestration | P0 | 24 | 6 |
| Working Memory | P0 | 16 | 4 |
| Self-Correction | P1 | 16 | 4 |
| Citation Verification | P1 | 18 | 4 |
| Security Hardening | P1 | 10 | 3 |
| Eval System | P1 | 14 | 4 |

---

## Sprint 1-2: Smart File Discovery [P0]

### Epic: SMART - Smart File Discovery

---

#### SMART-001: Build Import Graph Analyzer
**Priority:** P0 - Critical
**Story Points:** 5
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Create a module that builds an import graph for the repository, mapping which files import which others. This is the foundation for file importance scoring.

**Acceptance Criteria:**
- [ ] `src/tools/smart_discovery.py` created
- [ ] `build_import_graph()` parses Python imports
- [ ] `build_import_graph()` parses TypeScript/JavaScript imports
- [ ] Graph stored as adjacency list
- [ ] Handles circular imports gracefully

**Technical Details:**
```python
# src/tools/smart_discovery.py

import re
from pathlib import Path
from collections import defaultdict

class ImportGraphBuilder:
    """Build import dependency graph for a repository."""

    PYTHON_IMPORT_PATTERNS = [
        r'^import\s+(\S+)',
        r'^from\s+(\S+)\s+import',
    ]

    JS_IMPORT_PATTERNS = [
        r"^import\s+.*\s+from\s+['\"]([^'\"]+)['\"]",
        r"require\(['\"]([^'\"]+)['\"]\)",
    ]

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.graph: dict[str, set[str]] = defaultdict(set)
        self.reverse_graph: dict[str, set[str]] = defaultdict(set)

    def build(self) -> dict[str, set[str]]:
        """Build the complete import graph."""
        for py_file in self.repo_path.glob("**/*.py"):
            if self._should_skip(py_file):
                continue
            self._parse_python_imports(py_file)

        for js_file in self.repo_path.glob("**/*.{ts,tsx,js,jsx}"):
            if self._should_skip(js_file):
                continue
            self._parse_js_imports(js_file)

        return dict(self.graph)

    def _should_skip(self, path: Path) -> bool:
        """Skip node_modules, venv, etc."""
        skip_dirs = {'node_modules', '.git', '__pycache__', 'venv', '.venv'}
        return any(part in skip_dirs for part in path.parts)

    def _parse_python_imports(self, file_path: Path):
        """Extract imports from Python file."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return

        rel_path = str(file_path.relative_to(self.repo_path))

        for line in content.split('\n'):
            for pattern in self.PYTHON_IMPORT_PATTERNS:
                match = re.match(pattern, line.strip())
                if match:
                    imported = match.group(1).split('.')[0]
                    self.graph[rel_path].add(imported)
                    self.reverse_graph[imported].add(rel_path)

    def get_importers(self, module: str) -> set[str]:
        """Get files that import this module (in-degree)."""
        return self.reverse_graph.get(module, set())
```

**VERIFICATION (must ALL pass):**
```bash
# V1: smart_discovery.py exists
echo -n "V1 - smart_discovery.py exists: "
[ -f "src/tools/smart_discovery.py" ] && echo "PASS" || echo "FAIL"

# V2: ImportGraphBuilder class exists
echo -n "V2 - ImportGraphBuilder class: "
[ $(grep -c "class ImportGraphBuilder" src/tools/smart_discovery.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V3: build_import_graph function
echo -n "V3 - build method exists: "
[ $(grep -c "def build" src/tools/smart_discovery.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V4: Python imports parsed
echo -n "V4 - Python imports parsed: "
[ $(grep -c "PYTHON_IMPORT_PATTERNS\|_parse_python" src/tools/smart_discovery.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V5: Basic functionality test
echo -n "V5 - Import graph builds: "
python -c "
from src.tools.smart_discovery import ImportGraphBuilder
builder = ImportGraphBuilder('.')
graph = builder.build()
assert isinstance(graph, dict), 'Should return dict'
print('PASS')
" 2>/dev/null || echo "FAIL"
```

**Dependencies:** None
**Blocks:** SMART-002, SMART-003

---

#### SMART-002: Calculate File Importance Scores
**Priority:** P0 - Critical
**Story Points:** 5
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Calculate importance scores for files using multiple signals: centrality in import graph, naming conventions, file size, and git activity.

**Acceptance Criteria:**
- [ ] `FileImportanceAnalyzer` class implemented
- [ ] Centrality score from import graph (40% weight)
- [ ] Naming score (main.py > utils.py) (25% weight)
- [ ] Size score (medium files preferred) (20% weight)
- [ ] Git activity score (optional, 15% weight)
- [ ] `get_top_files(n)` returns most important files

**Technical Details:**
```python
# src/tools/smart_discovery.py (continued)

from dataclasses import dataclass
from typing import Optional
import subprocess

@dataclass
class FileScore:
    path: str
    total_score: float
    centrality: float
    naming: float
    size: float
    git_activity: float

class FileImportanceAnalyzer:
    """Score files by structural importance."""

    # Naming patterns with scores (higher = more important)
    NAMING_SCORES = {
        'main': 1.0, 'app': 1.0, 'index': 0.9, 'server': 0.9,
        'cli': 0.8, 'api': 0.8, 'routes': 0.7, 'models': 0.7,
        'config': 0.6, 'settings': 0.6, 'utils': 0.3, 'helpers': 0.3,
        '__init__': 0.1, 'test': 0.2, 'conftest': 0.2,
    }

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.graph_builder = ImportGraphBuilder(repo_path)
        self.import_graph = self.graph_builder.build()
        self.scores: dict[str, FileScore] = {}
        self._calculate_all_scores()

    def _calculate_all_scores(self):
        """Calculate scores for all files."""
        all_files = set(self.import_graph.keys())

        # Add files from reverse graph too
        for importers in self.graph_builder.reverse_graph.values():
            all_files.update(importers)

        for file_path in all_files:
            self.scores[file_path] = FileScore(
                path=file_path,
                total_score=0,
                centrality=self._centrality_score(file_path),
                naming=self._naming_score(file_path),
                size=self._size_score(file_path),
                git_activity=self._git_activity_score(file_path),
            )

            # Weighted total
            self.scores[file_path].total_score = (
                0.40 * self.scores[file_path].centrality +
                0.25 * self.scores[file_path].naming +
                0.20 * self.scores[file_path].size +
                0.15 * self.scores[file_path].git_activity
            )

    def _centrality_score(self, file_path: str) -> float:
        """Score by how many files import this one (in-degree)."""
        module_name = Path(file_path).stem
        importers = len(self.graph_builder.get_importers(module_name))
        # Normalize: 0 importers = 0, 10+ importers = 1.0
        return min(importers / 10, 1.0)

    def _naming_score(self, file_path: str) -> float:
        """Score by filename conventions."""
        stem = Path(file_path).stem.lower()
        for pattern, score in self.NAMING_SCORES.items():
            if pattern in stem:
                return score
        return 0.5  # Default for unknown patterns

    def _size_score(self, file_path: str) -> float:
        """Medium-sized files are often most important."""
        full_path = self.repo_path / file_path
        if not full_path.exists():
            return 0.5

        try:
            lines = len(full_path.read_text().split('\n'))
        except Exception:
            return 0.5

        # Ideal: 100-500 lines. Very small or very large = lower score
        if lines < 10:
            return 0.2  # Likely trivial
        elif lines < 50:
            return 0.5
        elif lines < 500:
            return 1.0  # Sweet spot
        elif lines < 1000:
            return 0.7
        else:
            return 0.4  # Might be too large to be core

    def _git_activity_score(self, file_path: str) -> float:
        """Score by git commit frequency (optional)."""
        try:
            result = subprocess.run(
                ['git', 'log', '--oneline', '--', file_path],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            commits = len(result.stdout.strip().split('\n'))
            return min(commits / 50, 1.0)  # 50+ commits = max score
        except Exception:
            return 0.5  # Default if git not available

    def get_top_files(self, n: int = 20) -> list[FileScore]:
        """Return most important files."""
        sorted_files = sorted(
            self.scores.values(),
            key=lambda x: x.total_score,
            reverse=True
        )
        return sorted_files[:n]

    def should_read_file(self, file_path: str) -> tuple[bool, str]:
        """Recommend whether to read a file."""
        score = self.scores.get(file_path)
        if not score:
            return True, "Unknown file"

        if score.total_score < 0.2:
            return False, f"Low importance ({score.total_score:.2f})"
        return True, f"Importance: {score.total_score:.2f}"
```

**VERIFICATION (must ALL pass):**
```bash
# V1: FileImportanceAnalyzer class
echo -n "V1 - FileImportanceAnalyzer class: "
[ $(grep -c "class FileImportanceAnalyzer" src/tools/smart_discovery.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V2: Centrality calculation
echo -n "V2 - Centrality scoring: "
[ $(grep -c "_centrality_score\|centrality" src/tools/smart_discovery.py 2>/dev/null) -ge 2 ] && echo "PASS" || echo "FAIL"

# V3: Naming conventions
echo -n "V3 - Naming score: "
[ $(grep -c "NAMING_SCORES\|_naming_score" src/tools/smart_discovery.py 2>/dev/null) -ge 2 ] && echo "PASS" || echo "FAIL"

# V4: get_top_files method
echo -n "V4 - get_top_files method: "
[ $(grep -c "def get_top_files" src/tools/smart_discovery.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V5: Analyzer produces scores
echo -n "V5 - Analyzer works: "
python -c "
from src.tools.smart_discovery import FileImportanceAnalyzer
analyzer = FileImportanceAnalyzer('.')
top = analyzer.get_top_files(5)
assert len(top) > 0, 'Should return files'
assert hasattr(top[0], 'total_score'), 'Should have scores'
print('PASS')
" 2>/dev/null || echo "FAIL"
```

**Dependencies:** SMART-001
**Blocks:** SMART-004

---

#### SMART-003: Trivial File Skip List
**Priority:** P0 - Critical
**Story Points:** 3
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Implement logic to detect and skip trivial files that waste context (empty `__init__.py`, re-export `index.ts`, generated files).

**Acceptance Criteria:**
- [ ] `TRIVIAL_FILE_PATTERNS` constant defined
- [ ] `is_trivial_file()` function checks content
- [ ] Empty `__init__.py` detected
- [ ] Re-export only `index.ts` detected
- [ ] Generated file markers detected
- [ ] Integrated into `read_file` tool

**Technical Details:**
```python
# src/tools/file_explorer.py (additions)

import re
from pathlib import Path

TRIVIAL_FILE_PATTERNS = {
    "__init__.py": lambda content: len(content.strip()) == 0 or len(content.strip().split('\n')) < 5,
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
    lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('//')]
    if len(lines) == 0:
        return True

    # All lines are exports
    export_patterns = [
        r'^export\s+',
        r'^export\s*\{',
        r'^export\s*\*',
        r'^module\.exports',
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
    lines = [l for l in content.split('\n') if l.strip()]
    if len(lines) < 3:
        return True, f"Minimal content ({len(lines)} lines)"

    return False, ""

def is_generated_file(content: str) -> bool:
    """Check if file appears to be auto-generated."""
    header = content[:1000]
    return any(marker.lower() in header.lower() for marker in GENERATED_FILE_MARKERS)
```

**VERIFICATION (must ALL pass):**
```bash
# V1: TRIVIAL_FILE_PATTERNS defined
echo -n "V1 - TRIVIAL_FILE_PATTERNS: "
[ $(grep -c "TRIVIAL_FILE_PATTERNS" src/tools/file_explorer.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V2: is_trivial_file function
echo -n "V2 - is_trivial_file function: "
[ $(grep -c "def is_trivial_file" src/tools/file_explorer.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V3: Generated markers defined
echo -n "V3 - GENERATED_FILE_MARKERS: "
[ $(grep -c "GENERATED_FILE_MARKERS" src/tools/file_explorer.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V4: __init__.py detection works
echo -n "V4 - Empty __init__ detected: "
python -c "
from src.tools.file_explorer import is_trivial_file
is_triv, reason = is_trivial_file('__init__.py', '')
assert is_triv == True, 'Empty __init__.py should be trivial'
print('PASS')
" 2>/dev/null || echo "FAIL"

# V5: Generated file detection
echo -n "V5 - Generated file detected: "
python -c "
from src.tools.file_explorer import is_trivial_file
is_triv, reason = is_trivial_file('schema.py', '# AUTO-GENERATED - DO NOT EDIT\nclass Schema: pass')
assert is_triv == True, 'Generated file should be trivial'
print('PASS')
" 2>/dev/null || echo "FAIL"
```

**Dependencies:** None
**Blocks:** SMART-004

---

#### SMART-004: Integrate Smart Discovery into read_file Tool
**Priority:** P0 - Critical
**Story Points:** 3
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Modify the `read_file` tool to check file importance and skip trivial files, with option to force-read if needed.

**Acceptance Criteria:**
- [ ] `read_file` checks `is_trivial_file()`
- [ ] Low-importance files show warning
- [ ] Trivial files return summary instead of full content
- [ ] `force=True` parameter to bypass checks
- [ ] Skipped file decision logged

**Technical Details:**
```python
# src/tools/file_explorer.py - Updated read_file

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
        return f"[BLOCKED] Cannot read '{file_path}' - potential sensitive file"

    if not path.exists():
        return f"Error: File '{file_path}' does not exist"

    if not path.is_file():
        return f"Error: '{file_path}' is not a file"

    # Check file size
    size = path.stat().st_size
    if size > 1_000_000:
        return f"Error: File too large ({size:,} bytes)"

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
    lines = content.split('\n')[:max_lines]
    numbered_lines = [f"{i:4d} | {line}" for i, line in enumerate(lines, 1)]
    content = "\n".join(numbered_lines)

    # SEC-002: Check for prompt injection
    content, was_filtered = sanitize_content(content, file_path)
    if was_filtered:
        return f"[SECURITY] File {path.name} contained potentially unsafe content\n{content}"

    result = f"📄 {path.name} ({len(lines)} lines)\n"
    result += "─" * 50 + "\n"
    result += content

    if len(lines) >= max_lines:
        result += f"\n\n... truncated"

    return result
```

**VERIFICATION (must ALL pass):**
```bash
# V1: read_file has force parameter
echo -n "V1 - force parameter: "
[ $(grep -c "force.*bool\|force=False" src/tools/file_explorer.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V2: Calls is_trivial_file
echo -n "V2 - Calls is_trivial_file: "
[ $(grep -A50 "def read_file" src/tools/file_explorer.py 2>/dev/null | grep -c "is_trivial_file") -ge 1 ] && echo "PASS" || echo "FAIL"

# V3: Returns SKIPPED for trivial
echo -n "V3 - SKIPPED message: "
[ $(grep -c "SKIPPED" src/tools/file_explorer.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V4: Logging for skipped files
echo -n "V4 - Skip logging: "
[ $(grep -c "logging.*skip\|Skip" src/tools/file_explorer.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V5: Tool still works for normal files
echo -n "V5 - Normal file read: "
python -c "
from src.tools.file_explorer import read_file
result = read_file.invoke({'file_path': 'app.py'})
assert 'Error' not in result or 'SKIPPED' in result or '📄' in result
print('PASS')
" 2>/dev/null || echo "FAIL"
```

**Dependencies:** SMART-002, SMART-003
**Blocks:** SMART-005

---

#### SMART-005: Architecture Pattern Detection
**Priority:** P0 - Critical
**Story Points:** 5
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Detect common architecture patterns (MVC, monorepo, Clean Architecture, frontend SPA, serverless) and report in overview.

**Acceptance Criteria:**
- [ ] `detect_architecture()` function implemented
- [ ] MVC pattern detected (models/, views/, controllers/)
- [ ] Monorepo detected (multiple package.json, lerna.json, nx.json)
- [ ] Frontend SPA detected (src/components/, pages/, router)
- [ ] Serverless detected (serverless.yml, functions/)
- [ ] Architecture added to overview output

**Technical Details:**
```python
# src/tools/smart_discovery.py (continued)

from dataclasses import dataclass
from typing import Optional

@dataclass
class ArchitecturePattern:
    name: str
    confidence: float  # 0-1
    evidence: list[str]
    suggested_entry_points: list[str]

class ArchitectureDetector:
    """Detect common architecture patterns in codebases."""

    PATTERNS = {
        "mvc": {
            "indicators": ["models", "views", "controllers"],
            "optional": ["templates", "static"],
            "entry_points": ["app.py", "manage.py", "server.py"],
        },
        "clean_architecture": {
            "indicators": ["domain", "infrastructure", "application"],
            "optional": ["interfaces", "use_cases", "entities"],
            "entry_points": ["main.py", "app.py"],
        },
        "frontend_spa": {
            "indicators": ["src/components", "pages", "src/pages"],
            "optional": ["hooks", "store", "redux", "context"],
            "entry_points": ["src/App.tsx", "src/main.tsx", "src/index.tsx"],
        },
        "monorepo": {
            "indicators": ["packages/", "apps/"],
            "config_files": ["lerna.json", "nx.json", "pnpm-workspace.yaml", "turbo.json"],
            "entry_points": [],  # Varies per package
        },
        "serverless": {
            "indicators": ["functions", "lambdas"],
            "config_files": ["serverless.yml", "serverless.yaml", "sam.yaml"],
            "entry_points": ["handler.py", "handler.js", "index.js"],
        },
        "django": {
            "indicators": ["manage.py"],
            "optional": ["settings.py", "urls.py", "wsgi.py"],
            "entry_points": ["manage.py"],
        },
        "fastapi": {
            "indicators": ["main.py"],
            "code_patterns": ["FastAPI()", "from fastapi"],
            "entry_points": ["main.py", "app.py"],
        },
    }

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def detect(self) -> list[ArchitecturePattern]:
        """Detect all matching architecture patterns."""
        detected = []

        dirs = {d.name.lower() for d in self.repo_path.iterdir() if d.is_dir()}
        files = {f.name for f in self.repo_path.glob("*") if f.is_file()}
        all_files = {str(f.relative_to(self.repo_path)) for f in self.repo_path.glob("**/*") if f.is_file()}

        for pattern_name, config in self.PATTERNS.items():
            evidence = []

            # Check directory indicators
            indicators = config.get("indicators", [])
            for ind in indicators:
                if ind in dirs or any(ind in str(f) for f in all_files):
                    evidence.append(f"Found: {ind}/")

            # Check config files
            config_files = config.get("config_files", [])
            for cf in config_files:
                if cf in files:
                    evidence.append(f"Config: {cf}")

            # Check code patterns (expensive, do last)
            code_patterns = config.get("code_patterns", [])
            for cp in code_patterns:
                if self._search_code_pattern(cp):
                    evidence.append(f"Code: {cp}")

            # Calculate confidence
            total_signals = len(indicators) + len(config_files) + len(code_patterns)
            if total_signals > 0 and len(evidence) > 0:
                confidence = len(evidence) / total_signals
                if confidence >= 0.3:  # At least 30% match
                    detected.append(ArchitecturePattern(
                        name=pattern_name,
                        confidence=confidence,
                        evidence=evidence,
                        suggested_entry_points=config.get("entry_points", []),
                    ))

        return sorted(detected, key=lambda x: x.confidence, reverse=True)

    def _search_code_pattern(self, pattern: str) -> bool:
        """Quick search for code pattern in key files."""
        for ext in ["*.py", "*.ts", "*.js"]:
            for f in list(self.repo_path.glob(ext))[:10]:  # Check first 10 files
                try:
                    if pattern in f.read_text():
                        return True
                except Exception:
                    pass
        return False

    def get_summary(self) -> str:
        """Get human-readable architecture summary."""
        patterns = self.detect()
        if not patterns:
            return "Architecture: Unknown/Custom"

        primary = patterns[0]
        summary = f"Architecture: {primary.name.upper()} ({primary.confidence:.0%} confidence)\n"
        summary += f"Evidence: {', '.join(primary.evidence)}\n"
        if primary.suggested_entry_points:
            summary += f"Entry points: {', '.join(primary.suggested_entry_points)}"

        return summary
```

**VERIFICATION (must ALL pass):**
```bash
# V1: ArchitectureDetector class
echo -n "V1 - ArchitectureDetector class: "
[ $(grep -c "class ArchitectureDetector" src/tools/smart_discovery.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V2: detect method
echo -n "V2 - detect method: "
[ $(grep -c "def detect" src/tools/smart_discovery.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V3: Multiple patterns defined
echo -n "V3 - Multiple patterns: "
[ $(grep -c '"mvc"\|"monorepo"\|"serverless"' src/tools/smart_discovery.py 2>/dev/null) -ge 3 ] && echo "PASS" || echo "FAIL"

# V4: Returns ArchitecturePattern
echo -n "V4 - ArchitecturePattern dataclass: "
[ $(grep -c "class ArchitecturePattern\|@dataclass" src/tools/smart_discovery.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V5: Detector runs
echo -n "V5 - Detector works: "
python -c "
from src.tools.smart_discovery import ArchitectureDetector
detector = ArchitectureDetector('.')
patterns = detector.detect()
assert isinstance(patterns, list)
print('PASS')
" 2>/dev/null || echo "FAIL"
```

**Dependencies:** SMART-001
**Blocks:** SMART-006

---

#### SMART-006: Add Smart Discovery Tool
**Priority:** P0 - Critical
**Story Points:** 5
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Create a new LangChain tool that provides smart file discovery recommendations to the agent.

**Acceptance Criteria:**
- [ ] `get_important_files` tool created
- [ ] Returns top-N files with importance scores
- [ ] Includes architecture detection summary
- [ ] Integrated into agent's toolset
- [ ] Tool used in overview generation

**Technical Details:**
```python
# src/tools/smart_discovery.py (continued)

from langchain_core.tools import tool

@tool
def get_important_files(repo_path: str, top_n: int = 15) -> str:
    """
    Analyze repository and return the most important files to read first.

    Use this tool BEFORE reading files to prioritize exploration.
    High-importance files are architectural cores, entry points, and config.
    Low-importance files are trivial (__init__.py), generated, or boilerplate.

    Args:
        repo_path: Path to repository root
        top_n: Number of files to return (default: 15)

    Returns:
        Ranked list of important files with scores and architecture summary
    """
    try:
        # Architecture detection
        arch_detector = ArchitectureDetector(repo_path)
        arch_summary = arch_detector.get_summary()

        # File importance analysis
        analyzer = FileImportanceAnalyzer(repo_path)
        top_files = analyzer.get_top_files(top_n)

        # Format output
        result = ["🎯 SMART FILE DISCOVERY", "=" * 50, ""]
        result.append(arch_summary)
        result.append("")
        result.append("📊 TOP FILES TO READ (by importance):")
        result.append("-" * 40)

        for i, score in enumerate(top_files, 1):
            importance = "🔴" if score.total_score > 0.7 else "🟡" if score.total_score > 0.4 else "⚪"
            result.append(f"{i:2d}. {importance} {score.path}")
            result.append(f"     Score: {score.total_score:.2f} (centrality: {score.centrality:.2f}, naming: {score.naming:.2f})")

        result.append("")
        result.append("💡 TIP: Start with 🔴 high-importance files for architecture understanding.")
        result.append("💡 SKIP: Files like __init__.py, index.ts (re-exports only) are usually trivial.")

        return "\n".join(result)

    except Exception as e:
        return f"Error analyzing repository: {e}"

# Export tools
def get_smart_discovery_tools():
    """Get smart discovery tools for agent."""
    return [get_important_files]
```

**VERIFICATION (must ALL pass):**
```bash
# V1: get_important_files tool exists
echo -n "V1 - get_important_files tool: "
[ $(grep -c "@tool.*\ndef get_important_files\|def get_important_files" src/tools/smart_discovery.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V2: Returns ranked files
echo -n "V2 - Returns ranked files: "
python -c "
from src.tools.smart_discovery import get_important_files
result = get_important_files.invoke({'repo_path': '.', 'top_n': 5})
assert 'TOP FILES' in result or 'Score' in result
print('PASS')
" 2>/dev/null || echo "FAIL"

# V3: Includes architecture summary
echo -n "V3 - Architecture included: "
python -c "
from src.tools.smart_discovery import get_important_files
result = get_important_files.invoke({'repo_path': '.', 'top_n': 5})
assert 'Architecture' in result or 'DISCOVERY' in result
print('PASS')
" 2>/dev/null || echo "FAIL"

# V4: get_smart_discovery_tools function
echo -n "V4 - Export function: "
[ $(grep -c "def get_smart_discovery_tools" src/tools/smart_discovery.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V5: Tool integrated in agent
echo -n "V5 - Integrated in agent: "
[ $(grep -c "smart_discovery\|get_important_files" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL - Not yet integrated"
```

**Dependencies:** SMART-002, SMART-005
**Blocks:** None

---

## Sprint 3-4: Intelligent Tool Orchestration [P0]

### Epic: ORCH - Intelligent Tool Orchestration

---

#### ORCH-001: Working Memory Data Structure
**Priority:** P0 - Critical
**Story Points:** 4
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Implement a structured working memory that persists across tool calls, tracking what has been explored, key findings, and confirmed facts.

**Acceptance Criteria:**
- [ ] `WorkingMemory` dataclass defined
- [ ] Tracks files read (avoid re-reading)
- [ ] Stores confirmed facts with citations
- [ ] Tracks searches performed
- [ ] Provides `to_context_string()` for LLM

**Technical Details:**
```python
# src/memory.py (new file)

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

@dataclass
class ConfirmedFact:
    """A fact discovered with supporting citation."""
    fact: str
    citation: str  # file:line format
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class FileRead:
    """Record of a file that was read."""
    path: str
    lines_read: int
    summary: str  # Brief summary of content
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class SearchPerformed:
    """Record of a search that was performed."""
    pattern: str
    results_count: int
    key_files: list[str]
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class WorkingMemory:
    """Structured working memory for exploration session."""

    # Project understanding (discovered during exploration)
    project_type: Optional[str] = None
    primary_language: Optional[str] = None
    architecture_pattern: Optional[str] = None

    # What we've discovered
    key_files: list[FileRead] = field(default_factory=list)
    confirmed_facts: list[ConfirmedFact] = field(default_factory=list)

    # What we've explored (avoid re-doing)
    files_read: set[str] = field(default_factory=set)
    searches_performed: list[SearchPerformed] = field(default_factory=list)

    # Current exploration state
    current_question: Optional[str] = None
    exploration_plan: list[str] = field(default_factory=list)

    def add_file_read(self, path: str, lines: int, summary: str):
        """Record that a file was read."""
        self.files_read.add(path)
        self.key_files.append(FileRead(path=path, lines_read=lines, summary=summary))

    def add_fact(self, fact: str, citation: str):
        """Add a confirmed fact with its citation."""
        self.confirmed_facts.append(ConfirmedFact(fact=fact, citation=citation))

    def add_search(self, pattern: str, results: int, key_files: list[str]):
        """Record a search that was performed."""
        self.searches_performed.append(SearchPerformed(
            pattern=pattern,
            results_count=results,
            key_files=key_files
        ))

    def was_file_read(self, path: str) -> bool:
        """Check if file was already read."""
        return path in self.files_read

    def to_context_string(self, max_facts: int = 10) -> str:
        """Convert to string for LLM context injection."""
        lines = ["## WORKING MEMORY", ""]

        if self.architecture_pattern:
            lines.append(f"Architecture: {self.architecture_pattern}")
        if self.primary_language:
            lines.append(f"Language: {self.primary_language}")

        if self.confirmed_facts:
            lines.append("\n### Confirmed Facts:")
            for fact in self.confirmed_facts[-max_facts:]:
                lines.append(f"- {fact.fact} [{fact.citation}]")

        if self.files_read:
            lines.append(f"\n### Files Read ({len(self.files_read)}):")
            lines.append(", ".join(sorted(self.files_read)[:20]))

        if self.exploration_plan:
            lines.append("\n### Exploration Plan:")
            for i, step in enumerate(self.exploration_plan, 1):
                lines.append(f"{i}. {step}")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        """Get memory statistics."""
        return {
            "files_read": len(self.files_read),
            "facts_confirmed": len(self.confirmed_facts),
            "searches_done": len(self.searches_performed),
        }
```

**VERIFICATION (must ALL pass):**
```bash
# V1: memory.py exists
echo -n "V1 - memory.py exists: "
[ -f "src/memory.py" ] && echo "PASS" || echo "FAIL"

# V2: WorkingMemory class
echo -n "V2 - WorkingMemory class: "
[ $(grep -c "class WorkingMemory" src/memory.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V3: files_read tracking
echo -n "V3 - files_read tracking: "
[ $(grep -c "files_read" src/memory.py 2>/dev/null) -ge 2 ] && echo "PASS" || echo "FAIL"

# V4: confirmed_facts tracking
echo -n "V4 - confirmed_facts: "
[ $(grep -c "confirmed_facts" src/memory.py 2>/dev/null) -ge 2 ] && echo "PASS" || echo "FAIL"

# V5: to_context_string method
echo -n "V5 - to_context_string: "
[ $(grep -c "def to_context_string" src/memory.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"
```

**Dependencies:** None
**Blocks:** ORCH-002

---

#### ORCH-002: Integrate Working Memory into Agent
**Priority:** P0 - Critical
**Story Points:** 4
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Integrate the WorkingMemory into the agent so it persists across tool calls and provides context.

**Acceptance Criteria:**
- [ ] Agent has `working_memory` attribute
- [ ] Memory updated after each tool call
- [ ] Memory context injected into prompts
- [ ] Files not re-read if already in memory
- [ ] Memory accessible via `get_memory_stats()`

**Technical Details:**
```python
# src/agent.py (modifications)

from src.memory import WorkingMemory

class CodebaseOnboardingAgent:
    def __init__(self, repo_path: str, ...):
        # ... existing code ...
        self.working_memory = WorkingMemory()

    def _update_memory_from_tool_call(self, tool_name: str, tool_input: dict, tool_output: str):
        """Update working memory based on tool results."""
        if tool_name == "read_file":
            file_path = tool_input.get("file_path", "")
            lines = tool_output.count('\n')
            # Extract brief summary (first non-empty line of content)
            summary = tool_output.split('\n')[2] if len(tool_output.split('\n')) > 2 else ""
            self.working_memory.add_file_read(file_path, lines, summary[:100])

        elif tool_name == "search_code":
            pattern = tool_input.get("pattern", "")
            # Count results
            results = tool_output.count('\n') - 2  # Minus header lines
            # Extract file paths from results
            import re
            files = re.findall(r'^([^:]+):', tool_output, re.MULTILINE)
            self.working_memory.add_search(pattern, results, list(set(files))[:5])

        elif tool_name == "get_important_files":
            # Extract architecture if present
            if "Architecture:" in tool_output:
                arch_line = [l for l in tool_output.split('\n') if 'Architecture:' in l]
                if arch_line:
                    self.working_memory.architecture_pattern = arch_line[0]

    def _should_skip_file_read(self, file_path: str) -> bool:
        """Check if file was already read."""
        if self.working_memory.was_file_read(file_path):
            return True
        return False

    def _inject_memory_context(self, messages: list) -> list:
        """Inject working memory into message context."""
        memory_context = self.working_memory.to_context_string()
        if memory_context and len(self.working_memory.files_read) > 0:
            # Add as system message or append to last user message
            memory_msg = SystemMessage(content=memory_context)
            return [messages[0], memory_msg] + messages[1:]
        return messages

    def get_memory_stats(self) -> dict:
        """Get current memory statistics."""
        return self.working_memory.get_stats()

    def reset_conversation(self):
        """Reset conversation and memory."""
        self.conversation_history = []
        self.last_tool_calls = []
        self.working_memory = WorkingMemory()  # Reset memory too
```

**VERIFICATION (must ALL pass):**
```bash
# V1: working_memory attribute
echo -n "V1 - working_memory attribute: "
[ $(grep -c "self.working_memory" src/agent.py 2>/dev/null) -ge 2 ] && echo "PASS" || echo "FAIL"

# V2: Memory import
echo -n "V2 - WorkingMemory imported: "
[ $(grep -c "from src.memory import\|import.*WorkingMemory" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V3: _update_memory method
echo -n "V3 - Memory update method: "
[ $(grep -c "_update_memory\|update_memory" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V4: get_memory_stats method
echo -n "V4 - get_memory_stats: "
[ $(grep -c "def get_memory_stats" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V5: Memory resets with conversation
echo -n "V5 - Memory resets: "
[ $(grep -A5 "def reset_conversation" src/agent.py 2>/dev/null | grep -c "working_memory") -ge 1 ] && echo "PASS" || echo "FAIL"
```

**Dependencies:** ORCH-001
**Blocks:** ORCH-003

---

#### ORCH-003: Tool Routing Rules
**Priority:** P0 - Critical
**Story Points:** 4
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Implement tool routing rules that guide efficient tool usage (e.g., search before read, directory listing first).

**Acceptance Criteria:**
- [ ] `TOOL_ROUTING_RULES` constant defined
- [ ] Rules checked before tool execution
- [ ] Warning issued for inefficient patterns
- [ ] "Search before read" enforced
- [ ] Rule violations logged

**Technical Details:**
```python
# src/tool_router.py (new file)

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class RoutingRule:
    """A rule for efficient tool usage."""
    tool_name: str
    prerequisites: list[str]  # Tools that should be called first
    min_prerequisite_count: int
    warning_message: str

TOOL_ROUTING_RULES = {
    "read_file": RoutingRule(
        tool_name="read_file",
        prerequisites=["search_code", "find_files_by_pattern", "list_directory_structure", "get_important_files"],
        min_prerequisite_count=1,
        warning_message="Consider searching for relevant files before reading directly."
    ),
    "get_function_signatures": RoutingRule(
        tool_name="get_function_signatures",
        prerequisites=["list_directory_structure", "read_file"],
        min_prerequisite_count=1,
        warning_message="Understand file content before extracting signatures."
    ),
}

class ToolRouter:
    """Routes and validates tool usage patterns."""

    def __init__(self):
        self.tool_history: list[str] = []
        self.warnings_issued: set[str] = set()

    def record_tool_call(self, tool_name: str):
        """Record a tool call in history."""
        self.tool_history.append(tool_name)

    def check_routing(self, tool_name: str) -> tuple[bool, Optional[str]]:
        """
        Check if tool call follows routing rules.

        Returns:
            (is_ok, warning_message) - warning_message is None if OK
        """
        rule = TOOL_ROUTING_RULES.get(tool_name)
        if not rule:
            return True, None

        # Count how many prerequisites have been called
        prereq_count = sum(1 for t in self.tool_history if t in rule.prerequisites)

        if prereq_count < rule.min_prerequisite_count:
            # Only warn once per rule per session
            warning_key = f"{tool_name}_routing"
            if warning_key not in self.warnings_issued:
                self.warnings_issued.add(warning_key)
                logger.warning(f"Tool routing: {rule.warning_message}")
                return False, rule.warning_message

        return True, None

    def get_recommended_next_tool(self, current_context: str) -> Optional[str]:
        """Suggest next tool based on current state."""
        # If no tools called yet, start with smart discovery or directory listing
        if len(self.tool_history) == 0:
            return "get_important_files"

        # If only directory listed, suggest search
        if self.tool_history[-1] == "list_directory_structure":
            return "search_code"

        # If searched, suggest reading found files
        if self.tool_history[-1] == "search_code":
            return "read_file"

        return None

    def reset(self):
        """Reset router state."""
        self.tool_history = []
        self.warnings_issued = set()
```

**VERIFICATION (must ALL pass):**
```bash
# V1: tool_router.py exists
echo -n "V1 - tool_router.py exists: "
[ -f "src/tool_router.py" ] && echo "PASS" || echo "FAIL"

# V2: TOOL_ROUTING_RULES defined
echo -n "V2 - TOOL_ROUTING_RULES: "
[ $(grep -c "TOOL_ROUTING_RULES" src/tool_router.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V3: ToolRouter class
echo -n "V3 - ToolRouter class: "
[ $(grep -c "class ToolRouter" src/tool_router.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V4: check_routing method
echo -n "V4 - check_routing method: "
[ $(grep -c "def check_routing" src/tool_router.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V5: Search before read rule
echo -n "V5 - Search before read: "
[ $(grep -c "search_code.*read_file\|read_file.*search" src/tool_router.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"
```

**Dependencies:** None
**Blocks:** ORCH-004

---

#### ORCH-004: Tool Thrashing Circuit Breaker
**Priority:** P0 - Critical
**Story Points:** 4
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Detect when the agent is stuck in a loop (tool thrashing) and gracefully exit with helpful message.

**Acceptance Criteria:**
- [ ] `MAX_TOOL_CALLS` constant (default: 25)
- [ ] Repetitive pattern detection (same tool 3+ times in 5 calls)
- [ ] "No new information" detection
- [ ] Graceful exit with "I couldn't find X"
- [ ] Circuit breaker stats tracked

**Technical Details:**
```python
# src/tool_router.py (continued)

@dataclass
class CircuitBreakerState:
    """Track circuit breaker state."""
    total_calls: int = 0
    calls_without_new_info: int = 0
    is_tripped: bool = False
    trip_reason: str = ""

class ToolUsageTracker:
    """Track tool usage and detect thrashing patterns."""

    MAX_TOTAL_CALLS = 25
    MAX_CALLS_PER_TOOL = 10
    THRASHING_WINDOW = 5
    THRASHING_THRESHOLD = 3

    def __init__(self):
        self.call_history: list[dict] = []  # {name, input_hash, output_hash}
        self.output_hashes: set[str] = set()
        self.circuit_breaker = CircuitBreakerState()

    def record_call(self, tool_name: str, tool_input: str, tool_output: str):
        """Record a tool call and check for issues."""
        # Hash outputs to detect repeats
        output_hash = hash(tool_output[:500])
        is_new_info = output_hash not in self.output_hashes

        self.call_history.append({
            "name": tool_name,
            "input": tool_input[:100],
            "is_new": is_new_info,
        })

        if is_new_info:
            self.output_hashes.add(output_hash)
            self.circuit_breaker.calls_without_new_info = 0
        else:
            self.circuit_breaker.calls_without_new_info += 1

        self.circuit_breaker.total_calls += 1

    def check_thrashing(self) -> tuple[bool, str]:
        """
        Detect if we're stuck in a thrashing loop.

        Returns:
            (is_thrashing, reason)
        """
        # Check total calls limit
        if self.circuit_breaker.total_calls >= self.MAX_TOTAL_CALLS:
            return True, f"Tool call budget exhausted ({self.MAX_TOTAL_CALLS} calls)"

        # Check for repetitive patterns in recent calls
        if len(self.call_history) >= self.THRASHING_WINDOW:
            recent = self.call_history[-self.THRASHING_WINDOW:]
            tool_names = [c["name"] for c in recent]

            for tool in set(tool_names):
                if tool_names.count(tool) >= self.THRASHING_THRESHOLD:
                    return True, f"Repetitive use of {tool} ({tool_names.count(tool)} times in last {self.THRASHING_WINDOW} calls)"

        # Check for no new information
        if self.circuit_breaker.calls_without_new_info >= 5:
            return True, "No new information in last 5 tool calls"

        # Check per-tool limits
        tool_counts = {}
        for call in self.call_history:
            tool_counts[call["name"]] = tool_counts.get(call["name"], 0) + 1

        for tool, count in tool_counts.items():
            if count >= self.MAX_CALLS_PER_TOOL:
                return True, f"{tool} called {count} times (limit: {self.MAX_CALLS_PER_TOOL})"

        return False, ""

    def get_graceful_exit_message(self, question: str) -> str:
        """Generate helpful message when circuit breaker trips."""
        stats = self.get_stats()

        message = f"""I've explored extensively but couldn't find a complete answer to your question.

**What I searched:**
- Made {stats['total_calls']} tool calls
- Read {stats['unique_files']} files
- Found {stats['new_info_calls']} pieces of new information

**Suggestion:** Try asking a more specific question, or point me to a particular file or component."""

        return message

    def get_stats(self) -> dict:
        """Get usage statistics."""
        unique_files = len([c for c in self.call_history if c["name"] == "read_file"])
        new_info_calls = sum(1 for c in self.call_history if c.get("is_new", False))

        return {
            "total_calls": self.circuit_breaker.total_calls,
            "unique_files": unique_files,
            "new_info_calls": new_info_calls,
            "is_tripped": self.circuit_breaker.is_tripped,
        }

    def reset(self):
        """Reset tracker."""
        self.call_history = []
        self.output_hashes = set()
        self.circuit_breaker = CircuitBreakerState()
```

**VERIFICATION (must ALL pass):**
```bash
# V1: ToolUsageTracker class
echo -n "V1 - ToolUsageTracker class: "
[ $(grep -c "class ToolUsageTracker" src/tool_router.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V2: MAX_TOOL_CALLS defined
echo -n "V2 - MAX_TOTAL_CALLS: "
[ $(grep -c "MAX_TOTAL_CALLS\|MAX_TOOL_CALLS" src/tool_router.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V3: check_thrashing method
echo -n "V3 - check_thrashing: "
[ $(grep -c "def check_thrashing" src/tool_router.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V4: Graceful exit message
echo -n "V4 - Graceful exit: "
[ $(grep -c "graceful_exit\|exit_message" src/tool_router.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V5: Thrashing detection works
echo -n "V5 - Thrashing detection: "
python -c "
from src.tool_router import ToolUsageTracker
tracker = ToolUsageTracker()
for i in range(6):
    tracker.record_call('read_file', f'file{i}', 'same output')
is_thrash, reason = tracker.check_thrashing()
assert is_thrash == True, 'Should detect thrashing'
print('PASS')
" 2>/dev/null || echo "FAIL"
```

**Dependencies:** ORCH-003
**Blocks:** ORCH-005

---

#### ORCH-005: Plan-Then-Execute Pattern
**Priority:** P0 - Critical
**Story Points:** 5
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Implement a planning phase that creates an exploration plan before diving into tool calls.

**Acceptance Criteria:**
- [ ] `create_exploration_plan()` method
- [ ] Plan visible in working memory
- [ ] Plan adapts based on findings
- [ ] Deep-dive questions use planning
- [ ] Plan checkpoints every 5 tool calls

**Technical Details:**
```python
# src/agent.py (additions)

PLANNING_PROMPT = """You are planning how to explore a codebase to answer a question.

QUESTION: {question}

CURRENT KNOWLEDGE:
{memory_context}

Create a brief exploration plan (3-5 steps) to answer this question.
Each step should be a specific action like:
- "Search for authentication-related files"
- "Read the main entry point"
- "Check the database models"

Return ONLY the numbered plan, nothing else.
"""

class CodebaseOnboardingAgent:
    # ... existing code ...

    async def create_exploration_plan(self, question: str) -> list[str]:
        """Create a plan for exploring the codebase."""
        memory_context = self.working_memory.to_context_string()

        prompt = PLANNING_PROMPT.format(
            question=question,
            memory_context=memory_context
        )

        # Use LLM to create plan
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])

        # Parse numbered list
        lines = response.content.strip().split('\n')
        plan = []
        for line in lines:
            # Remove numbering
            cleaned = line.strip().lstrip('0123456789.-) ')
            if cleaned:
                plan.append(cleaned)

        self.working_memory.exploration_plan = plan
        return plan

    async def explore_with_plan(self, question: str) -> str:
        """Explore codebase using plan-then-execute pattern."""
        # Phase 1: Create plan
        plan = await self.create_exploration_plan(question)

        # Phase 2: Execute with checkpoints
        findings = []
        tool_calls_since_checkpoint = 0

        for step in plan:
            # Execute step (let agent decide which tools)
            step_result = await self._execute_plan_step(step)
            findings.append(step_result)
            tool_calls_since_checkpoint += 1

            # Checkpoint every 5 tool calls
            if tool_calls_since_checkpoint >= 5:
                should_continue = await self._reflection_checkpoint(question, findings)
                if not should_continue:
                    break
                tool_calls_since_checkpoint = 0

        # Phase 3: Synthesize answer
        return await self._synthesize_answer(question, findings)

    async def _execute_plan_step(self, step: str) -> str:
        """Execute a single plan step."""
        # This invokes the agent to execute the step
        result = await self._run(f"Execute this exploration step: {step}")
        return result

    async def _reflection_checkpoint(self, question: str, findings: list) -> bool:
        """Check if we should continue exploring."""
        # Check circuit breaker
        is_thrashing, reason = self.tool_tracker.check_thrashing()
        if is_thrashing:
            return False

        # Ask LLM if we have enough to answer
        checkpoint_prompt = f"""Based on these findings, can we answer the question?

QUESTION: {question}

FINDINGS:
{chr(10).join(findings[-3:])}  # Last 3 findings

Reply with CONTINUE, PIVOT, or SYNTHESIZE."""

        response = await self.llm.ainvoke([HumanMessage(content=checkpoint_prompt)])

        return "CONTINUE" in response.content.upper()
```

**VERIFICATION (must ALL pass):**
```bash
# V1: create_exploration_plan method
echo -n "V1 - create_exploration_plan: "
[ $(grep -c "def create_exploration_plan\|async def create_exploration_plan" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V2: PLANNING_PROMPT defined
echo -n "V2 - PLANNING_PROMPT: "
[ $(grep -c "PLANNING_PROMPT" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V3: explore_with_plan method
echo -n "V3 - explore_with_plan: "
[ $(grep -c "explore_with_plan" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V4: Reflection checkpoint
echo -n "V4 - Reflection checkpoint: "
[ $(grep -c "reflection_checkpoint\|checkpoint" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V5: Plan stored in memory
echo -n "V5 - Plan in memory: "
[ $(grep -c "exploration_plan" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"
```

**Dependencies:** ORCH-001, ORCH-004
**Blocks:** ORCH-006

---

#### ORCH-006: Integrate Orchestration into Agent
**Priority:** P0 - Critical
**Story Points:** 3
**Assignee:** TBD
**Status:** [ ] Not Started  [ ] In Progress  [ ] Complete

**Description:**
Integrate all orchestration components (memory, router, tracker, planning) into the main agent flow.

**Acceptance Criteria:**
- [ ] Agent uses ToolRouter for routing
- [ ] Agent uses ToolUsageTracker for circuit breaking
- [ ] Deep-dive uses plan-then-execute
- [ ] All components reset on conversation reset
- [ ] Stats available via API

**VERIFICATION (must ALL pass):**
```bash
# V1: ToolRouter in agent
echo -n "V1 - ToolRouter integrated: "
[ $(grep -c "ToolRouter\|tool_router" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V2: ToolUsageTracker in agent
echo -n "V2 - ToolUsageTracker integrated: "
[ $(grep -c "ToolUsageTracker\|tool_tracker" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V3: Components reset together
echo -n "V3 - Components reset: "
[ $(grep -A10 "def reset_conversation" src/agent.py 2>/dev/null | grep -c "reset\|Router\|Tracker\|memory") -ge 2 ] && echo "PASS" || echo "FAIL"

# V4: Stats method
echo -n "V4 - Get stats method: "
[ $(grep -c "def get_stats\|def get_tool_stats" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"

# V5: Deep-dive uses planning
echo -n "V5 - Deep-dive planning: "
[ $(grep -c "plan.*deep\|deep.*plan\|explore_with_plan" src/agent.py 2>/dev/null) -ge 1 ] && echo "PASS" || echo "FAIL"
```

**Dependencies:** ORCH-002, ORCH-003, ORCH-004, ORCH-005
**Blocks:** None

---

## Sprint 5-6: Self-Correction & Citation Verification [P1]

*Additional tasks for Self-Correction (SELF-001 through SELF-004), Citation Verification (CITE-001 through CITE-004), Security Hardening (SEC-001 through SEC-003), and Eval System (EVAL-001 through EVAL-004) follow the same format as above.*

*Due to length constraints, these are summarized below. Full details available in expanded backlog.*

---

## Remaining Epics Summary

### Epic: SELF - Self-Correction [P1] - 16 points

| Task | Description | Points |
|------|-------------|--------|
| SELF-001 | Reflection Checkpoints | 4 |
| SELF-002 | Off-Track Detection | 4 |
| SELF-003 | Strategy Pivot Logic | 4 |
| SELF-004 | Integrate Self-Correction | 4 |

### Epic: CITE - Citation Verification [P1] - 18 points

| Task | Description | Points |
|------|-------------|--------|
| CITE-001 | Semantic Citation Verification | 5 |
| CITE-002 | Claim Extraction | 4 |
| CITE-003 | Claim-Citation Grounding | 5 |
| CITE-004 | Integrate into Eval Pipeline | 4 |

### Epic: SEC - Security Hardening [P1] - 10 points

| Task | Description | Points |
|------|-------------|--------|
| SEC-001 | Symlink Escape Prevention | 3 |
| SEC-002 | Improved Injection Filter | 4 |
| SEC-003 | Security Test Suite | 3 |

### Epic: EVAL - Eval System [P1] - 14 points

| Task | Description | Points |
|------|-------------|--------|
| EVAL-001 | Meaningful Metrics (P/R/F1) | 4 |
| EVAL-002 | Adversarial Test Suite | 4 |
| EVAL-003 | Historical Comparison | 3 |
| EVAL-004 | Eval Report Overhaul | 3 |

---

## Task Dependencies Graph

```
SMART-001 (Import Graph) ─────┬──→ SMART-002 (Importance Scores)
                              │
                              └──→ SMART-005 (Architecture Detection)

SMART-002 + SMART-003 ────────→ SMART-004 (Integrate into read_file)

SMART-002 + SMART-005 ────────→ SMART-006 (Smart Discovery Tool)

ORCH-001 (Working Memory) ────→ ORCH-002 (Integrate Memory)
                                        │
                                        └──→ ORCH-005 (Plan-Then-Execute)

ORCH-003 (Routing Rules) ─────→ ORCH-004 (Circuit Breaker)
                                        │
                                        └──→ ORCH-006 (Integrate Orchestration)

CITE-001 (Semantic Verify) ───→ CITE-003 (Grounding)
                                        │
CITE-002 (Claim Extract) ─────────────→ CITE-004 (Eval Integration)
```

---

## Success Criteria (V3 Definition of Done)

| Criteria | Measurement | Target |
|----------|-------------|--------|
| Agent reads important files first | % of reads in top-20 by centrality | >70% |
| No trivial file reads | `__init__.py` reads per session | <1 |
| No tool thrashing | Incidents with >20 calls, 0 citations | <1/10 repos |
| Working memory persists | Files not re-read in session | 100% |
| Citations verified semantically | Soft verification bugs | 0 |
| Deep-dive pass rate | Eval suite | >85% |

---

## Sprint Schedule

| Sprint | Focus | Story Points |
|--------|-------|--------------|
| Sprint 1-2 | Smart File Discovery | 26 |
| Sprint 3-4 | Intelligent Tool Orchestration | 24 |
| Sprint 5 | Self-Correction + Citation Verification | 34 |
| Sprint 6 | Security + Eval + Polish | 24 |

---

*Backlog generated by THE ALGORITHM - DETERMINED mode analysis*
*V3 focus: Intelligent exploration over raw tool access*
