"""
Category-based metrics for evaluation.

Tracks pass/fail rates and citation metrics per question category,
enabling targeted improvements for specific problem areas.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class CategoryMetrics:
    """Metrics for a single question category."""

    category: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    total_citations: int = 0
    verified_citations: int = 0

    @property
    def pass_rate(self) -> float:
        """Pass rate as a percentage (0-100)."""
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100

    @property
    def avg_citations(self) -> float:
        """Average citations per question."""
        if self.total == 0:
            return 0.0
        return self.total_citations / self.total

    @property
    def citation_accuracy(self) -> float:
        """Percentage of citations that were verified."""
        if self.total_citations == 0:
            return 0.0
        return (self.verified_citations / self.total_citations) * 100


# Categories tracked by the eval system
TRACKED_CATEGORIES = [
    "architecture",
    "dependencies",
    "code_flow",
    "debugging",
    "specific_file",
    "overview",
    "language_detection",
]


def aggregate_by_category(results: list[dict]) -> dict[str, CategoryMetrics]:
    """
    Aggregate evaluation results by question category.

    Args:
        results: List of per-repo result dictionaries from eval runs.
                 Each result should contain 'tests' dict with test results
                 and optionally 'diverse_questions' with question results.

    Returns:
        Dictionary mapping category names to CategoryMetrics.
    """
    category_data: dict[str, CategoryMetrics] = {}

    # Initialize all tracked categories
    for cat in TRACKED_CATEGORIES:
        category_data[cat] = CategoryMetrics(category=cat)

    for repo_result in results:
        # Process standard tests (map test names to categories)
        tests = repo_result.get("tests", {})
        for test_name, test_result in tests.items():
            if not isinstance(test_result, dict):
                continue

            # Map standard test names to categories
            category = _map_test_to_category(test_name)
            if category not in category_data:
                category_data[category] = CategoryMetrics(category=category)

            metrics = category_data[category]
            metrics.total += 1

            if test_result.get("passed", False):
                metrics.passed += 1
            else:
                metrics.failed += 1

            # Accumulate citation metrics
            metrics.total_citations += test_result.get("citations", 0)
            metrics.verified_citations += test_result.get("verified_citations", 0)

        # Process diverse questions (have explicit category field)
        diverse = repo_result.get("diverse_questions", {})
        if diverse and "questions" in diverse:
            for q_result in diverse["questions"]:
                category = q_result.get("category", "unknown")
                if category not in category_data:
                    category_data[category] = CategoryMetrics(category=category)

                metrics = category_data[category]
                metrics.total += 1

                if q_result.get("passed", False):
                    metrics.passed += 1
                else:
                    metrics.failed += 1

                metrics.total_citations += q_result.get("citations", 0)
                metrics.verified_citations += q_result.get("verified_citations", 0)

    # Remove categories with no data
    return {k: v for k, v in category_data.items() if v.total > 0}


def _map_test_to_category(test_name: str) -> str:
    """
    Map standard test names to categories.

    Args:
        test_name: Name of the test (e.g., 'overview', 'deep_dive', 'language_detection')

    Returns:
        Category name
    """
    mapping = {
        "overview": "overview",
        "deep_dive": "architecture",
        "language_detection": "language_detection",
    }
    return mapping.get(test_name, "other")


def format_category_metrics_table(metrics: dict[str, CategoryMetrics]) -> str:
    """
    Format category metrics as a table.

    Args:
        metrics: Dictionary of category name to CategoryMetrics

    Returns:
        Formatted table string
    """
    lines = []
    lines.append("┌" + "─" * 70 + "┐")
    lines.append("│" + " PER-CATEGORY METRICS".center(70) + "│")
    lines.append(
        "├"
        + "─" * 20
        + "┬"
        + "─" * 12
        + "┬"
        + "─" * 12
        + "┬"
        + "─" * 12
        + "┬"
        + "─" * 12
        + "┤"
    )
    lines.append(
        "│"
        + " Category".ljust(20)
        + "│"
        + " Pass Rate".center(12)
        + "│"
        + " Passed".center(12)
        + "│"
        + " Failed".center(12)
        + "│"
        + " Avg Cites".center(12)
        + "│"
    )
    lines.append(
        "├"
        + "─" * 20
        + "┼"
        + "─" * 12
        + "┼"
        + "─" * 12
        + "┼"
        + "─" * 12
        + "┼"
        + "─" * 12
        + "┤"
    )

    # Sort by pass rate (ascending to show problem areas first)
    sorted_categories = sorted(metrics.items(), key=lambda x: x[1].pass_rate)

    for category, m in sorted_categories:
        # Status indicator
        if m.pass_rate >= 80:
            indicator = "🟢"
        elif m.pass_rate >= 60:
            indicator = "🟡"
        else:
            indicator = "🔴"

        lines.append(
            f"│ {indicator} {category[:17].ljust(17)}"
            f"│{f'{m.pass_rate:.1f}%'.center(12)}"
            f"│{str(m.passed).center(12)}"
            f"│{str(m.failed).center(12)}"
            f"│{f'{m.avg_citations:.1f}'.center(12)}│"
        )

    lines.append(
        "└"
        + "─" * 20
        + "┴"
        + "─" * 12
        + "┴"
        + "─" * 12
        + "┴"
        + "─" * 12
        + "┴"
        + "─" * 12
        + "┘"
    )

    return "\n".join(lines)


def metrics_to_dict(metrics: dict[str, CategoryMetrics]) -> dict[str, dict[str, Any]]:
    """
    Convert category metrics to JSON-serializable dictionary.

    Args:
        metrics: Dictionary of category name to CategoryMetrics

    Returns:
        Nested dictionary suitable for JSON serialization
    """
    return {
        category: {
            "category": m.category,
            "total": m.total,
            "passed": m.passed,
            "failed": m.failed,
            "pass_rate": m.pass_rate,
            "total_citations": m.total_citations,
            "verified_citations": m.verified_citations,
            "avg_citations": m.avg_citations,
            "citation_accuracy": m.citation_accuracy,
        }
        for category, m in metrics.items()
    }


def identify_problem_categories(
    metrics: dict[str, CategoryMetrics], threshold: float = 70.0
) -> list[tuple[str, float]]:
    """
    Identify categories with pass rates below threshold.

    Args:
        metrics: Dictionary of category name to CategoryMetrics
        threshold: Pass rate threshold (default 70%)

    Returns:
        List of (category, pass_rate) tuples for problem categories,
        sorted by pass rate ascending (worst first)
    """
    problems = []
    for category, m in metrics.items():
        if m.pass_rate < threshold and m.total > 0:
            problems.append((category, m.pass_rate))

    return sorted(problems, key=lambda x: x[1])
