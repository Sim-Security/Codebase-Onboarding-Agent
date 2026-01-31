"""
Tool usage metrics for evaluation.

Tracks tool usage patterns to identify when the agent answers questions
without properly grounding responses in file reads.
"""

from dataclasses import dataclass, field


@dataclass
class ToolUsageMetrics:
    """Metrics for tool usage in a single question/response."""

    question_id: str
    read_file_calls: int = 0
    search_code_calls: int = 0
    other_tool_calls: int = 0
    total_tool_calls: int = 0
    citations_count: int = 0
    has_citations_without_read: bool = False
    files_read: list[str] = field(default_factory=list)
    files_cited: list[str] = field(default_factory=list)
    ungrounded_files: list[str] = field(default_factory=list)

    @property
    def grounding_valid(self) -> bool:
        """True if all citations are properly grounded in read files."""
        return not self.has_citations_without_read and len(self.ungrounded_files) == 0


@dataclass
class AggregateToolMetrics:
    """Aggregated tool metrics across multiple questions."""

    total_questions: int = 0
    questions_with_read_file: int = 0
    questions_with_citations: int = 0
    questions_with_ungrounded_citations: int = 0
    total_read_file_calls: int = 0
    total_search_code_calls: int = 0
    total_tool_calls: int = 0
    total_citations: int = 0
    grounding_violation_count: int = 0

    @property
    def read_file_rate(self) -> float:
        """Percentage of questions where read_file was called."""
        if self.total_questions == 0:
            return 0.0
        return (self.questions_with_read_file / self.total_questions) * 100

    @property
    def grounding_rate(self) -> float:
        """Percentage of questions with properly grounded citations."""
        if self.questions_with_citations == 0:
            return 100.0  # No citations = no violations
        grounded = (
            self.questions_with_citations - self.questions_with_ungrounded_citations
        )
        return (grounded / self.questions_with_citations) * 100

    @property
    def avg_read_file_per_question(self) -> float:
        """Average number of read_file calls per question."""
        if self.total_questions == 0:
            return 0.0
        return self.total_read_file_calls / self.total_questions

    @property
    def avg_search_code_per_question(self) -> float:
        """Average number of search_code calls per question."""
        if self.total_questions == 0:
            return 0.0
        return self.total_search_code_calls / self.total_questions


def extract_tool_metrics(
    tool_calls: list[dict],
    response: str,
    question_id: str = "unknown",
) -> ToolUsageMetrics:
    """
    Extract tool usage metrics from a single agent run.

    Args:
        tool_calls: List of tool call dictionaries with format:
                    {"name": str, "args": dict}
        response: The agent's final text response
        question_id: Identifier for the question (for tracking)

    Returns:
        ToolUsageMetrics with comprehensive usage data
    """
    from .verification import extract_citations, get_files_read_from_tool_calls

    metrics = ToolUsageMetrics(question_id=question_id)

    # Count tool calls by type
    for tc in tool_calls:
        tool_name = tc.get("name", "")
        metrics.total_tool_calls += 1

        if tool_name == "read_file":
            metrics.read_file_calls += 1
        elif tool_name == "search_code":
            metrics.search_code_calls += 1
        else:
            metrics.other_tool_calls += 1

    # Get files read
    files_read = get_files_read_from_tool_calls(tool_calls)
    metrics.files_read = list(files_read)

    # Extract citations from response
    citations = extract_citations(response)
    metrics.citations_count = len(citations)

    # Get unique cited files
    cited_files = set()
    for citation in citations:
        file_path = citation.get("file", "")
        if file_path:
            cited_files.add(file_path)
    metrics.files_cited = list(cited_files)

    # Check for grounding violations
    if metrics.citations_count > 0 and metrics.read_file_calls == 0:
        metrics.has_citations_without_read = True

    # Find ungrounded files (cited but never read)
    for cited_file in cited_files:
        cited_basename = cited_file.split("/")[-1]
        file_was_read = False

        for read_file in files_read:
            read_basename = read_file.split("/")[-1]
            if (
                read_file == cited_file
                or read_file.endswith(cited_file)
                or cited_file.endswith(read_file)
                or cited_basename == read_basename
            ):
                file_was_read = True
                break

        if not file_was_read:
            metrics.ungrounded_files.append(cited_file)

    return metrics


def aggregate_tool_metrics(
    metrics_list: list[ToolUsageMetrics],
) -> AggregateToolMetrics:
    """
    Aggregate tool metrics across multiple questions.

    Args:
        metrics_list: List of ToolUsageMetrics from individual questions

    Returns:
        AggregateToolMetrics with summary statistics
    """
    aggregate = AggregateToolMetrics()
    aggregate.total_questions = len(metrics_list)

    for m in metrics_list:
        aggregate.total_read_file_calls += m.read_file_calls
        aggregate.total_search_code_calls += m.search_code_calls
        aggregate.total_tool_calls += m.total_tool_calls
        aggregate.total_citations += m.citations_count

        if m.read_file_calls > 0:
            aggregate.questions_with_read_file += 1

        if m.citations_count > 0:
            aggregate.questions_with_citations += 1

        if m.has_citations_without_read or len(m.ungrounded_files) > 0:
            aggregate.questions_with_ungrounded_citations += 1
            aggregate.grounding_violation_count += 1

    return aggregate


def format_tool_metrics_report(
    aggregate: AggregateToolMetrics,
    per_question_metrics: list[ToolUsageMetrics] | None = None,
) -> str:
    """
    Format tool metrics for display.

    Args:
        aggregate: Aggregated metrics
        per_question_metrics: Optional per-question metrics for detailed view

    Returns:
        Formatted report string
    """
    lines = []
    lines.append("┌" + "─" * 58 + "┐")
    lines.append("│" + " TOOL USAGE METRICS".center(58) + "│")
    lines.append("├" + "─" * 58 + "┤")

    # Summary stats
    read_indicator = (
        "🟢"
        if aggregate.read_file_rate >= 80
        else "🟡"
        if aggregate.read_file_rate >= 60
        else "🔴"
    )
    grounding_indicator = (
        "🟢"
        if aggregate.grounding_rate >= 90
        else "🟡"
        if aggregate.grounding_rate >= 70
        else "🔴"
    )

    lines.append(
        f"│  read_file Usage: {read_indicator} {aggregate.read_file_rate:.1f}%".ljust(
            59
        )
        + "│"
    )
    lines.append(
        f"│  Grounding Rate: {grounding_indicator} {aggregate.grounding_rate:.1f}%".ljust(
            59
        )
        + "│"
    )
    lines.append("├" + "─" * 58 + "┤")
    lines.append(f"│  Total Questions: {aggregate.total_questions}".ljust(59) + "│")
    lines.append(
        f"│  Questions with read_file: {aggregate.questions_with_read_file}".ljust(59)
        + "│"
    )
    lines.append(
        f"│  Questions with Citations: {aggregate.questions_with_citations}".ljust(59)
        + "│"
    )
    lines.append(
        f"│  Grounding Violations: {aggregate.grounding_violation_count}".ljust(59)
        + "│"
    )
    lines.append("├" + "─" * 58 + "┤")
    lines.append(
        f"│  Avg read_file/question: {aggregate.avg_read_file_per_question:.2f}".ljust(
            59
        )
        + "│"
    )
    lines.append(
        f"│  Avg search_code/question: {aggregate.avg_search_code_per_question:.2f}".ljust(
            59
        )
        + "│"
    )
    lines.append(f"│  Total Tool Calls: {aggregate.total_tool_calls}".ljust(59) + "│")
    lines.append("└" + "─" * 58 + "┘")

    # Per-question details for violations
    if per_question_metrics:
        violations = [m for m in per_question_metrics if not m.grounding_valid]
        if violations:
            lines.append("")
            lines.append("⚠️  Grounding Violations:")
            for v in violations[:10]:  # Show up to 10 violations
                lines.append(f"   • {v.question_id}:")
                if v.has_citations_without_read:
                    lines.append(
                        f"     - {v.citations_count} citations but 0 read_file calls"
                    )
                if v.ungrounded_files:
                    lines.append(
                        f"     - Unread files cited: {', '.join(v.ungrounded_files[:3])}"
                    )

    return "\n".join(lines)


def metrics_to_dict(metrics: ToolUsageMetrics | AggregateToolMetrics) -> dict:
    """Convert metrics to dictionary for JSON serialization."""
    if isinstance(metrics, ToolUsageMetrics):
        return {
            "question_id": metrics.question_id,
            "read_file_calls": metrics.read_file_calls,
            "search_code_calls": metrics.search_code_calls,
            "other_tool_calls": metrics.other_tool_calls,
            "total_tool_calls": metrics.total_tool_calls,
            "citations_count": metrics.citations_count,
            "has_citations_without_read": metrics.has_citations_without_read,
            "files_read": metrics.files_read,
            "files_cited": metrics.files_cited,
            "ungrounded_files": metrics.ungrounded_files,
            "grounding_valid": metrics.grounding_valid,
        }
    else:
        return {
            "total_questions": metrics.total_questions,
            "questions_with_read_file": metrics.questions_with_read_file,
            "questions_with_citations": metrics.questions_with_citations,
            "questions_with_ungrounded_citations": metrics.questions_with_ungrounded_citations,
            "total_read_file_calls": metrics.total_read_file_calls,
            "total_search_code_calls": metrics.total_search_code_calls,
            "total_tool_calls": metrics.total_tool_calls,
            "total_citations": metrics.total_citations,
            "grounding_violation_count": metrics.grounding_violation_count,
            "read_file_rate": metrics.read_file_rate,
            "grounding_rate": metrics.grounding_rate,
            "avg_read_file_per_question": metrics.avg_read_file_per_question,
            "avg_search_code_per_question": metrics.avg_search_code_per_question,
        }
