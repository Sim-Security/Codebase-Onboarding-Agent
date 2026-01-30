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
        self.searches_performed.append(
            SearchPerformed(pattern=pattern, results_count=results, key_files=key_files)
        )

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
