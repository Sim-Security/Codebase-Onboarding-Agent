"""Tool routing and usage tracking for intelligent orchestration."""

import logging
from dataclasses import dataclass
from typing import Optional

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
        prerequisites=[
            "search_code",
            "find_files_by_pattern",
            "list_directory_structure",
            "get_important_files",
        ],
        min_prerequisite_count=1,
        warning_message="Consider searching for relevant files before reading directly.",
    ),
    "get_function_signatures": RoutingRule(
        tool_name="get_function_signatures",
        prerequisites=["list_directory_structure", "read_file"],
        min_prerequisite_count=1,
        warning_message="Understand file content before extracting signatures.",
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

    def get_recommended_next_tool(self, current_context: str = "") -> Optional[str]:
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
        self.output_hashes: set[int] = set()
        self.circuit_breaker = CircuitBreakerState()

    def record_call(self, tool_name: str, tool_input: str, tool_output: str):
        """Record a tool call and check for issues."""
        # Hash outputs to detect repeats
        output_hash = hash(tool_output[:500])
        is_new_info = output_hash not in self.output_hashes

        self.call_history.append(
            {
                "name": tool_name,
                "input": tool_input[:100],
                "is_new": is_new_info,
            }
        )

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
            recent = self.call_history[-self.THRASHING_WINDOW :]
            tool_names = [c["name"] for c in recent]

            for tool in set(tool_names):
                if tool_names.count(tool) >= self.THRASHING_THRESHOLD:
                    return (
                        True,
                        f"Repetitive use of {tool} ({tool_names.count(tool)} times in last {self.THRASHING_WINDOW} calls)",
                    )

        # Check for no new information
        if self.circuit_breaker.calls_without_new_info >= 5:
            return True, "No new information in last 5 tool calls"

        # Check per-tool limits
        tool_counts: dict[str, int] = {}
        for call in self.call_history:
            tool_counts[call["name"]] = tool_counts.get(call["name"], 0) + 1

        for tool, count in tool_counts.items():
            if count >= self.MAX_CALLS_PER_TOOL:
                return (
                    True,
                    f"{tool} called {count} times (limit: {self.MAX_CALLS_PER_TOOL})",
                )

        return False, ""

    def get_graceful_exit_message(self, question: str) -> str:
        """Generate helpful message when circuit breaker trips."""
        stats = self.get_stats()

        message = f"""I've explored extensively but couldn't find a complete answer to your question.

**What I searched:**
- Made {stats["total_calls"]} tool calls
- Read {stats["unique_files"]} files
- Found {stats["new_info_calls"]} pieces of new information

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
