"""
Smart discovery tools for codebase analysis.
Build import dependency graphs for repositories.
"""

import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


class ImportGraphBuilder:
    """Build import dependency graph for a repository."""

    PYTHON_IMPORT_PATTERNS = [
        r"^import\s+(\S+)",
        r"^from\s+(\S+)\s+import",
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

        for js_file in self.repo_path.glob("**/*.ts"):
            if self._should_skip(js_file):
                continue
            self._parse_js_imports(js_file)

        # Also handle tsx, js, jsx
        for ext in ["tsx", "js", "jsx"]:
            for js_file in self.repo_path.glob(f"**/*.{ext}"):
                if self._should_skip(js_file):
                    continue
                self._parse_js_imports(js_file)

        return dict(self.graph)

    def _should_skip(self, path: Path) -> bool:
        """Skip node_modules, venv, etc."""
        skip_dirs = {
            "node_modules",
            ".git",
            "__pycache__",
            "venv",
            ".venv",
            "dist",
            "build",
        }
        return any(part in skip_dirs for part in path.parts)

    def _parse_python_imports(self, file_path: Path):
        """Extract imports from Python file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return

        rel_path = str(file_path.relative_to(self.repo_path))

        for line in content.split("\n"):
            for pattern in self.PYTHON_IMPORT_PATTERNS:
                match = re.match(pattern, line.strip())
                if match:
                    imported = match.group(1).split(".")[0]
                    self.graph[rel_path].add(imported)
                    self.reverse_graph[imported].add(rel_path)

    def _parse_js_imports(self, file_path: Path):
        """Extract imports from JavaScript/TypeScript file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return

        rel_path = str(file_path.relative_to(self.repo_path))

        for line in content.split("\n"):
            for pattern in self.JS_IMPORT_PATTERNS:
                match = re.match(pattern, line.strip())
                if match:
                    imported = match.group(1)
                    # Normalize: remove leading ./ and file extensions
                    imported = imported.lstrip("./")
                    imported = re.sub(r"\.(ts|tsx|js|jsx)$", "", imported)
                    self.graph[rel_path].add(imported)
                    self.reverse_graph[imported].add(rel_path)

    def get_importers(self, module: str) -> set[str]:
        """Get files that import this module (in-degree)."""
        return self.reverse_graph.get(module, set())


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
            "indicators": ["components", "pages"],
            "optional": ["hooks", "store", "redux", "context"],
            "entry_points": [
                "src/App.tsx",
                "src/main.tsx",
                "src/index.tsx",
                "src/App.js",
            ],
        },
        "monorepo": {
            "indicators": ["packages", "apps"],
            "config_files": [
                "lerna.json",
                "nx.json",
                "pnpm-workspace.yaml",
                "turbo.json",
            ],
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
            "indicators": [],
            "code_patterns": ["FastAPI()", "from fastapi"],
            "entry_points": ["main.py", "app.py"],
        },
        "flask": {
            "indicators": [],
            "code_patterns": ["Flask(__name__)", "from flask"],
            "entry_points": ["app.py", "main.py", "run.py"],
        },
    }

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def detect(self) -> list[ArchitecturePattern]:
        """Detect all matching architecture patterns."""
        detected = []

        # Get directory and file listings
        try:
            dirs = {d.name.lower() for d in self.repo_path.iterdir() if d.is_dir()}
        except Exception:
            dirs = set()

        try:
            files = {f.name for f in self.repo_path.glob("*") if f.is_file()}
        except Exception:
            files = set()

        try:
            all_files = {
                str(f.relative_to(self.repo_path))
                for f in self.repo_path.glob("**/*")
                if f.is_file()
            }
        except Exception:
            all_files = set()

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
                    detected.append(
                        ArchitecturePattern(
                            name=pattern_name,
                            confidence=confidence,
                            evidence=evidence,
                            suggested_entry_points=config.get("entry_points", []),
                        )
                    )

        return sorted(detected, key=lambda x: x.confidence, reverse=True)

    def _search_code_pattern(self, pattern: str) -> bool:
        """Quick search for code pattern in key files."""
        for ext in ["*.py", "*.ts", "*.js"]:
            try:
                for f in list(self.repo_path.glob(ext))[:10]:  # Check first 10 files
                    try:
                        if pattern in f.read_text():
                            return True
                    except Exception:
                        pass
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
        "main": 1.0,
        "app": 1.0,
        "index": 0.9,
        "server": 0.9,
        "cli": 0.8,
        "api": 0.8,
        "routes": 0.7,
        "models": 0.7,
        "config": 0.6,
        "settings": 0.6,
        "utils": 0.3,
        "helpers": 0.3,
        "__init__": 0.1,
        "test": 0.2,
        "conftest": 0.2,
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
                0.40 * self.scores[file_path].centrality
                + 0.25 * self.scores[file_path].naming
                + 0.20 * self.scores[file_path].size
                + 0.15 * self.scores[file_path].git_activity
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
            lines = len(full_path.read_text().split("\n"))
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
                ["git", "log", "--oneline", "--", file_path],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            commits = (
                len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
            )
            return min(commits / 50, 1.0)  # 50+ commits = max score
        except Exception:
            return 0.5  # Default if git not available

    def get_top_files(self, n: int = 20) -> list[FileScore]:
        """Return most important files."""
        sorted_files = sorted(
            self.scores.values(), key=lambda x: x.total_score, reverse=True
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
            importance = (
                "🔴"
                if score.total_score > 0.7
                else "🟡"
                if score.total_score > 0.4
                else "⚪"
            )
            result.append(f"{i:2d}. {importance} {score.path}")
            result.append(
                f"     Score: {score.total_score:.2f} (centrality: {score.centrality:.2f}, naming: {score.naming:.2f})"
            )

        result.append("")
        result.append(
            "💡 TIP: Start with 🔴 high-importance files for architecture understanding."
        )
        result.append(
            "💡 SKIP: Files like __init__.py, index.ts (re-exports only) are usually trivial."
        )

        return "\n".join(result)

    except Exception as e:
        return f"Error analyzing repository: {e}"


def get_smart_discovery_tools():
    """Get smart discovery tools for agent."""
    return [get_important_files]
