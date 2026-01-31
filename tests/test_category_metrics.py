"""
Tests for category-based metrics tracking.
"""

import pytest

from src.eval.category_metrics import (
    TRACKED_CATEGORIES,
    CategoryMetrics,
    aggregate_by_category,
    format_category_metrics_table,
    identify_problem_categories,
    metrics_to_dict,
)


class TestCategoryMetrics:
    """Tests for the CategoryMetrics dataclass."""

    def test_pass_rate_calculation(self):
        """Test pass rate is calculated correctly."""
        metrics = CategoryMetrics(
            category="architecture",
            total=10,
            passed=8,
            failed=2,
        )
        assert metrics.pass_rate == 80.0

    def test_pass_rate_zero_total(self):
        """Test pass rate returns 0 when total is 0."""
        metrics = CategoryMetrics(category="architecture")
        assert metrics.pass_rate == 0.0

    def test_avg_citations_calculation(self):
        """Test average citations is calculated correctly."""
        metrics = CategoryMetrics(
            category="code_flow",
            total=5,
            total_citations=20,
        )
        assert metrics.avg_citations == 4.0

    def test_avg_citations_zero_total(self):
        """Test avg citations returns 0 when total is 0."""
        metrics = CategoryMetrics(category="code_flow")
        assert metrics.avg_citations == 0.0

    def test_citation_accuracy_calculation(self):
        """Test citation accuracy is calculated correctly."""
        metrics = CategoryMetrics(
            category="dependencies",
            total_citations=10,
            verified_citations=9,
        )
        assert metrics.citation_accuracy == 90.0

    def test_citation_accuracy_zero_citations(self):
        """Test citation accuracy returns 0 when no citations."""
        metrics = CategoryMetrics(category="dependencies")
        assert metrics.citation_accuracy == 0.0


class TestAggregateByCategory:
    """Tests for the aggregate_by_category function."""

    def test_aggregate_standard_tests(self):
        """Test aggregation of standard test results."""
        results = [
            {
                "repo": "flask",
                "tests": {
                    "overview": {
                        "passed": True,
                        "citations": 5,
                        "verified_citations": 4,
                    },
                    "deep_dive": {
                        "passed": False,
                        "citations": 3,
                        "verified_citations": 2,
                    },
                    "language_detection": {
                        "passed": True,
                        "citations": 0,
                        "verified_citations": 0,
                    },
                },
            },
        ]

        category_metrics = aggregate_by_category(results)

        # Overview should map to "overview" category
        assert "overview" in category_metrics
        assert category_metrics["overview"].total == 1
        assert category_metrics["overview"].passed == 1
        assert category_metrics["overview"].total_citations == 5

        # Deep dive should map to "architecture" category
        assert "architecture" in category_metrics
        assert category_metrics["architecture"].total == 1
        assert category_metrics["architecture"].passed == 0
        assert category_metrics["architecture"].failed == 1

        # Language detection
        assert "language_detection" in category_metrics
        assert category_metrics["language_detection"].passed == 1

    def test_aggregate_diverse_questions(self):
        """Test aggregation of diverse question results."""
        results = [
            {
                "repo": "flask",
                "tests": {},
                "diverse_questions": {
                    "questions": [
                        {
                            "category": "architecture",
                            "passed": True,
                            "citations": 4,
                            "verified_citations": 4,
                        },
                        {
                            "category": "code_flow",
                            "passed": False,
                            "citations": 2,
                            "verified_citations": 1,
                        },
                        {
                            "category": "code_flow",
                            "passed": True,
                            "citations": 5,
                            "verified_citations": 5,
                        },
                    ],
                },
            },
        ]

        category_metrics = aggregate_by_category(results)

        assert "architecture" in category_metrics
        assert category_metrics["architecture"].total == 1
        assert category_metrics["architecture"].passed == 1

        assert "code_flow" in category_metrics
        assert category_metrics["code_flow"].total == 2
        assert category_metrics["code_flow"].passed == 1
        assert category_metrics["code_flow"].failed == 1
        assert category_metrics["code_flow"].total_citations == 7

    def test_aggregate_multiple_repos(self):
        """Test aggregation across multiple repositories."""
        results = [
            {
                "repo": "flask",
                "tests": {
                    "overview": {
                        "passed": True,
                        "citations": 3,
                        "verified_citations": 3,
                    },
                },
            },
            {
                "repo": "express",
                "tests": {
                    "overview": {
                        "passed": False,
                        "citations": 2,
                        "verified_citations": 1,
                    },
                },
            },
            {
                "repo": "gin",
                "tests": {
                    "overview": {
                        "passed": True,
                        "citations": 4,
                        "verified_citations": 4,
                    },
                },
            },
        ]

        category_metrics = aggregate_by_category(results)

        assert category_metrics["overview"].total == 3
        assert category_metrics["overview"].passed == 2
        assert category_metrics["overview"].failed == 1
        assert category_metrics["overview"].total_citations == 9
        assert category_metrics["overview"].pass_rate == pytest.approx(66.67, rel=0.01)

    def test_aggregate_empty_results(self):
        """Test aggregation with empty results."""
        category_metrics = aggregate_by_category([])
        assert category_metrics == {}

    def test_aggregate_skips_non_dict_tests(self):
        """Test that non-dict test values are skipped."""
        results = [
            {
                "repo": "test",
                "tests": {
                    "overview": {
                        "passed": True,
                        "citations": 1,
                        "verified_citations": 1,
                    },
                    "error_test": "some error string",  # Not a dict
                },
            },
        ]

        category_metrics = aggregate_by_category(results)
        # Should only have overview, not error_test
        assert "overview" in category_metrics
        assert category_metrics["overview"].total == 1


class TestFormatCategoryMetricsTable:
    """Tests for the format_category_metrics_table function."""

    def test_format_table_output(self):
        """Test that table formatting produces expected structure."""
        metrics = {
            "architecture": CategoryMetrics(
                category="architecture",
                total=10,
                passed=8,
                failed=2,
                total_citations=40,
            ),
            "code_flow": CategoryMetrics(
                category="code_flow",
                total=5,
                passed=2,
                failed=3,
                total_citations=15,
            ),
        }

        table = format_category_metrics_table(metrics)

        # Check header
        assert "PER-CATEGORY METRICS" in table
        assert "Category" in table
        assert "Pass Rate" in table

        # Check categories appear
        assert "architecture" in table
        assert "code_flow" in table

        # Check indicators (code_flow should be red with 40% pass rate)
        assert "🔴" in table  # code_flow at 40%
        assert "🟢" in table  # architecture at 80%

    def test_format_table_empty(self):
        """Test formatting with empty metrics."""
        table = format_category_metrics_table({})
        assert "PER-CATEGORY METRICS" in table


class TestIdentifyProblemCategories:
    """Tests for the identify_problem_categories function."""

    def test_identify_below_threshold(self):
        """Test identification of categories below threshold."""
        metrics = {
            "architecture": CategoryMetrics(
                category="architecture", total=10, passed=8, failed=2
            ),
            "code_flow": CategoryMetrics(
                category="code_flow", total=10, passed=5, failed=5
            ),
            "debugging": CategoryMetrics(
                category="debugging", total=10, passed=3, failed=7
            ),
        }

        problems = identify_problem_categories(metrics, threshold=70.0)

        assert len(problems) == 2
        # Should be sorted by pass rate ascending
        assert problems[0][0] == "debugging"  # 30%
        assert problems[0][1] == 30.0
        assert problems[1][0] == "code_flow"  # 50%
        assert problems[1][1] == 50.0

    def test_identify_no_problems(self):
        """Test when all categories are above threshold."""
        metrics = {
            "architecture": CategoryMetrics(
                category="architecture", total=10, passed=9, failed=1
            ),
        }

        problems = identify_problem_categories(metrics, threshold=70.0)
        assert problems == []

    def test_identify_skips_empty_categories(self):
        """Test that categories with no tests are skipped."""
        metrics = {
            "architecture": CategoryMetrics(
                category="architecture", total=0, passed=0, failed=0
            ),
        }

        problems = identify_problem_categories(metrics, threshold=70.0)
        assert problems == []


class TestMetricsToDict:
    """Tests for the metrics_to_dict function."""

    def test_conversion_to_dict(self):
        """Test conversion of CategoryMetrics to dict."""
        metrics = {
            "architecture": CategoryMetrics(
                category="architecture",
                total=10,
                passed=8,
                failed=2,
                total_citations=30,
                verified_citations=28,
            ),
        }

        result = metrics_to_dict(metrics)

        assert "architecture" in result
        arch = result["architecture"]
        assert arch["category"] == "architecture"
        assert arch["total"] == 10
        assert arch["passed"] == 8
        assert arch["failed"] == 2
        assert arch["pass_rate"] == 80.0
        assert arch["total_citations"] == 30
        assert arch["verified_citations"] == 28
        assert arch["avg_citations"] == 3.0
        assert arch["citation_accuracy"] == pytest.approx(93.33, rel=0.01)


class TestTrackedCategories:
    """Tests for the TRACKED_CATEGORIES constant."""

    def test_required_categories_present(self):
        """Test that all required categories are in TRACKED_CATEGORIES."""
        required = [
            "architecture",
            "dependencies",
            "code_flow",
            "debugging",
            "specific_file",
            "overview",
            "language_detection",
        ]
        for cat in required:
            assert cat in TRACKED_CATEGORIES, f"Missing category: {cat}"
