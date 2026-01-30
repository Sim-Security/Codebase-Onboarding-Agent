"""Working memory for codebase exploration sessions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


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
    max_line: int = 0  # Highest line number in the file
    summary: str = ""  # Brief summary of content
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

    def add_file_read(self, path: str, lines: int, summary: str, max_line: int = 0):
        """Record that a file was read."""
        # Normalize path for consistent matching
        normalized = self._normalize_path(path)
        self.files_read.add(normalized)
        self.key_files.append(
            FileRead(
                path=normalized, lines_read=lines, max_line=max_line, summary=summary
            )
        )

    def _normalize_path(self, path: str) -> str:
        """Normalize file path for consistent matching."""
        # Remove leading ./ or /
        path = path.lstrip("./")
        # Get just the filename for simple matching
        return path

    def add_fact(self, fact: str, citation: str):
        """Add a confirmed fact with its citation."""
        self.confirmed_facts.append(ConfirmedFact(fact=fact, citation=citation))

    def add_search(self, pattern: str, results: int, key_files: list[str]):
        """Record a search that was performed."""
        self.searches_performed.append(
            SearchPerformed(pattern=pattern, results_count=results, key_files=key_files)
        )

    def was_file_read(self, path: str) -> bool:
        """Check if file was already read."""
        normalized = self._normalize_path(path)
        # Check exact match
        if normalized in self.files_read:
            return True
        # Check if filename matches any read file
        filename = normalized.split("/")[-1]
        for read_path in self.files_read:
            if read_path.endswith(filename) or read_path == filename:
                return True
        return False

    def can_cite_line(self, path: str, line: int) -> bool:
        """Check if a specific line can be cited (file was read and line exists)."""
        if not self.was_file_read(path):
            return False
        # Find the file read record
        filename = self._normalize_path(path).split("/")[-1]
        for file_read in self.key_files:
            if file_read.path.endswith(filename) or file_read.path == filename:
                # Check if line is within range
                if file_read.max_line > 0:
                    return line <= file_read.max_line
                # If we don't have max_line info, trust that it was read
                return True
        return False

    def get_citable_files(self) -> list[str]:
        """Get list of files that can be cited (were read with read_file)."""
        return sorted(self.files_read)

    def to_context_string(self, max_facts: int = 10) -> str:
        """Convert to string for LLM context injection."""
        lines = ["## WORKING MEMORY", ""]

        if self.architecture_pattern:
            lines.append(f"Architecture: {self.architecture_pattern}")
        if self.primary_language:
            lines.append(f"Language: {self.primary_language}")

        # CRITICAL: Show files that can be cited
        if self.files_read:
            lines.append("\n### FILES YOU CAN CITE (read with read_file):")
            for f in sorted(self.files_read)[:20]:
                # Find max_line for this file
                max_line = 0
                for kf in self.key_files:
                    if kf.path == f:
                        max_line = max(max_line, kf.max_line)
                if max_line > 0:
                    lines.append(f"- {f} (lines 1-{max_line})")
                else:
                    lines.append(f"- {f}")
            lines.append(
                "\n**CITATION RULE:** You can ONLY cite file:line for files listed above."
            )
        else:
            lines.append("\n### NO FILES READ YET")
            lines.append("**You must call read_file before citing any line numbers!**")

        if self.confirmed_facts:
            lines.append("\n### Confirmed Facts:")
            for fact in self.confirmed_facts[-max_facts:]:
                lines.append(f"- {fact.fact} [{fact.citation}]")

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
