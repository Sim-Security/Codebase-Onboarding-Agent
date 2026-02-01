"""
Tests for the response caching system.

Tests cover:
- get_repo_hash: Repository state hashing
- CacheKey: Cache key generation and filename creation
- ResponseCache: Cache get/set/invalidate operations
- Agent integration: Caching in CodebaseOnboardingAgent
"""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cache import (
    CACHE_EXPIRATION_DAYS,
    CacheEntry,
    CacheKey,
    ResponseCache,
    get_repo_hash,
)

# =============================================================================
# get_repo_hash Tests
# =============================================================================


class TestGetRepoHash:
    """Tests for get_repo_hash function."""

    def test_hash_changes_with_git_commit(self, temp_repo: Path):
        """Hash should change when git commit changes."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=temp_repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=temp_repo, capture_output=True
        )
        subprocess.run(["git", "add", "."], cwd=temp_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"], cwd=temp_repo, capture_output=True
        )

        hash1 = get_repo_hash(str(temp_repo))

        # Make a change and commit
        (temp_repo / "new_file.txt").write_text("test content")
        subprocess.run(["git", "add", "."], cwd=temp_repo, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add file"], cwd=temp_repo, capture_output=True
        )

        hash2 = get_repo_hash(str(temp_repo))

        assert hash1 != hash2, "Hash should change with new commit"

    def test_hash_changes_with_key_file_modification(self, temp_repo: Path):
        """Hash should change when key files are modified."""
        hash1 = get_repo_hash(str(temp_repo))

        # Modify requirements.txt (a key file)
        req_file = temp_repo / "requirements.txt"
        original = req_file.read_text()
        req_file.write_text(original + "\nnew-package>=1.0.0")

        hash2 = get_repo_hash(str(temp_repo))

        assert hash1 != hash2, "Hash should change when key files are modified"

    def test_hash_consistent_for_same_state(self, temp_repo: Path):
        """Hash should be consistent for the same repo state."""
        hash1 = get_repo_hash(str(temp_repo))
        hash2 = get_repo_hash(str(temp_repo))

        assert hash1 == hash2, "Hash should be consistent for same state"

    def test_hash_works_without_git(self, temp_repo: Path):
        """Hash should work for non-git directories."""
        hash1 = get_repo_hash(str(temp_repo))

        assert hash1, "Should produce a hash even without git"
        assert len(hash1) == 16, "Hash should be 16 characters"

    def test_hash_is_hex_string(self, temp_repo: Path):
        """Hash should be a valid hex string."""
        hash_val = get_repo_hash(str(temp_repo))

        # Should not raise an exception
        int(hash_val, 16)


# =============================================================================
# CacheKey Tests
# =============================================================================


class TestCacheKey:
    """Tests for CacheKey dataclass."""

    def test_create_from_inputs(self, temp_repo: Path):
        """CacheKey.create should generate consistent keys."""
        key = CacheKey.create(str(temp_repo), "What is this codebase?", "gpt-4")

        assert key.repo_hash, "Should have repo hash"
        assert key.question_hash, "Should have question hash"
        assert key.model == "gpt-4", "Should have model"

    def test_question_normalization(self, temp_repo: Path):
        """Questions should be normalized for consistent hashing."""
        key1 = CacheKey.create(str(temp_repo), "What is this?", "gpt-4")
        key2 = CacheKey.create(str(temp_repo), "  WHAT IS THIS?  ", "gpt-4")

        assert key1.question_hash == key2.question_hash, (
            "Normalized questions should have same hash"
        )

    def test_different_questions_different_hashes(self, temp_repo: Path):
        """Different questions should produce different hashes."""
        key1 = CacheKey.create(str(temp_repo), "What is this?", "gpt-4")
        key2 = CacheKey.create(str(temp_repo), "How does it work?", "gpt-4")

        assert key1.question_hash != key2.question_hash, (
            "Different questions should have different hashes"
        )

    def test_different_models_different_keys(self, temp_repo: Path):
        """Different models should produce different keys."""
        key1 = CacheKey.create(str(temp_repo), "What is this?", "gpt-4")
        key2 = CacheKey.create(str(temp_repo), "What is this?", "claude-3")

        assert key1.to_filename() != key2.to_filename(), (
            "Different models should have different filenames"
        )

    def test_to_filename_safe_characters(self, temp_repo: Path):
        """Filename should only contain safe characters."""
        key = CacheKey.create(str(temp_repo), "What is this?", "anthropic/claude-3")

        filename = key.to_filename()

        assert "/" not in filename, "Filename should not contain slashes"
        assert filename.endswith(".json"), "Filename should have .json extension"

    def test_default_model(self, temp_repo: Path):
        """None model should default to 'default'."""
        key = CacheKey.create(str(temp_repo), "What is this?", None)

        assert key.model == "default", "None model should default to 'default'"


# =============================================================================
# CacheEntry Tests
# =============================================================================


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_is_expired_fresh_entry(self):
        """Fresh entries should not be expired."""
        entry = CacheEntry(
            response="test response",
            tool_calls=[],
            created_at=datetime.now().isoformat(),
            repo_path="/test/path",
        )

        assert not entry.is_expired(), "Fresh entry should not be expired"

    def test_is_expired_old_entry(self):
        """Old entries should be expired."""
        old_date = datetime.now() - timedelta(days=CACHE_EXPIRATION_DAYS + 1)
        entry = CacheEntry(
            response="test response",
            tool_calls=[],
            created_at=old_date.isoformat(),
            repo_path="/test/path",
        )

        assert entry.is_expired(), "Old entry should be expired"

    def test_is_expired_invalid_date(self):
        """Invalid dates should be treated as expired."""
        entry = CacheEntry(
            response="test response",
            tool_calls=[],
            created_at="invalid-date",
            repo_path="/test/path",
        )

        assert entry.is_expired(), "Invalid date should be treated as expired"


# =============================================================================
# ResponseCache Tests
# =============================================================================


class TestResponseCache:
    """Tests for ResponseCache class."""

    @pytest.fixture
    def cache(self, temp_repo: Path) -> ResponseCache:
        """Create a cache instance for testing."""
        return ResponseCache(repo_path=str(temp_repo))

    @pytest.fixture
    def cache_key(self, temp_repo: Path) -> CacheKey:
        """Create a test cache key."""
        return CacheKey.create(str(temp_repo), "What is this codebase?", "test-model")

    def test_get_returns_none_for_missing_key(
        self, cache: ResponseCache, cache_key: CacheKey
    ):
        """get() should return None for missing keys."""
        result = cache.get(cache_key)

        assert result is None, "Should return None for missing key"

    def test_set_and_get(self, cache: ResponseCache, cache_key: CacheKey):
        """set() then get() should return the cached response."""
        response = "This is a test response"
        tool_calls = [{"name": "read_file", "args": {"file_path": "test.py"}}]

        cache.set(cache_key, response, tool_calls=tool_calls)
        result = cache.get(cache_key)

        assert result == response, "Should return cached response"

    def test_get_with_tool_calls(self, cache: ResponseCache, cache_key: CacheKey):
        """get_with_tool_calls() should return both response and tool calls."""
        response = "This is a test response"
        tool_calls = [{"name": "read_file", "args": {"file_path": "test.py"}}]

        cache.set(cache_key, response, tool_calls=tool_calls)
        result_response, result_tool_calls = cache.get_with_tool_calls(cache_key)

        assert result_response == response, "Should return cached response"
        assert result_tool_calls == tool_calls, "Should return cached tool calls"

    def test_expired_entry_returns_none(
        self, cache: ResponseCache, cache_key: CacheKey
    ):
        """Expired entries should return None and be deleted."""
        # Manually create an expired entry
        cache_path = cache._get_cache_path(cache_key)
        old_date = datetime.now() - timedelta(days=CACHE_EXPIRATION_DAYS + 1)
        entry_data = {
            "response": "old response",
            "tool_calls": [],
            "created_at": old_date.isoformat(),
            "repo_path": "/test",
        }
        cache_path.write_text(json.dumps(entry_data))

        result = cache.get(cache_key)

        assert result is None, "Expired entry should return None"
        assert not cache_path.exists(), "Expired entry should be deleted"

    def test_corrupted_entry_returns_none(
        self, cache: ResponseCache, cache_key: CacheKey
    ):
        """Corrupted entries should return None and be deleted."""
        cache_path = cache._get_cache_path(cache_key)
        cache_path.write_text("not valid json {{{")

        result = cache.get(cache_key)

        assert result is None, "Corrupted entry should return None"
        assert not cache_path.exists(), "Corrupted entry should be deleted"

    def test_invalidate_removes_stale_entries(
        self, cache: ResponseCache, temp_repo: Path
    ):
        """invalidate() should remove entries with old repo hash."""
        # Create an entry with a fake old hash (simulating repo change)
        old_key = CacheKey(
            repo_hash="oldhash12345678",
            question_hash="testhash1234567",
            model="model",
        )
        cache.set(old_key, "test response")

        # Verify entry exists
        assert cache.get(old_key) == "test response"

        # Invalidate - should remove entry with old hash
        count = cache.invalidate(str(temp_repo))

        assert count == 1, "Should invalidate one entry"
        assert cache.get(old_key) is None, "Entry should be gone"

    def test_clear_removes_all_entries(self, cache: ResponseCache, cache_key: CacheKey):
        """clear() should remove all cache entries."""
        cache.set(cache_key, "response 1")

        # Create another entry
        key2 = CacheKey(repo_hash="other", question_hash="other", model="other")
        cache.set(key2, "response 2")

        count = cache.clear()

        assert count == 2, "Should clear 2 entries"
        assert cache.get(cache_key) is None, "First entry should be gone"
        assert cache.get(key2) is None, "Second entry should be gone"

    def test_get_stats(self, cache: ResponseCache, cache_key: CacheKey):
        """get_stats() should return cache statistics."""
        cache.set(cache_key, "test response")

        stats = cache.get_stats()

        assert stats["entries"] == 1, "Should have 1 entry"
        assert stats["total_size_bytes"] > 0, "Should have non-zero size"
        assert "cache_dir" in stats, "Should include cache directory"

    def test_gitignore_created(self, temp_repo: Path):
        """Cache directory should have .gitignore."""
        cache = ResponseCache(repo_path=str(temp_repo))

        gitignore = cache.cache_dir / ".gitignore"

        assert gitignore.exists(), ".gitignore should exist"
        content = gitignore.read_text()
        assert "*" in content, ".gitignore should ignore all files"


# =============================================================================
# Agent Integration Tests
# =============================================================================


class TestAgentCacheIntegration:
    """Tests for cache integration in CodebaseOnboardingAgent."""

    @pytest.fixture
    def mock_agent_with_cache(self, temp_repo: Path):
        """Create a mock agent with caching enabled."""
        with patch("src.agent.create_agent") as mock_create:
            # Mock the underlying LangGraph agent
            mock_graph = MagicMock()

            # Create a mock response
            from langchain_core.messages import AIMessage

            mock_response = {"messages": [AIMessage(content="Test response")]}
            mock_graph.invoke.return_value = mock_response

            mock_create.return_value = mock_graph

            from src.agent import CodebaseOnboardingAgent

            agent = CodebaseOnboardingAgent(
                str(temp_repo), api_key="test-key", use_cache=True
            )
            return agent

    @pytest.fixture
    def mock_agent_no_cache(self, temp_repo: Path):
        """Create a mock agent with caching disabled."""
        with patch("src.agent.create_agent") as mock_create:
            mock_graph = MagicMock()

            from langchain_core.messages import AIMessage

            mock_response = {"messages": [AIMessage(content="Test response")]}
            mock_graph.invoke.return_value = mock_response

            mock_create.return_value = mock_graph

            from src.agent import CodebaseOnboardingAgent

            agent = CodebaseOnboardingAgent(
                str(temp_repo), api_key="test-key", use_cache=False
            )
            return agent

    def test_cache_enabled_by_default(self, temp_repo: Path):
        """Cache should be enabled by default."""
        with patch("src.agent.create_agent"):
            from src.agent import CodebaseOnboardingAgent

            agent = CodebaseOnboardingAgent(str(temp_repo), api_key="test-key")

            assert agent.use_cache is True, "Cache should be enabled by default"
            assert agent.cache is not None, "Cache object should exist"

    def test_cache_disabled_when_requested(self, mock_agent_no_cache):
        """Cache should be disabled when use_cache=False."""
        assert mock_agent_no_cache.use_cache is False
        assert mock_agent_no_cache.cache is None

    def test_cache_hit_flag(self, mock_agent_with_cache):
        """was_cache_hit() should return True after cache hit."""
        agent = mock_agent_with_cache

        # First call - cache miss
        agent._run("test question")
        assert not agent.was_cache_hit(), "First call should be cache miss"

        # Second call with same question - cache hit
        agent._run("test question")
        assert agent.was_cache_hit(), "Second call should be cache hit"

    def test_get_cache_stats(self, mock_agent_with_cache):
        """get_cache_stats() should return cache statistics."""
        agent = mock_agent_with_cache

        stats = agent.get_cache_stats()

        assert "entries" in stats
        assert "total_size_bytes" in stats

    def test_invalidate_cache(self, mock_agent_with_cache, temp_repo: Path):
        """invalidate_cache() should invalidate cache entries."""
        agent = mock_agent_with_cache

        # Manually add a cached entry with a fake old hash
        old_key = CacheKey(
            repo_hash="oldhash12345678",
            question_hash="testhash1234567",
            model=agent.model,
        )
        agent.cache.set(old_key, "old response")

        # Invalidate - should remove entry with old hash
        count = agent.invalidate_cache()

        assert count == 1, "Should invalidate one entry"

    def test_cache_disabled_stats(self, mock_agent_no_cache):
        """get_cache_stats() should indicate disabled when cache is off."""
        stats = mock_agent_no_cache.get_cache_stats()

        assert stats["entries"] == 0
        assert stats.get("cache_enabled") is False

    def test_reset_conversation_clears_cache_hit_flag(self, mock_agent_with_cache):
        """reset_conversation() should reset the cache hit flag."""
        agent = mock_agent_with_cache

        # First call
        agent._run("test question")
        # Second call - cache hit
        agent._run("test question")
        assert agent.was_cache_hit()

        # Reset
        agent.reset_conversation()

        assert not agent.was_cache_hit(), "Cache hit flag should be reset"
