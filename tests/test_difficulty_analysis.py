"""
Tests for question difficulty analysis functionality.
"""

from src.eval.questions import (
    DIFFICULTY_THRESHOLDS,
    DifficultyMismatch,
    QuestionTemplate,
    analyze_difficulty_mismatches,
    compute_difficulty_from_results,
    difficulty_analysis_to_dict,
    format_difficulty_analysis,
)


class TestQuestionTemplateActualDifficulty:
    """Tests for the QuestionTemplate dataclass with actual_difficulty field."""

    def test_actual_difficulty_default_none(self):
        """Test that actual_difficulty defaults to None."""
        template = QuestionTemplate(
            id="test_template",
            category="architecture",
            template="Test question",
            difficulty="medium",
            expected_tools=["read_file"],
            min_citations=2,
        )
        assert template.actual_difficulty is None

    def test_actual_difficulty_can_be_set(self):
        """Test that actual_difficulty can be set."""
        template = QuestionTemplate(
            id="test_template",
            category="architecture",
            template="Test question",
            difficulty="medium",
            expected_tools=["read_file"],
            min_citations=2,
            actual_difficulty="hard",
        )
        assert template.actual_difficulty == "hard"


class TestDifficultyMismatch:
    """Tests for the DifficultyMismatch dataclass."""

    def test_mismatch_str_harder_than_expected(self):
        """Test string representation for harder than expected."""
        mismatch = DifficultyMismatch(
            template_id="flow_request",
            expected_difficulty="medium",
            actual_difficulty="hard",
            pass_rate=45.0,
            total_runs=10,
            direction="harder_than_expected",
        )
        result = str(mismatch)
        assert "flow_request" in result
        assert "medium" in result
        assert "hard" in result
        assert "45.0%" in result
        assert "n=10" in result
        assert "⬆️" in result

    def test_mismatch_str_easier_than_expected(self):
        """Test string representation for easier than expected."""
        mismatch = DifficultyMismatch(
            template_id="arch_entry",
            expected_difficulty="hard",
            actual_difficulty="easy",
            pass_rate=95.0,
            total_runs=5,
            direction="easier_than_expected",
        )
        result = str(mismatch)
        assert "arch_entry" in result
        assert "hard" in result
        assert "easy" in result
        assert "95.0%" in result
        assert "⬇️" in result


class TestComputeDifficultyFromResults:
    """Tests for the compute_difficulty_from_results function."""

    def test_easy_difficulty(self):
        """Test that high pass rate returns 'easy'."""
        assert compute_difficulty_from_results(95.0) == "easy"
        assert compute_difficulty_from_results(91.0) == "easy"
        assert compute_difficulty_from_results(100.0) == "easy"

    def test_medium_difficulty(self):
        """Test that medium pass rate returns 'medium'."""
        assert compute_difficulty_from_results(90.0) == "medium"
        assert compute_difficulty_from_results(80.0) == "medium"
        assert compute_difficulty_from_results(70.0) == "medium"

    def test_hard_difficulty(self):
        """Test that low pass rate returns 'hard'."""
        assert compute_difficulty_from_results(69.9) == "hard"
        assert compute_difficulty_from_results(50.0) == "hard"
        assert compute_difficulty_from_results(0.0) == "hard"

    def test_boundary_values(self):
        """Test boundary values between difficulty levels."""
        # At the boundary of easy/medium
        assert compute_difficulty_from_results(90.0) == "medium"
        assert compute_difficulty_from_results(90.1) == "easy"

        # At the boundary of medium/hard
        assert compute_difficulty_from_results(70.0) == "medium"
        assert compute_difficulty_from_results(69.9) == "hard"


class TestAnalyzeDifficultyMismatches:
    """Tests for the analyze_difficulty_mismatches function."""

    def test_no_mismatches(self):
        """Test when actual difficulty matches expected."""
        results = [
            {
                "repo": "flask",
                "diverse_questions": {
                    "questions": [
                        {"id": "arch_entry", "difficulty": "easy", "passed": True},
                        {"id": "arch_entry", "difficulty": "easy", "passed": True},
                        {"id": "arch_entry", "difficulty": "easy", "passed": True},
                        {"id": "arch_entry", "difficulty": "easy", "passed": True},
                        {
                            "id": "arch_entry",
                            "difficulty": "easy",
                            "passed": True,
                        },  # 100% pass = easy
                    ],
                },
            },
        ]

        stats, mismatches = analyze_difficulty_mismatches(results)

        assert "arch_entry" in stats
        assert stats["arch_entry"]["pass_rate"] == 100.0
        assert stats["arch_entry"]["actual_difficulty"] == "easy"
        assert len(mismatches) == 0

    def test_harder_than_expected_mismatch(self):
        """Test detection of questions that are harder than expected."""
        results = [
            {
                "repo": "flask",
                "diverse_questions": {
                    "questions": [
                        {"id": "flow_init", "difficulty": "easy", "passed": False},
                        {"id": "flow_init", "difficulty": "easy", "passed": False},
                        {"id": "flow_init", "difficulty": "easy", "passed": True},
                        {"id": "flow_init", "difficulty": "easy", "passed": False},
                        {
                            "id": "flow_init",
                            "difficulty": "easy",
                            "passed": False,
                        },  # 20% pass
                    ],
                },
            },
        ]

        stats, mismatches = analyze_difficulty_mismatches(results)

        assert len(mismatches) == 1
        assert mismatches[0].template_id == "flow_init"
        assert mismatches[0].expected_difficulty == "easy"
        assert mismatches[0].actual_difficulty == "hard"
        assert mismatches[0].direction == "harder_than_expected"

    def test_easier_than_expected_mismatch(self):
        """Test detection of questions that are easier than expected."""
        results = [
            {
                "repo": "flask",
                "diverse_questions": {
                    "questions": [
                        {"id": "specific_core", "difficulty": "hard", "passed": True},
                        {"id": "specific_core", "difficulty": "hard", "passed": True},
                        {"id": "specific_core", "difficulty": "hard", "passed": True},
                        {"id": "specific_core", "difficulty": "hard", "passed": True},
                        {
                            "id": "specific_core",
                            "difficulty": "hard",
                            "passed": True,
                        },  # 100% pass
                    ],
                },
            },
        ]

        stats, mismatches = analyze_difficulty_mismatches(results)

        assert len(mismatches) == 1
        assert mismatches[0].template_id == "specific_core"
        assert mismatches[0].expected_difficulty == "hard"
        assert mismatches[0].actual_difficulty == "easy"
        assert mismatches[0].direction == "easier_than_expected"

    def test_multiple_templates(self):
        """Test analysis across multiple templates."""
        results = [
            {
                "repo": "flask",
                "diverse_questions": {
                    "questions": [
                        {"id": "arch_overview", "difficulty": "medium", "passed": True},
                        {"id": "arch_overview", "difficulty": "medium", "passed": True},
                        {
                            "id": "flow_request",
                            "difficulty": "hard",
                            "passed": False,
                        },
                        {"id": "flow_request", "difficulty": "hard", "passed": False},
                    ],
                },
            },
            {
                "repo": "express",
                "diverse_questions": {
                    "questions": [
                        {"id": "arch_overview", "difficulty": "medium", "passed": True},
                        {
                            "id": "arch_overview",
                            "difficulty": "medium",
                            "passed": False,
                        },
                        {
                            "id": "flow_request",
                            "difficulty": "hard",
                            "passed": False,
                        },
                        {"id": "flow_request", "difficulty": "hard", "passed": False},
                    ],
                },
            },
        ]

        stats, mismatches = analyze_difficulty_mismatches(results)

        # arch_overview: 3/4 = 75% = medium (matches expected)
        # flow_request: 0/4 = 0% = hard (matches expected)
        assert "arch_overview" in stats
        assert "flow_request" in stats
        assert stats["arch_overview"]["pass_rate"] == 75.0
        assert stats["arch_overview"]["actual_difficulty"] == "medium"
        assert stats["flow_request"]["pass_rate"] == 0.0
        assert stats["flow_request"]["actual_difficulty"] == "hard"
        assert len(mismatches) == 0

    def test_empty_results(self):
        """Test with empty results."""
        stats, mismatches = analyze_difficulty_mismatches([])
        assert stats == {}
        assert mismatches == []

    def test_no_diverse_questions(self):
        """Test with results that have no diverse questions."""
        results = [
            {
                "repo": "flask",
                "tests": {"overview": {"passed": True}},
            },
        ]

        stats, mismatches = analyze_difficulty_mismatches(results)
        assert stats == {}
        assert mismatches == []

    def test_aggregates_across_repos(self):
        """Test that stats aggregate across multiple repos."""
        results = [
            {
                "repo": "flask",
                "diverse_questions": {
                    "questions": [
                        {"id": "dep_external", "difficulty": "easy", "passed": True},
                    ],
                },
            },
            {
                "repo": "express",
                "diverse_questions": {
                    "questions": [
                        {"id": "dep_external", "difficulty": "easy", "passed": True},
                    ],
                },
            },
            {
                "repo": "gin",
                "diverse_questions": {
                    "questions": [
                        {"id": "dep_external", "difficulty": "easy", "passed": True},
                    ],
                },
            },
        ]

        stats, mismatches = analyze_difficulty_mismatches(results)

        assert stats["dep_external"]["total"] == 3
        assert stats["dep_external"]["pass_count"] == 3
        assert stats["dep_external"]["pass_rate"] == 100.0


class TestFormatDifficultyAnalysis:
    """Tests for the format_difficulty_analysis function."""

    def test_format_with_mismatches(self):
        """Test formatting with mismatches present."""
        stats = {
            "flow_init": {
                "expected_difficulty": "easy",
                "actual_difficulty": "hard",
                "pass_rate": 30.0,
                "pass_count": 3,
                "total": 10,
            },
        }
        mismatches = [
            DifficultyMismatch(
                template_id="flow_init",
                expected_difficulty="easy",
                actual_difficulty="hard",
                pass_rate=30.0,
                total_runs=10,
                direction="harder_than_expected",
            ),
        ]

        result = format_difficulty_analysis(stats, mismatches)

        assert "DIFFICULTY ANALYSIS" in result
        assert "Difficulty Mismatches" in result
        assert "flow_init" in result

    def test_format_without_mismatches(self):
        """Test formatting when no mismatches exist."""
        stats = {
            "arch_entry": {
                "expected_difficulty": "easy",
                "actual_difficulty": "easy",
                "pass_rate": 95.0,
                "pass_count": 19,
                "total": 20,
            },
        }
        mismatches = []

        result = format_difficulty_analysis(stats, mismatches)

        assert "DIFFICULTY ANALYSIS" in result
        assert "No difficulty mismatches detected" in result

    def test_format_empty_stats(self):
        """Test formatting with no data."""
        result = format_difficulty_analysis({}, [])
        assert "DIFFICULTY ANALYSIS" in result
        assert "No question data available" in result


class TestDifficultyAnalysisToDict:
    """Tests for the difficulty_analysis_to_dict function."""

    def test_conversion_with_mismatches(self):
        """Test conversion to dict with mismatches."""
        stats = {
            "flow_request": {
                "expected_difficulty": "hard",
                "actual_difficulty": "hard",
                "pass_rate": 40.0,
                "pass_count": 4,
                "total": 10,
            },
            "arch_entry": {
                "expected_difficulty": "easy",
                "actual_difficulty": "hard",
                "pass_rate": 20.0,
                "pass_count": 2,
                "total": 10,
            },
        }
        mismatches = [
            DifficultyMismatch(
                template_id="arch_entry",
                expected_difficulty="easy",
                actual_difficulty="hard",
                pass_rate=20.0,
                total_runs=10,
                direction="harder_than_expected",
            ),
        ]

        result = difficulty_analysis_to_dict(stats, mismatches)

        assert "template_stats" in result
        assert "mismatches" in result
        assert "summary" in result

        assert result["summary"]["total_templates"] == 2
        assert result["summary"]["total_mismatches"] == 1
        assert result["summary"]["harder_than_expected"] == 1
        assert result["summary"]["easier_than_expected"] == 0

        assert len(result["mismatches"]) == 1
        assert result["mismatches"][0]["template_id"] == "arch_entry"

    def test_conversion_empty(self):
        """Test conversion with empty data."""
        result = difficulty_analysis_to_dict({}, [])

        assert result["template_stats"] == {}
        assert result["mismatches"] == []
        assert result["summary"]["total_templates"] == 0
        assert result["summary"]["total_mismatches"] == 0


class TestDifficultyThresholds:
    """Tests for the DIFFICULTY_THRESHOLDS constant."""

    def test_thresholds_exist(self):
        """Test that all difficulty thresholds are defined."""
        assert "easy" in DIFFICULTY_THRESHOLDS
        assert "medium" in DIFFICULTY_THRESHOLDS
        assert "hard" in DIFFICULTY_THRESHOLDS

    def test_thresholds_are_ordered(self):
        """Test that thresholds are in descending order."""
        assert DIFFICULTY_THRESHOLDS["easy"] > DIFFICULTY_THRESHOLDS["medium"]
        assert DIFFICULTY_THRESHOLDS["medium"] > DIFFICULTY_THRESHOLDS["hard"]
