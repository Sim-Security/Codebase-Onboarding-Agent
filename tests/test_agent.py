"""
Integration tests for CodebaseOnboardingAgent.

Tests cover:
- Agent initialization
- Context budget tracking
- History pruning
- Error handling
- Tool call tracking
"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# =============================================================================
# Agent Initialization Tests
# =============================================================================


class TestAgentInitialization:
    """Tests for agent initialization."""

    def test_initializes_with_valid_path(self, temp_repo: Path, env_with_api_key):
        """Should initialize agent with valid repo path."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo), api_key="test_key")

        assert agent.repo_path == str(temp_repo.resolve())
        assert agent.conversation_history == []
        assert agent.last_tool_calls == []

    def test_raises_for_invalid_path(self, env_with_api_key):
        """Should raise error for nonexistent path."""
        from src.agent import CodebaseOnboardingAgent

        with pytest.raises(ValueError, match="does not exist"):
            CodebaseOnboardingAgent(repo_path="/nonexistent/path", api_key="test_key")

    def test_raises_without_api_key(self, temp_repo: Path, env_without_api_key):
        """Should raise error without API key."""
        from src.agent import CodebaseOnboardingAgent

        with pytest.raises(ValueError, match="API key"):
            CodebaseOnboardingAgent(repo_path=str(temp_repo))

    def test_uses_env_api_key(self, temp_repo: Path, env_with_api_key):
        """Should use API key from environment."""
        from src.agent import CodebaseOnboardingAgent

        # Should not raise - uses env var
        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo))
        assert agent is not None


# =============================================================================
# Context Budget Tests
# =============================================================================


class TestContextBudget:
    """Tests for context budget tracking (EVAL-003)."""

    def test_estimates_tokens(self, temp_repo: Path, env_with_api_key):
        """Should estimate tokens from content."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo), api_key="test_key")

        # Rough estimate: 1 token ≈ 4 chars
        tokens = agent._estimate_tokens("Hello World!")  # 12 chars
        assert tokens == 3  # 12 // 4

    def test_tracks_context_usage(self, temp_repo: Path, env_with_api_key):
        """Should track cumulative context usage."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo), api_key="test_key")

        initial = agent.context_tokens
        agent._track_context("a" * 400)  # 100 tokens
        assert agent.context_tokens == initial + 100

    def test_get_context_usage(self, temp_repo: Path, env_with_api_key):
        """Should return context usage stats."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo), api_key="test_key")

        usage = agent.get_context_usage()

        assert "tokens_used" in usage
        assert "limit" in usage
        assert "percentage" in usage
        assert usage["tokens_used"] == 0
        assert usage["limit"] == 100000  # Default


# =============================================================================
# History Pruning Tests
# =============================================================================


class TestHistoryPruning:
    """Tests for history pruning (UX-006)."""

    def test_prunes_when_over_limit(self, temp_repo: Path, env_with_api_key):
        """Should prune history when over limit."""
        from src.agent import MAX_HISTORY_MESSAGES, CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo), api_key="test_key")

        # Add more messages than limit
        for i in range(MAX_HISTORY_MESSAGES + 10):
            agent.conversation_history.append(HumanMessage(content=f"Message {i}"))

        agent._prune_history()

        assert len(agent.conversation_history) <= MAX_HISTORY_MESSAGES

    def test_preserves_system_messages(self, temp_repo: Path, env_with_api_key):
        """Should preserve system messages during pruning."""
        from src.agent import MAX_HISTORY_MESSAGES, CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo), api_key="test_key")

        # Add system message
        agent.conversation_history.append(SystemMessage(content="System prompt"))

        # Add many regular messages
        for i in range(MAX_HISTORY_MESSAGES + 10):
            agent.conversation_history.append(HumanMessage(content=f"Message {i}"))

        agent._prune_history()

        # System message should still be there
        system_msgs = [
            m for m in agent.conversation_history if isinstance(m, SystemMessage)
        ]
        assert len(system_msgs) == 1

    def test_no_prune_under_limit(self, temp_repo: Path, env_with_api_key):
        """Should not prune when under limit."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo), api_key="test_key")

        agent.conversation_history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there"),
        ]

        original_len = len(agent.conversation_history)
        agent._prune_history()

        assert len(agent.conversation_history) == original_len


# =============================================================================
# Tool Call Tracking Tests
# =============================================================================


class TestToolCallTracking:
    """Tests for tool call tracking."""

    def test_get_tool_calls_empty(self, temp_repo: Path, env_with_api_key):
        """Should return empty list initially."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo), api_key="test_key")

        assert agent.get_tool_calls() == []

    def test_get_tool_names(self, temp_repo: Path, env_with_api_key):
        """Should return unique tool names."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo), api_key="test_key")

        agent.last_tool_calls = [
            {"name": "read_file", "args": {}},
            {"name": "read_file", "args": {}},
            {"name": "search_code", "args": {}},
        ]

        names = agent.get_tool_names()

        assert "read_file" in names
        assert "search_code" in names
        assert len(names) == 2  # Unique

    def test_get_tool_outputs(self, temp_repo: Path, env_with_api_key):
        """Should return tool outputs (EVAL-005)."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo), api_key="test_key")

        agent.last_tool_outputs = ["output1", "output2"]

        outputs = agent.get_tool_outputs()

        assert outputs == ["output1", "output2"]


# =============================================================================
# Conversation Reset Tests
# =============================================================================


class TestConversationReset:
    """Tests for conversation reset functionality."""

    def test_reset_clears_history(self, temp_repo: Path, env_with_api_key):
        """Should clear conversation history on reset."""
        from src.agent import CodebaseOnboardingAgent

        agent = CodebaseOnboardingAgent(repo_path=str(temp_repo), api_key="test_key")

        agent.conversation_history = [HumanMessage(content="Test")]
        agent.last_tool_calls = [{"name": "test", "args": {}}]
        agent.last_tool_outputs = ["output"]

        agent.reset_conversation()

        assert agent.conversation_history == []
        assert agent.last_tool_calls == []
        assert agent.last_tool_outputs == []


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_friendly_error_rate_limit(self):
        """Should return friendly error for rate limit."""
        from src.errors import get_friendly_error

        error = Exception("rate limit exceeded (429)")
        result = get_friendly_error(error)

        assert "Error" in result
        assert "busy" in result.lower() or "rate" in result.lower()

    def test_friendly_error_timeout(self):
        """Should return friendly error for timeout."""
        from src.errors import get_friendly_error

        error = Exception("Request timed out")
        result = get_friendly_error(error)

        assert "Error" in result
        assert "timeout" in result.lower() or "took too long" in result.lower()

    def test_friendly_error_context_length(self):
        """Should return friendly error for context length."""
        from src.errors import get_friendly_error

        error = Exception("context length exceeded")
        result = get_friendly_error(error)

        assert "Error" in result

    def test_is_retryable_error(self):
        """Should identify retryable errors."""
        from src.errors import is_retryable_error

        # Rate limit is retryable (note: space, not underscore)
        assert is_retryable_error(Exception("rate limit")) is True
        assert is_retryable_error(Exception("429")) is True
        assert is_retryable_error(Exception("timed out")) is True
        assert is_retryable_error(Exception("502")) is True
        assert is_retryable_error(Exception("503")) is True

        # Auth errors are not retryable
        assert is_retryable_error(Exception("invalid api key")) is False
        assert is_retryable_error(Exception("random error")) is False


# =============================================================================
# Verification Module Tests
# =============================================================================


class TestVerificationModule:
    """Tests for citation verification (EVAL-001)."""

    def test_extract_citations(self):
        """Should extract file:line citations."""
        from src.eval.verification import extract_citations

        text = "The main function is at src/main.py:42 and the helper is at utils.py:17"

        citations = extract_citations(text)

        assert len(citations) == 2
        assert citations[0]["file"] == "src/main.py"
        assert citations[0]["line"] == 42
        assert citations[1]["file"] == "utils.py"
        assert citations[1]["line"] == 17

    def test_extract_citations_various_extensions(self):
        """Should extract citations with various file extensions."""
        from src.eval.verification import extract_citations

        text = "Found in app.ts:10, server.go:20, lib.rs:30, Main.java:40"

        citations = extract_citations(text)

        assert len(citations) == 4
        assert any(c["file"].endswith(".ts") for c in citations)
        assert any(c["file"].endswith(".go") for c in citations)
        assert any(c["file"].endswith(".rs") for c in citations)
        assert any(c["file"].endswith(".java") for c in citations)

    def test_verify_citation_file_read(self):
        """Should verify citation against tool outputs."""
        from src.eval.verification import verify_citation

        citation = {"file": "main.py", "line": 42}
        tool_outputs = ["📄 main.py (100 lines)\n  42 | def main():\n  43 |     pass"]

        result = verify_citation(citation, tool_outputs)

        assert result["valid"] is True
        assert result["file_read"] is True

    def test_verify_citation_file_not_read(self):
        """Should mark unverified when file not read."""
        from src.eval.verification import verify_citation

        citation = {"file": "other.py", "line": 10}
        tool_outputs = ["📄 main.py (100 lines)\n  1 | import os"]

        result = verify_citation(citation, tool_outputs)

        assert result["valid"] is False
        assert result["file_read"] is False

    def test_count_technical_claims(self):
        """Should count technical claims in text."""
        from src.eval.verification import count_technical_claims

        text = """The application uses FastAPI for the web framework.
        It handles requests at the /api endpoint.
        The database is PostgreSQL.
        """

        count = count_technical_claims(text)

        assert count >= 1  # At least some claims

    def test_calculate_citation_metrics(self):
        """Should calculate precision/recall/F1."""
        from src.eval.verification import calculate_citation_metrics

        response = "The main function at main.py:42 uses the helper at utils.py:17"
        tool_outputs = ["📄 main.py (100 lines)\n  42 | def main():"]

        metrics = calculate_citation_metrics(response, tool_outputs)

        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1" in metrics
        assert metrics["total_citations"] == 2


# =============================================================================
# Provider Configuration Tests
# =============================================================================


class TestProviderConfiguration:
    """Tests for LLM provider configuration."""

    def test_default_model_openrouter(self, temp_repo: Path, env_with_api_key):
        """Should use default OpenRouter model."""
        from src.agent import DEFAULT_MODELS

        assert "openrouter" in DEFAULT_MODELS
        assert DEFAULT_MODELS["openrouter"] is not None

    def test_default_model_groq(self, temp_repo: Path, env_with_api_key):
        """Should have default Groq model."""
        from src.agent import DEFAULT_MODELS

        assert "groq" in DEFAULT_MODELS
        assert DEFAULT_MODELS["groq"] is not None
