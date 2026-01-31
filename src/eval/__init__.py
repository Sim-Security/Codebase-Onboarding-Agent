"""Evaluation and verification utilities."""

from .pass_at_k import (
    PassAtKResult,
    RunResult,
    aggregate_pass_at_k_results,
    format_pass_at_k_report,
    run_with_pass_at_k,
)
from .questions import (
    FEATURE_AREAS,
    QUESTION_TEMPLATES,
    QuestionTemplate,
    get_all_questions,
    get_questions_for_repo,
)
from .tool_metrics import (
    AggregateToolMetrics,
    ToolUsageMetrics,
    aggregate_tool_metrics,
    extract_tool_metrics,
    format_tool_metrics_report,
    metrics_to_dict,
)
from .verification import (
    CitationResult,
    Claim,
    GroundingResult,
    calculate_citation_metrics,
    compute_relevance,
    extract_citations,
    extract_claims,
    filter_ungrounded_citations,
    get_files_read_from_tool_calls,
    get_grounded_citations_only,
    ground_claims,
    validate_tool_usage,
    verify_citation,
)

__all__ = [
    # Verification
    "verify_citation",
    "extract_citations",
    "CitationResult",
    "extract_claims",
    "Claim",
    "ground_claims",
    "GroundingResult",
    "compute_relevance",
    "calculate_citation_metrics",
    "filter_ungrounded_citations",
    "get_grounded_citations_only",
    "get_files_read_from_tool_calls",
    "validate_tool_usage",
    # Questions
    "QuestionTemplate",
    "QUESTION_TEMPLATES",
    "FEATURE_AREAS",
    "get_questions_for_repo",
    "get_all_questions",
    # Pass@k
    "RunResult",
    "PassAtKResult",
    "run_with_pass_at_k",
    "aggregate_pass_at_k_results",
    "format_pass_at_k_report",
    # Tool Metrics
    "ToolUsageMetrics",
    "AggregateToolMetrics",
    "extract_tool_metrics",
    "aggregate_tool_metrics",
    "format_tool_metrics_report",
    "metrics_to_dict",
]
