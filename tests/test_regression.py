"""
Tests for regression detection in evaluation results.
"""

import pytest

from src.eval.regression import (
    RegressionWarning,
    detect_regressions,
    format_regression_warnings,
    get_category_averages,
    get_repo_pass_rates,
    regression_warnings_to_dict,
)


class TestGetCategoryAverages:
    """Tests for the get_category_averages function."""

    def test_averages_from_by_question_category(self):
        """Test averaging from by_question_category format."""
        history = [
            {
                "by_question_category": {
                    "architecture": {"pass_rate": 80.0},
                    "code_flow": {"pass_rate": 60.0},
                }
            },
            {
                "by_question_category": {
                    "architecture": {"pass_rate": 90.0},
                    "code_flow": {"pass_rate": 70.0},
                }
            },
            {
                "by_question_category": {
                    "architecture": {"pass_rate": 85.0},
                    "code_flow": {"pass_rate": 65.0},
                }
            },
        ]

        averages = get_category_averages(history, last_n=3)

        assert "architecture" in averages
        assert averages["architecture"] == pytest.approx(85.0, rel=0.01)
        assert "code_flow" in averages
        assert averages["code_flow"] == pytest.approx(65.0, rel=0.01)

    def test_averages_from_by_category_legacy(self):
        """Test averaging from legacy by_category format."""
        history = [
            {"by_category": {"cli": {"passed": 8, "failed": 2}}},  # 80%
            {"by_category": {"cli": {"passed": 9, "failed": 1}}},  # 90%
            {"by_category": {"cli": {"passed": 7, "failed": 3}}},  # 70%
        ]

        averages = get_category_averages(history, last_n=3)

        assert "repo_cli" in averages
        assert averages["repo_cli"] == pytest.approx(80.0, rel=0.01)

    def test_averages_with_fewer_runs(self):
        """Test averaging with fewer runs than last_n."""
        history = [{"by_question_category": {"debugging": {"pass_rate": 50.0}}}]

        averages = get_category_averages(history, last_n=3)

        assert "debugging" in averages
        assert averages["debugging"] == 50.0

    def test_averages_empty_history(self):
        """Test with empty history."""
        averages = get_category_averages([], last_n=3)
        assert averages == {}

    def test_averages_only_last_n(self):
        """Test that only last_n runs are considered."""
        history = [
            {"by_question_category": {"architecture": {"pass_rate": 50.0}}},  # Ignored
            {"by_question_category": {"architecture": {"pass_rate": 80.0}}},
            {"by_question_category": {"architecture": {"pass_rate": 90.0}}},
            {"by_question_category": {"architecture": {"pass_rate": 100.0}}},
        ]

        averages = get_category_averages(history, last_n=2)

        # Should only average last 2: (90 + 100) / 2 = 95
        assert averages["architecture"] == pytest.approx(95.0, rel=0.01)


class TestGetRepoPassRates:
    """Tests for the get_repo_pass_rates function."""

    def test_extract_rates_from_by_language(self):
        """Test extracting pass rates from by_language."""
        run = {
            "by_language": {
                "Python": {"passed": 8, "failed": 2},
                "Go": {"passed": 6, "failed": 0},
                "Rust": {"passed": 5, "failed": 1},
            }
        }

        rates = get_repo_pass_rates(run)

        assert rates["Python"] == pytest.approx(80.0, rel=0.01)
        assert rates["Go"] == pytest.approx(100.0, rel=0.01)
        assert rates["Rust"] == pytest.approx(83.33, rel=0.01)

    def test_handles_empty_language(self):
        """Test handling empty language data."""
        run = {"by_language": {}}
        rates = get_repo_pass_rates(run)
        assert rates == {}

    def test_handles_missing_by_language(self):
        """Test handling missing by_language key."""
        run = {}
        rates = get_repo_pass_rates(run)
        assert rates == {}


class TestDetectRegressions:
    """Tests for the detect_regressions function."""

    def test_detect_category_regression(self):
        """Test detection of category-level regression."""
        history = [
            {"by_question_category": {"architecture": {"pass_rate": 90.0}}},
            {"by_question_category": {"architecture": {"pass_rate": 85.0}}},
            {"by_question_category": {"architecture": {"pass_rate": 88.0}}},
        ]
        # Average: 87.67%, threshold 10% = must be above 78.9%
        current = {"by_question_category": {"architecture": {"pass_rate": 70.0}}}
        # Drop: 17.67 points from 87.67 = 20.15% drop

        warnings = detect_regressions(current, history, category_threshold=10.0)

        assert len(warnings) == 1
        assert warnings[0].level == "category"
        assert warnings[0].name == "architecture"
        assert warnings[0].current_value == 70.0

    def test_no_regression_within_threshold(self):
        """Test no warning when drop is within threshold."""
        history = [
            {"by_question_category": {"code_flow": {"pass_rate": 80.0}}},
            {"by_question_category": {"code_flow": {"pass_rate": 82.0}}},
            {"by_question_category": {"code_flow": {"pass_rate": 78.0}}},
        ]
        # Average: 80%, 10% threshold = 72%
        current = {"by_question_category": {"code_flow": {"pass_rate": 75.0}}}
        # Drop: 5 points from 80 = 6.25% drop (within threshold)

        warnings = detect_regressions(current, history, category_threshold=10.0)

        assert len(warnings) == 0

    def test_detect_repo_regression(self):
        """Test detection of repo/language-level regression."""
        history = [
            {"by_language": {"Python": {"passed": 10, "failed": 0}}}  # 100%
        ]
        current = {"by_language": {"Python": {"passed": 7, "failed": 3}}}  # 70%
        # Drop: 30 points from 100 = 30% drop

        warnings = detect_regressions(current, history, repo_threshold=20.0)

        assert len(warnings) == 1
        assert warnings[0].level == "repo"
        assert warnings[0].name == "Python"
        assert warnings[0].drop_percent == pytest.approx(30.0, rel=0.01)

    def test_multiple_regressions(self):
        """Test detection of multiple regressions."""
        history = [
            {
                "by_question_category": {
                    "architecture": {"pass_rate": 90.0},
                    "code_flow": {"pass_rate": 80.0},
                },
                "by_language": {"Go": {"passed": 10, "failed": 0}},
            }
        ]
        current = {
            "by_question_category": {
                "architecture": {"pass_rate": 50.0},  # Big drop
                "code_flow": {"pass_rate": 40.0},  # Big drop
            },
            "by_language": {"Go": {"passed": 5, "failed": 5}},  # 50% = 50% drop
        }

        warnings = detect_regressions(current, history)

        # Should detect all 3 regressions
        assert len(warnings) == 3
        # Should be sorted by severity (highest drop first)
        assert warnings[0].drop_percent >= warnings[1].drop_percent
        assert warnings[1].drop_percent >= warnings[2].drop_percent

    def test_empty_history(self):
        """Test with empty history."""
        current = {"by_question_category": {"architecture": {"pass_rate": 50.0}}}
        warnings = detect_regressions(current, [])
        assert len(warnings) == 0

    def test_new_category_no_warning(self):
        """Test that new categories don't trigger warnings."""
        history = [{"by_question_category": {"architecture": {"pass_rate": 90.0}}}]
        current = {
            "by_question_category": {
                "architecture": {"pass_rate": 85.0},
                "new_category": {"pass_rate": 50.0},  # New, not in history
            }
        }

        warnings = detect_regressions(current, history)

        # No warnings - architecture within threshold, new_category has no baseline
        assert len(warnings) == 0


class TestFormatRegressionWarnings:
    """Tests for the format_regression_warnings function."""

    def test_format_no_warnings(self):
        """Test formatting when no regressions detected."""
        result = format_regression_warnings([])
        assert "No regressions detected" in result
        assert "✅" in result

    def test_format_with_warnings(self):
        """Test formatting regression warnings."""
        warnings = [
            RegressionWarning(
                level="category",
                name="architecture",
                current_value=60.0,
                baseline_value=90.0,
                drop_percent=33.3,
                message="Category 'architecture' dropped 33.3%",
            ),
            RegressionWarning(
                level="repo",
                name="Python",
                current_value=70.0,
                baseline_value=100.0,
                drop_percent=30.0,
                message="Language 'Python' dropped 30.0%",
            ),
        ]

        result = format_regression_warnings(warnings)

        assert "REGRESSION WARNINGS DETECTED" in result
        assert "Category Regressions" in result
        assert "Repo/Language Regressions" in result
        assert "architecture" in result
        assert "Python" in result
        assert "2 regression(s) detected" in result


class TestRegressionWarningsToDict:
    """Tests for the regression_warnings_to_dict function."""

    def test_convert_to_dict(self):
        """Test conversion of warnings to dict format."""
        warnings = [
            RegressionWarning(
                level="category",
                name="code_flow",
                current_value=55.0,
                baseline_value=85.0,
                drop_percent=35.3,
                message="Code flow dropped",
            )
        ]

        result = regression_warnings_to_dict(warnings)

        assert len(result) == 1
        assert result[0]["level"] == "category"
        assert result[0]["name"] == "code_flow"
        assert result[0]["current_value"] == 55.0
        assert result[0]["baseline_value"] == 85.0
        assert result[0]["drop_percent"] == 35.3
        assert result[0]["message"] == "Code flow dropped"

    def test_convert_empty_list(self):
        """Test conversion of empty list."""
        result = regression_warnings_to_dict([])
        assert result == []
