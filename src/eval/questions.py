"""
Question templates for diverse evaluation testing.
Each template is parameterized by repo metadata (language, category, etc.)
"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class QuestionTemplate:
    """A parameterized question template for evaluation."""

    id: str
    category: str  # architecture, dependencies, code_flow, debugging, specific_file
    template: str  # Question with {placeholders}
    difficulty: str  # easy, medium, hard
    expected_tools: list[str]  # Tools that should be used
    min_citations: int  # Minimum citations expected
    grader: Callable[[str, dict], tuple[bool, str]] | None = None  # Custom grader
    actual_difficulty: str | None = None  # Computed from eval results


@dataclass
class DifficultyMismatch:
    """Represents a mismatch between expected and actual question difficulty."""

    template_id: str
    expected_difficulty: str
    actual_difficulty: str
    pass_rate: float
    total_runs: int
    direction: str  # "harder_than_expected" or "easier_than_expected"

    def __str__(self) -> str:
        """Format the mismatch for display."""
        if self.direction == "harder_than_expected":
            arrow = "→"
            indicator = "⬆️"
        else:
            arrow = "→"
            indicator = "⬇️"
        return (
            f"{indicator} {self.template_id}: expected '{self.expected_difficulty}' "
            f"{arrow} actual '{self.actual_difficulty}' "
            f"(pass rate: {self.pass_rate:.1f}%, n={self.total_runs})"
        )


# Difficulty thresholds based on pass rate
DIFFICULTY_THRESHOLDS = {
    "easy": 90.0,  # > 90% pass rate = easy
    "medium": 70.0,  # 70-90% pass rate = medium
    "hard": 0.0,  # < 70% pass rate = hard
}


def compute_difficulty_from_results(pass_rate: float) -> str:
    """
    Compute the actual difficulty based on pass rate.

    Args:
        pass_rate: The percentage of test runs that passed (0-100)

    Returns:
        Difficulty level: "easy", "medium", or "hard"
    """
    if pass_rate > DIFFICULTY_THRESHOLDS["easy"]:
        return "easy"
    elif pass_rate >= DIFFICULTY_THRESHOLDS["medium"]:
        return "medium"
    else:
        return "hard"


def analyze_difficulty_mismatches(
    results: list[dict],
) -> tuple[dict[str, dict], list[DifficultyMismatch]]:
    """
    Analyze eval results to find difficulty mismatches.

    Args:
        results: List of eval results from run_multi_eval

    Returns:
        Tuple of:
        - Dict mapping template_id to {pass_count, total, pass_rate, actual_difficulty}
        - List of DifficultyMismatch objects for questions where expected != actual
    """
    # Aggregate results by template_id
    template_stats: dict[str, dict] = {}

    for result in results:
        # Check diverse questions
        diverse = result.get("diverse_questions", {})
        questions = diverse.get("questions", [])

        for q in questions:
            template_id = q.get("id", "")
            if not template_id:
                continue

            if template_id not in template_stats:
                template_stats[template_id] = {
                    "expected_difficulty": q.get("difficulty", "medium"),
                    "pass_count": 0,
                    "total": 0,
                }

            template_stats[template_id]["total"] += 1
            if q.get("passed", False):
                template_stats[template_id]["pass_count"] += 1

    # Calculate pass rates and actual difficulties
    for template_id, stats in template_stats.items():
        if stats["total"] > 0:
            stats["pass_rate"] = (stats["pass_count"] / stats["total"]) * 100
        else:
            stats["pass_rate"] = 0.0
        stats["actual_difficulty"] = compute_difficulty_from_results(stats["pass_rate"])

    # Find mismatches
    mismatches: list[DifficultyMismatch] = []

    for template_id, stats in template_stats.items():
        expected = stats["expected_difficulty"]
        actual = stats["actual_difficulty"]

        if expected != actual:
            # Determine direction
            difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
            if difficulty_order.get(actual, 1) > difficulty_order.get(expected, 1):
                direction = "harder_than_expected"
            else:
                direction = "easier_than_expected"

            mismatches.append(
                DifficultyMismatch(
                    template_id=template_id,
                    expected_difficulty=expected,
                    actual_difficulty=actual,
                    pass_rate=stats["pass_rate"],
                    total_runs=stats["total"],
                    direction=direction,
                )
            )

    # Sort mismatches by severity (harder_than_expected first, then by pass rate diff)
    mismatches.sort(
        key=lambda m: (
            0 if m.direction == "harder_than_expected" else 1,
            -abs(_difficulty_to_expected_rate(m.expected_difficulty) - m.pass_rate),
        )
    )

    return template_stats, mismatches


def _difficulty_to_expected_rate(difficulty: str) -> float:
    """Convert difficulty to expected pass rate midpoint."""
    if difficulty == "easy":
        return 95.0
    elif difficulty == "medium":
        return 80.0
    else:  # hard
        return 50.0


def format_difficulty_analysis(
    template_stats: dict[str, dict],
    mismatches: list[DifficultyMismatch],
) -> str:
    """
    Format difficulty analysis for display.

    Args:
        template_stats: Dict mapping template_id to stats
        mismatches: List of difficulty mismatches

    Returns:
        Formatted string for console output
    """
    lines = [
        "",
        "┌" + "─" * 58 + "┐",
        "│" + " DIFFICULTY ANALYSIS".center(58) + "│",
        "├" + "─" * 58 + "┤",
    ]

    if not template_stats:
        lines.append("│" + "  No question data available".ljust(58) + "│")
    else:
        # Summary by difficulty level
        by_difficulty: dict[str, list[float]] = {"easy": [], "medium": [], "hard": []}
        for stats in template_stats.values():
            expected = stats.get("expected_difficulty", "medium")
            if expected in by_difficulty:
                by_difficulty[expected].append(stats["pass_rate"])

        lines.append("│" + "  Expected Difficulty Summary:".ljust(58) + "│")
        for diff in ["easy", "medium", "hard"]:
            rates = by_difficulty[diff]
            if rates:
                avg_rate = sum(rates) / len(rates)
                indicator = "🟢" if avg_rate >= 70 else "🟡" if avg_rate >= 50 else "🔴"
                lines.append(
                    "│"
                    + f"    {indicator} {diff.capitalize()}: {avg_rate:.1f}% avg pass rate (n={len(rates)})".ljust(
                        58
                    )
                    + "│"
                )

    lines.append("├" + "─" * 58 + "┤")

    if mismatches:
        lines.append("│" + "  ⚠️  Difficulty Mismatches:".ljust(58) + "│")
        for mismatch in mismatches:
            lines.append("│" + f"    {mismatch}".ljust(58) + "│")
    else:
        lines.append("│" + "  ✅ No difficulty mismatches detected".ljust(58) + "│")

    lines.append("└" + "─" * 58 + "┘")

    return "\n".join(lines)


def difficulty_analysis_to_dict(
    template_stats: dict[str, dict],
    mismatches: list[DifficultyMismatch],
) -> dict:
    """
    Convert difficulty analysis to dict for JSON serialization.

    Args:
        template_stats: Dict mapping template_id to stats
        mismatches: List of difficulty mismatches

    Returns:
        Dict suitable for JSON serialization
    """
    return {
        "template_stats": template_stats,
        "mismatches": [
            {
                "template_id": m.template_id,
                "expected_difficulty": m.expected_difficulty,
                "actual_difficulty": m.actual_difficulty,
                "pass_rate": m.pass_rate,
                "total_runs": m.total_runs,
                "direction": m.direction,
            }
            for m in mismatches
        ],
        "summary": {
            "total_templates": len(template_stats),
            "total_mismatches": len(mismatches),
            "harder_than_expected": sum(
                1 for m in mismatches if m.direction == "harder_than_expected"
            ),
            "easier_than_expected": sum(
                1 for m in mismatches if m.direction == "easier_than_expected"
            ),
        },
    }


# Question templates organized by category
QUESTION_TEMPLATES = [
    # =========================================================================
    # IDENTITY QUESTIONS (Anti-Hallucination)
    # =========================================================================
    QuestionTemplate(
        id="identity_check",
        category="identity",
        template="What is the name and purpose of this project? Cite the package metadata file.",
        difficulty="easy",
        expected_tools=["read_file"],
        min_citations=1,
    ),
    QuestionTemplate(
        id="identity_type",
        category="identity",
        template="Is this a CLI tool, web framework, or library? Cite the specific code that shows this.",
        difficulty="easy",
        expected_tools=["read_file", "find_entry_points"],
        min_citations=1,
    ),
    QuestionTemplate(
        id="identity_not_confused",
        category="identity",
        template="Based on the package metadata and source code, confirm this project's name and describe what it does.",
        difficulty="easy",
        expected_tools=["read_file", "list_directory_structure"],
        min_citations=1,
    ),
    # =========================================================================
    # ARCHITECTURE QUESTIONS
    # =========================================================================
    QuestionTemplate(
        id="arch_overview",
        category="architecture",
        template="What is the overall architecture of this {language} project? Describe the main components and how they interact.",
        difficulty="medium",
        expected_tools=["list_directory_structure", "read_file", "get_important_files"],
        min_citations=3,
    ),
    QuestionTemplate(
        id="arch_patterns",
        category="architecture",
        template="What design patterns are used in this codebase? Cite specific files where you see these patterns.",
        difficulty="hard",
        expected_tools=["read_file", "search_code"],
        min_citations=2,
    ),
    QuestionTemplate(
        id="arch_entry",
        category="architecture",
        template="How does the main entry point work in this {language} project?",
        difficulty="easy",
        expected_tools=["find_entry_points", "read_file"],
        min_citations=2,
    ),
    QuestionTemplate(
        id="arch_modules",
        category="architecture",
        template="What are the main modules or packages in this project and what is each one responsible for?",
        difficulty="medium",
        expected_tools=["list_directory_structure", "read_file"],
        min_citations=3,
    ),
    # =========================================================================
    # DEPENDENCY QUESTIONS
    # =========================================================================
    QuestionTemplate(
        id="dep_external",
        category="dependencies",
        template="What are the key external dependencies of this project and what is each used for?",
        difficulty="easy",
        expected_tools=["analyze_dependencies", "read_file"],
        min_citations=2,
    ),
    QuestionTemplate(
        id="dep_internal",
        category="dependencies",
        template="How do the internal modules depend on each other? Describe the import relationships.",
        difficulty="medium",
        expected_tools=["get_imports", "read_file"],
        min_citations=2,
    ),
    QuestionTemplate(
        id="dep_specific",
        category="dependencies",
        template="What library or module handles {feature_area} in this codebase? Show me where it's used.",
        difficulty="medium",
        expected_tools=["search_code", "read_file"],
        min_citations=2,
    ),
    # =========================================================================
    # CODE FLOW QUESTIONS
    # =========================================================================
    QuestionTemplate(
        id="flow_request",
        category="code_flow",
        template="Trace what happens when a request/call comes into this {category}. What functions are called in what order?",
        difficulty="hard",
        expected_tools=["find_entry_points", "read_file", "get_imports"],
        min_citations=4,
    ),
    QuestionTemplate(
        id="flow_init",
        category="code_flow",
        template="What happens during initialization/startup of this project? Walk through the sequence.",
        difficulty="medium",
        expected_tools=["find_entry_points", "read_file", "get_imports"],
        min_citations=4,
    ),
    QuestionTemplate(
        id="flow_error",
        category="code_flow",
        template="How does error handling work in this codebase? Where are errors caught and how are they processed?",
        difficulty="hard",
        expected_tools=["find_entry_points", "read_file", "get_imports"],
        min_citations=4,
    ),
    QuestionTemplate(
        id="flow_main_function",
        category="code_flow",
        template="Trace what happens when {main_function} is called from start to finish.",
        difficulty="hard",
        expected_tools=["find_entry_points", "read_file", "get_imports"],
        min_citations=4,
    ),
    QuestionTemplate(
        id="flow_execution_path",
        category="code_flow",
        template="What is the execution path from the entry point to {feature_area}?",
        difficulty="hard",
        expected_tools=["find_entry_points", "read_file", "get_imports"],
        min_citations=4,
    ),
    QuestionTemplate(
        id="flow_user_action",
        category="code_flow",
        template="Walk through the code flow step by step when a user performs {feature_area}.",
        difficulty="hard",
        expected_tools=["find_entry_points", "read_file", "get_imports"],
        min_citations=4,
    ),
    # =========================================================================
    # DEBUGGING/INVESTIGATION QUESTIONS
    # =========================================================================
    QuestionTemplate(
        id="debug_where",
        category="debugging",
        template="If I wanted to add logging to track {feature_area}, which files would I need to modify?",
        difficulty="medium",
        expected_tools=["search_code", "read_file"],
        min_citations=2,
    ),
    QuestionTemplate(
        id="debug_config",
        category="debugging",
        template="Where is configuration handled in this project? How would I change settings?",
        difficulty="easy",
        expected_tools=["find_files_by_pattern", "read_file"],
        min_citations=1,
    ),
    QuestionTemplate(
        id="debug_test",
        category="debugging",
        template="How is testing structured in this project? Where are the tests and how do they work?",
        difficulty="medium",
        expected_tools=["list_directory_structure", "read_file"],
        min_citations=2,
    ),
    # =========================================================================
    # SPECIFIC FILE/FUNCTION QUESTIONS
    # =========================================================================
    QuestionTemplate(
        id="specific_main",
        category="specific_file",
        template="What does the main module/file do? Walk me through its key functions.",
        difficulty="easy",
        expected_tools=["get_important_files", "read_file", "get_function_signatures"],
        min_citations=3,
    ),
    QuestionTemplate(
        id="specific_core",
        category="specific_file",
        template="What is the most important class or function in this codebase and why?",
        difficulty="hard",
        expected_tools=["read_file", "get_function_signatures"],
        min_citations=2,
    ),
    QuestionTemplate(
        id="specific_api",
        category="specific_file",
        template="What public API does this {category} expose? List the main functions/methods users would call.",
        difficulty="medium",
        expected_tools=["read_file", "get_function_signatures"],
        min_citations=3,
    ),
]

# Feature areas by category for parameterization
FEATURE_AREAS = {
    "framework": ["HTTP requests", "routing", "middleware", "responses"],
    "library": [
        "core functionality",
        "data processing",
        "API calls",
        "state management",
    ],
    "cli": ["command parsing", "argument handling", "output formatting", "subcommands"],
    "api": ["endpoints", "authentication", "data validation", "responses"],
}

# Main functions by category for code flow questions
MAIN_FUNCTIONS = {
    "framework": [
        "the main application handler",
        "the request router",
        "the middleware chain",
    ],
    "library": [
        "the primary API function",
        "the main processing function",
        "the core algorithm",
    ],
    "cli": [
        "the main command handler",
        "the argument parser",
        "the subcommand dispatcher",
    ],
    "api": ["the request handler", "the endpoint function", "the data processor"],
}


def get_questions_for_repo(
    language: str,
    category: str,
    num_questions: int = 5,
    difficulty_filter: list[str] | None = None,
) -> list[dict]:
    """
    Get a diverse set of questions for a specific repo.

    Args:
        language: Programming language (Python, Go, Rust, etc.)
        category: Repo category (framework, library, cli, api)
        num_questions: Number of questions to return
        difficulty_filter: Only include these difficulties (None = all)

    Returns:
        List of formatted questions with metadata
    """
    # Filter by difficulty if specified
    templates = QUESTION_TEMPLATES
    if difficulty_filter:
        templates = [t for t in templates if t.difficulty in difficulty_filter]

    # Get feature areas for this category
    feature_areas = FEATURE_AREAS.get(category, ["core functionality"])
    main_functions = MAIN_FUNCTIONS.get(category, ["the main function"])

    # Format questions
    questions = []
    for template in templates:
        # Format the template with repo metadata
        question_text = template.template.format(
            language=language,
            category=category,
            feature_area=feature_areas[len(questions) % len(feature_areas)],
            main_function=main_functions[len(questions) % len(main_functions)],
        )

        questions.append(
            {
                "id": template.id,
                "category": template.category,
                "question": question_text,
                "difficulty": template.difficulty,
                "expected_tools": template.expected_tools,
                "min_citations": template.min_citations,
            }
        )

    # Select diverse set (one from each category, then fill)
    categories = [
        "identity",
        "architecture",
        "dependencies",
        "code_flow",
        "debugging",
        "specific_file",
    ]
    selected = []

    # First pass: one from each category
    for cat in categories:
        cat_questions = [q for q in questions if q["category"] == cat]
        if cat_questions and len(selected) < num_questions:
            selected.append(cat_questions[0])

    # Second pass: fill remaining slots
    remaining = [q for q in questions if q not in selected]
    while len(selected) < num_questions and remaining:
        selected.append(remaining.pop(0))

    return selected[:num_questions]


def get_all_questions() -> list[dict]:
    """Get all question templates as formatted dicts."""
    return [
        {
            "id": t.id,
            "category": t.category,
            "template": t.template,
            "difficulty": t.difficulty,
            "expected_tools": t.expected_tools,
            "min_citations": t.min_citations,
        }
        for t in QUESTION_TEMPLATES
    ]
