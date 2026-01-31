"""
Pass@k metrics for evaluating agent consistency and reliability.

Pass@k measures: "If we run the test k times, what's the probability
that at least one run passes?"

This helps identify:
- Flaky tests (high variance between runs)
- Reliable capabilities (consistent passes)
- Edge cases that sometimes fail
"""

import statistics
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class RunResult:
    """Result of a single test run."""

    passed: bool
    metrics: dict = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class PassAtKResult:
    """Aggregated pass@k metrics for a test."""

    test_id: str
    k: int  # Number of runs
    passes: int  # Number of successful runs
    failures: int  # Number of failed runs

    # Core metrics
    pass_at_1: float  # Probability of passing on first try
    pass_at_k: float  # Probability of at least one pass in k tries

    # Consistency metrics
    consistency: float  # 1.0 = always same result, 0.0 = random
    variance: float  # Variance in numeric metrics

    # Individual runs
    runs: list[RunResult] = field(default_factory=list)

    # Aggregated metrics (averaged across runs)
    avg_metrics: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.k > 0:
            self.pass_at_1 = self.passes / self.k
            # pass@k = 1 - (probability of all failures)
            # If we have p = pass_at_1, then P(at least 1 pass in k) = 1 - (1-p)^k
            self.pass_at_k = 1 - ((1 - self.pass_at_1) ** self.k) if self.k > 0 else 0

            # Consistency: how often do we get the same result?
            # 1.0 if all pass or all fail, lower if mixed
            if self.passes == self.k or self.failures == self.k:
                self.consistency = 1.0
            else:
                # Use coefficient of variation (lower = more consistent)
                results = [1 if r.passed else 0 for r in self.runs]
                if len(results) > 1:
                    self.consistency = 1 - statistics.stdev(results)
                else:
                    self.consistency = 1.0


def run_with_pass_at_k(
    test_fn: Callable[[], tuple[bool, dict]],
    test_id: str,
    k: int = 3,
    stop_on_pass: bool = False,
) -> PassAtKResult:
    """
    Run a test k times and compute pass@k metrics.

    Args:
        test_fn: Function that returns (passed: bool, metrics: dict)
        test_id: Identifier for this test
        k: Number of times to run
        stop_on_pass: If True, stop after first pass (for efficiency)

    Returns:
        PassAtKResult with aggregated metrics
    """
    import time

    runs = []
    passes = 0
    failures = 0

    for i in range(k):
        start = time.time()
        try:
            passed, metrics = test_fn()
            duration = (time.time() - start) * 1000

            runs.append(
                RunResult(
                    passed=passed,
                    metrics=metrics,
                    duration_ms=duration,
                )
            )

            if passed:
                passes += 1
                if stop_on_pass:
                    break
            else:
                failures += 1

        except Exception as e:
            duration = (time.time() - start) * 1000
            runs.append(
                RunResult(
                    passed=False,
                    error=str(e),
                    duration_ms=duration,
                )
            )
            failures += 1

    # Aggregate numeric metrics
    avg_metrics = {}
    metric_keys = set()
    for run in runs:
        metric_keys.update(run.metrics.keys())

    for key in metric_keys:
        values = [r.metrics.get(key) for r in runs if key in r.metrics]
        numeric_values = [v for v in values if isinstance(v, (int, float))]
        if numeric_values:
            avg_metrics[key] = {
                "mean": statistics.mean(numeric_values),
                "min": min(numeric_values),
                "max": max(numeric_values),
                "stddev": statistics.stdev(numeric_values)
                if len(numeric_values) > 1
                else 0,
            }

    # Calculate variance across key metrics
    variance = 0.0
    if avg_metrics:
        variances = [m.get("stddev", 0) for m in avg_metrics.values()]
        variance = statistics.mean(variances) if variances else 0.0

    return PassAtKResult(
        test_id=test_id,
        k=len(runs),  # Actual runs (may be < k if stop_on_pass)
        passes=passes,
        failures=failures,
        pass_at_1=0,  # Will be calculated in __post_init__
        pass_at_k=0,
        consistency=0,
        variance=variance,
        runs=runs,
        avg_metrics=avg_metrics,
    )


def aggregate_pass_at_k_results(results: list[PassAtKResult]) -> dict:
    """
    Aggregate pass@k results across multiple tests.

    Returns:
        Summary statistics for the entire eval suite
    """
    if not results:
        return {}

    total_tests = len(results)
    total_runs = sum(r.k for r in results)
    total_passes = sum(r.passes for r in results)

    # Calculate aggregate pass rates
    pass_at_1_values = [r.pass_at_1 for r in results]
    pass_at_k_values = [r.pass_at_k for r in results]
    consistency_values = [r.consistency for r in results]

    return {
        "total_tests": total_tests,
        "total_runs": total_runs,
        "total_passes": total_passes,
        "overall_pass_rate": total_passes / total_runs if total_runs > 0 else 0,
        "pass_at_1": {
            "mean": statistics.mean(pass_at_1_values),
            "min": min(pass_at_1_values),
            "max": max(pass_at_1_values),
            "stddev": statistics.stdev(pass_at_1_values)
            if len(pass_at_1_values) > 1
            else 0,
        },
        "pass_at_k": {
            "mean": statistics.mean(pass_at_k_values),
            "min": min(pass_at_k_values),
            "max": max(pass_at_k_values),
        },
        "consistency": {
            "mean": statistics.mean(consistency_values),
            "min": min(consistency_values),
            "max": max(consistency_values),
        },
        # Identify flaky tests (passed sometimes but not always)
        "flaky_tests": [r.test_id for r in results if 0 < r.passes < r.k],
        "always_pass": [r.test_id for r in results if r.passes == r.k],
        "always_fail": [r.test_id for r in results if r.passes == 0],
    }


def format_pass_at_k_report(results: list[PassAtKResult], k: int) -> str:
    """Format pass@k results as a human-readable report."""
    lines = []
    lines.append(f"\n{'=' * 60}")
    lines.append(f"PASS@{k} METRICS")
    lines.append(f"{'=' * 60}")

    # Summary
    summary = aggregate_pass_at_k_results(results)
    lines.append(f"\nOverall Pass Rate: {summary['overall_pass_rate'] * 100:.1f}%")
    lines.append(f"Pass@1 (first try): {summary['pass_at_1']['mean'] * 100:.1f}%")
    lines.append(f"Pass@{k} (at least once): {summary['pass_at_k']['mean'] * 100:.1f}%")
    lines.append(f"Consistency: {summary['consistency']['mean'] * 100:.1f}%")

    # Flaky tests
    if summary["flaky_tests"]:
        lines.append(f"\n⚠️  Flaky Tests ({len(summary['flaky_tests'])}):")
        for test_id in summary["flaky_tests"][:5]:
            result = next(r for r in results if r.test_id == test_id)
            lines.append(f"   - {test_id}: {result.passes}/{result.k} passed")

    # Per-test breakdown
    lines.append(f"\n{'─' * 60}")
    lines.append("Per-Test Results:")
    lines.append(f"{'─' * 60}")

    for result in sorted(results, key=lambda r: r.pass_at_1, reverse=True):
        status = (
            "✅" if result.passes == result.k else "⚠️" if result.passes > 0 else "❌"
        )
        lines.append(
            f"  {status} {result.test_id}: {result.passes}/{result.k} "
            f"(pass@1={result.pass_at_1 * 100:.0f}%, consistency={result.consistency * 100:.0f}%)"
        )

    return "\n".join(lines)
