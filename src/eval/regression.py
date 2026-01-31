"""
Regression detection for evaluation results.

Compares current eval run against historical runs to detect:
- Category-level regressions (>10% drop from average of last 3 runs)
- Repository-level regressions (>20% drop from previous run)
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class RegressionWarning:
    """A detected regression in eval metrics."""

    level: str  # "category" or "repo"
    name: str  # Category or repo name
    current_value: float
    baseline_value: float
    drop_percent: float
    message: str


def get_category_averages(history: list[dict], last_n: int = 3) -> dict[str, float]:
    """
    Calculate average pass rates per category from recent history.

    Args:
        history: List of historical eval results
        last_n: Number of recent runs to average

    Returns:
        Dictionary mapping category names to average pass rates
    """
    if not history:
        return {}

    recent = history[-last_n:]
    category_values: dict[str, list[float]] = {}

    for run in recent:
        # Check by_question_category first (new format from Phase 04)
        by_category = run.get("by_question_category", {})
        if by_category:
            for cat, metrics in by_category.items():
                if cat not in category_values:
                    category_values[cat] = []
                # metrics might be a dict with pass_rate key
                if isinstance(metrics, dict):
                    pass_rate = metrics.get("pass_rate", 0)
                    category_values[cat].append(pass_rate)

        # Also check by_category (legacy format - repo category, not question category)
        by_cat = run.get("by_category", {})
        for cat, stats in by_cat.items():
            if isinstance(stats, dict):
                passed = stats.get("passed", 0)
                failed = stats.get("failed", 0)
                total = passed + failed
                if total > 0:
                    pass_rate = (passed / total) * 100
                    key = (
                        f"repo_{cat}"  # Prefix to distinguish from question categories
                    )
                    if key not in category_values:
                        category_values[key] = []
                    category_values[key].append(pass_rate)

    # Calculate averages
    return {
        cat: sum(values) / len(values)
        for cat, values in category_values.items()
        if values
    }


def get_repo_pass_rates(run: dict) -> dict[str, float]:
    """
    Extract per-repo pass rates from a run.

    Args:
        run: Eval run result dictionary

    Returns:
        Dictionary mapping repo names to pass rates
    """
    by_language = run.get("by_language", {})
    repo_rates = {}

    for lang, stats in by_language.items():
        if isinstance(stats, dict):
            passed = stats.get("passed", 0)
            failed = stats.get("failed", 0)
            total = passed + failed
            if total > 0:
                repo_rates[lang] = (passed / total) * 100

    return repo_rates


def detect_regressions(
    current: dict,
    history: list[dict],
    category_threshold: float = 10.0,
    repo_threshold: float = 20.0,
) -> list[RegressionWarning]:
    """
    Detect regressions in current eval run compared to historical runs.

    Args:
        current: Current eval run results
        history: List of historical eval results
        category_threshold: Percentage drop to flag for categories (default 10%)
        repo_threshold: Percentage drop to flag for repos (default 20%)

    Returns:
        List of RegressionWarning objects for detected regressions
    """
    warnings: list[RegressionWarning] = []

    if not history:
        return warnings

    # Category regressions (compare to average of last 3 runs)
    category_averages = get_category_averages(history, last_n=3)

    # Get current category metrics
    current_by_category = current.get("by_question_category", {})
    for cat, metrics in current_by_category.items():
        if cat not in category_averages:
            continue

        current_rate = metrics.get("pass_rate", 0) if isinstance(metrics, dict) else 0
        avg_rate = category_averages[cat]

        if avg_rate > 0:
            drop = avg_rate - current_rate
            drop_percent = (drop / avg_rate) * 100

            if drop_percent > category_threshold:
                warnings.append(
                    RegressionWarning(
                        level="category",
                        name=cat,
                        current_value=current_rate,
                        baseline_value=avg_rate,
                        drop_percent=drop_percent,
                        message=f"Category '{cat}' dropped {drop_percent:.1f}% (from avg {avg_rate:.1f}% to {current_rate:.1f}%)",
                    )
                )

    # Also check legacy by_category (repo categories)
    current_by_cat = current.get("by_category", {})
    for cat, stats in current_by_cat.items():
        if not isinstance(stats, dict):
            continue

        key = f"repo_{cat}"
        if key not in category_averages:
            continue

        passed = stats.get("passed", 0)
        failed = stats.get("failed", 0)
        total = passed + failed
        current_rate = (passed / total) * 100 if total > 0 else 0
        avg_rate = category_averages[key]

        if avg_rate > 0:
            drop = avg_rate - current_rate
            drop_percent = (drop / avg_rate) * 100

            if drop_percent > category_threshold:
                warnings.append(
                    RegressionWarning(
                        level="category",
                        name=f"repo:{cat}",
                        current_value=current_rate,
                        baseline_value=avg_rate,
                        drop_percent=drop_percent,
                        message=f"Repo category '{cat}' dropped {drop_percent:.1f}% (from avg {avg_rate:.1f}% to {current_rate:.1f}%)",
                    )
                )

    # Repo/language regressions (compare to previous run only)
    if len(history) >= 1:
        previous = history[-1]
        prev_rates = get_repo_pass_rates(previous)
        curr_rates = get_repo_pass_rates(current)

        for lang, curr_rate in curr_rates.items():
            if lang not in prev_rates:
                continue

            prev_rate = prev_rates[lang]
            if prev_rate > 0:
                drop = prev_rate - curr_rate
                drop_percent = (drop / prev_rate) * 100

                if drop_percent > repo_threshold:
                    warnings.append(
                        RegressionWarning(
                            level="repo",
                            name=lang,
                            current_value=curr_rate,
                            baseline_value=prev_rate,
                            drop_percent=drop_percent,
                            message=f"Language '{lang}' dropped {drop_percent:.1f}% from previous run (from {prev_rate:.1f}% to {curr_rate:.1f}%)",
                        )
                    )

    # Sort by severity (highest drop first)
    warnings.sort(key=lambda w: w.drop_percent, reverse=True)

    return warnings


def format_regression_warnings(warnings: list[RegressionWarning]) -> str:
    """
    Format regression warnings for display.

    Args:
        warnings: List of RegressionWarning objects

    Returns:
        Formatted string for display
    """
    if not warnings:
        return "✅ No regressions detected"

    lines = []
    lines.append("🔴 REGRESSION WARNINGS DETECTED")
    lines.append("─" * 50)

    category_warnings = [w for w in warnings if w.level == "category"]
    repo_warnings = [w for w in warnings if w.level == "repo"]

    if category_warnings:
        lines.append("\n📊 Category Regressions (>10% drop from 3-run average):")
        for w in category_warnings:
            lines.append(f"  ⚠️  {w.message}")

    if repo_warnings:
        lines.append("\n📦 Repo/Language Regressions (>20% drop from previous run):")
        for w in repo_warnings:
            lines.append(f"  ⚠️  {w.message}")

    lines.append("")
    lines.append(f"Total: {len(warnings)} regression(s) detected")

    return "\n".join(lines)


def regression_warnings_to_dict(
    warnings: list[RegressionWarning],
) -> list[dict[str, Any]]:
    """
    Convert regression warnings to JSON-serializable format.

    Args:
        warnings: List of RegressionWarning objects

    Returns:
        List of dictionaries suitable for JSON serialization
    """
    return [
        {
            "level": w.level,
            "name": w.name,
            "current_value": w.current_value,
            "baseline_value": w.baseline_value,
            "drop_percent": w.drop_percent,
            "message": w.message,
        }
        for w in warnings
    ]
