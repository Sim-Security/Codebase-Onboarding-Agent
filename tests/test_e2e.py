"""
End-to-end tests for the Codebase Onboarding Agent.

These tests call the real API and require OPENROUTER_API_KEY to be set.
Skip gracefully when API key is not available.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set - skipping E2E tests",
)


@pytest.fixture
def simple_repo() -> Path:
    """Create a simple test repository for E2E testing."""
    repo_dir = tempfile.mkdtemp(prefix="e2e_repo_")
    repo_path = Path(repo_dir)

    # Create a minimal Python project
    (repo_path / "src").mkdir()
    (repo_path / "src" / "__init__.py").write_text("")
    (
        repo_path / "src" / "main.py"
    ).write_text('''"""Main module for the test application."""

import os
from typing import Optional

def greet(name: str = "World") -> str:
    """Greet someone by name.

    Args:
        name: The name to greet

    Returns:
        A greeting message
    """
    return f"Hello, {name}!"


def main() -> None:
    """Entry point for the application."""
    message = greet()
    print(message)


if __name__ == "__main__":
    main()
''')

    (repo_path / "requirements.txt").write_text("typing_extensions>=4.0.0\n")

    (repo_path / "README.md").write_text("""# Test Project

A simple test project for E2E testing.

## Usage

```bash
python src/main.py
```
""")

    yield repo_path

    # Cleanup
    shutil.rmtree(repo_dir, ignore_errors=True)


@pytest.mark.e2e
@pytest.mark.slow
class TestEndToEnd:
    """End-to-end tests with real API calls."""

    def test_agent_initialization(self, simple_repo: Path):
        """Should initialize agent with real API key."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(simple_repo))

        assert agent is not None
        assert agent.repo_path == str(simple_repo.resolve())

    def test_get_overview_returns_response(self, simple_repo: Path):
        """Should generate an overview with real API call."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(
            repo_path=str(simple_repo),
            model="xiaomi/mimo-v2-flash:free",  # Use free model for tests
        )

        overview = agent.get_overview()

        # Should have some content
        assert len(overview) > 100
        # Should mention Python (the language of the project)
        assert "python" in overview.lower() or "py" in overview.lower()

    def test_get_overview_uses_tools(self, simple_repo: Path):
        """Should use tools when generating overview."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(
            repo_path=str(simple_repo), model="xiaomi/mimo-v2-flash:free"
        )

        agent.get_overview()
        tool_names = agent.get_tool_names()

        # Should have used at least one tool
        assert len(tool_names) > 0

    def test_ask_returns_grounded_response(self, simple_repo: Path):
        """Should answer questions with citations."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(
            repo_path=str(simple_repo), model="xiaomi/mimo-v2-flash:free"
        )

        # Ask about the main function
        response = agent.ask("How does the main function work?")

        # Should have content
        assert len(response) > 50
        # Should use tools
        tool_names = agent.get_tool_names()
        assert len(tool_names) > 0

    def test_conversation_maintains_history(self, simple_repo: Path):
        """Should maintain conversation context."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(
            repo_path=str(simple_repo), model="xiaomi/mimo-v2-flash:free"
        )

        # First message
        agent.chat("What is this project about?")
        history_len_1 = len(agent.conversation_history)

        # Second message
        agent.chat("Tell me more about the main function.")
        history_len_2 = len(agent.conversation_history)

        # History should grow
        assert history_len_2 > history_len_1

    def test_reset_clears_context(self, simple_repo: Path):
        """Should clear context on reset."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(
            repo_path=str(simple_repo), model="xiaomi/mimo-v2-flash:free"
        )

        # Build some history
        agent.chat("What is this project?")
        assert len(agent.conversation_history) > 0

        # Reset
        agent.reset_conversation()

        # Should be empty
        assert len(agent.conversation_history) == 0
        assert len(agent.last_tool_calls) == 0


@pytest.mark.e2e
@pytest.mark.slow
class TestToolVerification:
    """Verify that tools are being used correctly."""

    def test_read_file_tool_used(self, simple_repo: Path):
        """Should use read_file tool for specific questions."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(
            repo_path=str(simple_repo), model="xiaomi/mimo-v2-flash:free"
        )

        # Ask about a specific file
        agent.ask("What does the greet function in main.py do?")
        tool_names = agent.get_tool_names()

        # Should have used read_file
        assert "read_file" in tool_names

    def test_list_directory_tool_used(self, simple_repo: Path):
        """Should use list_directory_structure for structure questions."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(
            repo_path=str(simple_repo), model="xiaomi/mimo-v2-flash:free"
        )

        # Ask about project structure
        agent.ask("What is the directory structure of this project?")
        tool_names = agent.get_tool_names()

        # Should have used list_directory_structure
        assert "list_directory_structure" in tool_names


@pytest.mark.e2e
@pytest.mark.slow
class TestErrorHandling:
    """Test error handling with real API."""

    def test_handles_invalid_model_gracefully(self, simple_repo: Path):
        """Should handle invalid model name gracefully."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(
            repo_path=str(simple_repo), model="invalid-model-name-xyz-123"
        )

        # Should not crash, but return error message
        result = agent.get_overview()

        # Should have some error indication
        assert result is not None
        # Might be an error message or successful with fallback
        assert len(result) > 0
