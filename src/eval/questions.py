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


# Question templates organized by category
QUESTION_TEMPLATES = [
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
        expected_tools=["read_file", "search_code", "get_imports"],
        min_citations=3,
    ),
    QuestionTemplate(
        id="flow_init",
        category="code_flow",
        template="What happens during initialization/startup of this project? Walk through the sequence.",
        difficulty="medium",
        expected_tools=["find_entry_points", "read_file"],
        min_citations=2,
    ),
    QuestionTemplate(
        id="flow_error",
        category="code_flow",
        template="How does error handling work in this codebase? Where are errors caught and how are they processed?",
        difficulty="hard",
        expected_tools=["search_code", "read_file"],
        min_citations=2,
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

    # Format questions
    questions = []
    for template in templates:
        # Format the template with repo metadata
        question_text = template.template.format(
            language=language,
            category=category,
            feature_area=feature_areas[len(questions) % len(feature_areas)],
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
