"""Tests for flaky test detection in pass_at_k module."""

import pytest

from src.eval.pass_at_k import (
    FlakyTest,
    PassAtKResult,
    RunResult,
    detect_flaky_tests,
    flaky_tests_to_dict,
    format_flaky_tests_report,
)


class TestFlakyTestDataclass:
    """Tests for the FlakyTest dataclass."""

    def test_flakiness_score_maximally_flaky(self):
        """50/50 pass/fail should have flakiness score of 1.0."""
        test = FlakyTest(
            test_id="test_50_50",
            pass_count=5,
            fail_count=5,
            total_runs=10,
            pass_rate=0.5,
        )
        assert test.flakiness_score == 1.0

    def test_flakiness_score_mostly_passing(self):
        """Mostly passing tests should have lower flakiness score."""
        test = FlakyTest(
            test_id="test_mostly_pass",
            pass_count=9,
            fail_count=1,
            total_runs=10,
            pass_rate=0.9,
        )
        # 2 * min(0.9, 0.1) = 0.2
        assert test.flakiness_score == pytest.approx(0.2)

    def test_flakiness_score_mostly_failing(self):
        """Mostly failing tests should have lower flakiness score."""
        test = FlakyTest(
            test_id="test_mostly_fail",
            pass_count=1,
            fail_count=9,
            total_runs=10,
            pass_rate=0.1,
        )
        # 2 * min(0.1, 0.9) = 0.2
        assert test.flakiness_score == pytest.approx(0.2)

    def test_flakiness_score_zero_runs(self):
        """Zero runs should return flakiness score of 0."""
        test = FlakyTest(
            test_id="test_no_runs",
            pass_count=0,
            fail_count=0,
            total_runs=0,
            pass_rate=0.0,
        )
        assert test.flakiness_score == 0.0

    def test_default_values(self):
        """Test default values for optional fields."""
        test = FlakyTest(
            test_id="test_defaults",
            pass_count=2,
            fail_count=1,
            total_runs=3,
            pass_rate=0.67,
        )
        assert test.errors == []
        assert test.avg_duration_ms == 0.0


class TestDetectFlakyTests:
    """Tests for detect_flaky_tests function."""

    def _create_pass_at_k_result(
        self, test_id: str, passes: int, failures: int, errors: list[str] | None = None
    ) -> PassAtKResult:
        """Helper to create PassAtKResult with RunResult objects."""
        runs = []
        for i in range(passes):
            runs.append(RunResult(passed=True, duration_ms=100.0))
        for i in range(failures):
            error = errors[i] if errors and i < len(errors) else None
            runs.append(RunResult(passed=False, error=error, duration_ms=150.0))

        return PassAtKResult(
            test_id=test_id,
            k=passes + failures,
            passes=passes,
            failures=failures,
            pass_at_1=0,  # Will be calculated in __post_init__
            pass_at_k=0,
            consistency=0,
            variance=0.0,
            runs=runs,
        )

    def test_detect_flaky_finds_flaky_tests(self):
        """Should detect tests that sometimes pass and sometimes fail."""
        results = [
            self._create_pass_at_k_result("flaky_test", 2, 1),
            self._create_pass_at_k_result("stable_pass", 3, 0),
            self._create_pass_at_k_result("stable_fail", 0, 3),
        ]

        flaky = detect_flaky_tests(results, k=3)

        assert len(flaky) == 1
        assert flaky[0].test_id == "flaky_test"
        assert flaky[0].pass_count == 2
        assert flaky[0].fail_count == 1

    def test_detect_flaky_empty_results(self):
        """Should return empty list for no results."""
        flaky = detect_flaky_tests([], k=3)
        assert flaky == []

    def test_detect_flaky_all_stable(self):
        """Should return empty list when all tests are stable."""
        results = [
            self._create_pass_at_k_result("stable_pass_1", 3, 0),
            self._create_pass_at_k_result("stable_pass_2", 3, 0),
            self._create_pass_at_k_result("stable_fail", 0, 3),
        ]

        flaky = detect_flaky_tests(results, k=3)
        assert len(flaky) == 0

    def test_detect_flaky_sorted_by_flakiness(self):
        """Should sort by flakiness score (most flaky first)."""
        results = [
            self._create_pass_at_k_result("slightly_flaky", 4, 1),  # 0.4 flakiness
            self._create_pass_at_k_result("very_flaky", 2, 2),  # 1.0 flakiness
            self._create_pass_at_k_result("somewhat_flaky", 3, 2),  # 0.8 flakiness
        ]

        flaky = detect_flaky_tests(results, k=5)

        assert len(flaky) == 3
        assert flaky[0].test_id == "very_flaky"  # Most flaky first
        assert flaky[1].test_id == "somewhat_flaky"
        assert flaky[2].test_id == "slightly_flaky"

    def test_detect_flaky_captures_errors(self):
        """Should capture error messages from failed runs."""
        results = [
            self._create_pass_at_k_result(
                "error_test", 1, 2, errors=["Error 1", "Error 2"]
            ),
        ]

        flaky = detect_flaky_tests(results, k=3)

        assert len(flaky) == 1
        assert len(flaky[0].errors) == 2
        assert "Error 1" in flaky[0].errors
        assert "Error 2" in flaky[0].errors

    def test_detect_flaky_calculates_avg_duration(self):
        """Should calculate average duration from runs."""
        result = self._create_pass_at_k_result("duration_test", 2, 1)
        # Passes have 100ms, failures have 150ms -> avg = (100+100+150)/3 = 116.67
        flaky = detect_flaky_tests([result], k=3)

        assert len(flaky) == 1
        assert abs(flaky[0].avg_duration_ms - 116.67) < 1


class TestFormatFlakyTestsReport:
    """Tests for format_flaky_tests_report function."""

    def test_no_flaky_tests_message(self):
        """Should show success message when no flaky tests."""
        report = format_flaky_tests_report([])
        assert "No flaky tests detected" in report
        assert "consistent behavior" in report

    def test_report_contains_test_info(self):
        """Should include test info in report."""
        flaky_tests = [
            FlakyTest(
                test_id="my_flaky_test",
                pass_count=2,
                fail_count=1,
                total_runs=3,
                pass_rate=0.67,
                errors=["Something went wrong"],
                avg_duration_ms=150.0,
            )
        ]

        report = format_flaky_tests_report(flaky_tests)

        assert "my_flaky_test" in report
        assert "2/3" in report
        assert "150ms" in report
        assert "Something went wrong" in report

    def test_report_contains_investigation_suggestions(self):
        """Should include investigation suggestions."""
        flaky_tests = [
            FlakyTest(
                test_id="test1",
                pass_count=1,
                fail_count=1,
                total_runs=2,
                pass_rate=0.5,
            )
        ]

        report = format_flaky_tests_report(flaky_tests)

        assert "Investigation Suggestions" in report
        assert "timing-dependent" in report or "race conditions" in report

    def test_report_truncates_long_errors(self):
        """Should truncate long error messages."""
        long_error = "A" * 200
        flaky_tests = [
            FlakyTest(
                test_id="test1",
                pass_count=1,
                fail_count=1,
                total_runs=2,
                pass_rate=0.5,
                errors=[long_error],
            )
        ]

        report = format_flaky_tests_report(flaky_tests)

        # Long errors should be truncated with ...
        assert "..." in report
        # Full error should not be in report
        assert long_error not in report


class TestFlakyTestsToDict:
    """Tests for flaky_tests_to_dict function."""

    def test_empty_list(self):
        """Should return empty list for empty input."""
        result = flaky_tests_to_dict([])
        assert result == []

    def test_converts_to_dict(self):
        """Should convert FlakyTest objects to dictionaries."""
        flaky_tests = [
            FlakyTest(
                test_id="test1",
                pass_count=2,
                fail_count=1,
                total_runs=3,
                pass_rate=0.67,
                errors=["Error msg"],
                avg_duration_ms=100.5,
            )
        ]

        result = flaky_tests_to_dict(flaky_tests)

        assert len(result) == 1
        assert result[0]["test_id"] == "test1"
        assert result[0]["pass_count"] == 2
        assert result[0]["fail_count"] == 1
        assert result[0]["total_runs"] == 3
        assert result[0]["pass_rate"] == 0.67
        assert result[0]["flakiness_score"] == pytest.approx(0.66, rel=0.1)
        assert result[0]["errors"] == ["Error msg"]
        assert result[0]["avg_duration_ms"] == 100.5

    def test_multiple_tests(self):
        """Should convert multiple FlakyTest objects."""
        flaky_tests = [
            FlakyTest("test1", 1, 1, 2, 0.5),
            FlakyTest("test2", 2, 1, 3, 0.67),
        ]

        result = flaky_tests_to_dict(flaky_tests)

        assert len(result) == 2
        assert result[0]["test_id"] == "test1"
        assert result[1]["test_id"] == "test2"
