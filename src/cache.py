"""
Response caching based on repository state.

Provides caching for agent responses to improve performance on repeated queries.
Cache keys are based on:
- Repository state (git HEAD + file mtimes)
- Question hash
- Model identifier

The cache invalidates automatically when the repository changes.
"""

import hashlib
import json
import logging
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default cache directory relative to repo
DEFAULT_CACHE_DIR = ".cache"

# Cache entry expiration (7 days)
CACHE_EXPIRATION_DAYS = 7


def get_repo_hash(repo_path: str) -> str:
    """
    Compute hash of repository state.

    Uses git HEAD commit hash if available, combined with modification times
    of key files (requirements.txt, pyproject.toml, package.json, etc.)
    to detect changes that might affect agent responses.

    Args:
        repo_path: Path to the repository

    Returns:
        SHA256 hash representing current repo state
    """
    repo_path = Path(repo_path).resolve()
    state_parts = []

    # Try to get git HEAD hash
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            state_parts.append(f"git:{result.stdout.strip()}")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # Not a git repo or git not available - use directory mtime
        state_parts.append(f"dir:{repo_path.stat().st_mtime}")

    # Key files that indicate project structure changes
    key_files = [
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "README.md",
        "README.rst",
    ]

    for filename in key_files:
        file_path = repo_path / filename
        if file_path.exists():
            try:
                stat = file_path.stat()
                state_parts.append(f"{filename}:{stat.st_mtime}:{stat.st_size}")
            except OSError:
                pass

    # Hash all state parts
    state_string = "|".join(sorted(state_parts))
    return hashlib.sha256(state_string.encode()).hexdigest()[:16]


@dataclass
class CacheKey:
    """
    Cache key combining repo state, question, and model.

    Attributes:
        repo_hash: Hash of the repository state
        question_hash: Hash of the normalized question
        model: Model identifier used for the query
    """

    repo_hash: str
    question_hash: str
    model: str

    @classmethod
    def create(cls, repo_path: str, question: str, model: str) -> "CacheKey":
        """
        Create a cache key from inputs.

        Args:
            repo_path: Path to the repository
            question: The question being asked
            model: Model identifier

        Returns:
            CacheKey instance
        """
        repo_hash = get_repo_hash(repo_path)

        # Normalize question for consistent hashing
        normalized_question = question.strip().lower()
        question_hash = hashlib.sha256(normalized_question.encode()).hexdigest()[:16]

        return cls(
            repo_hash=repo_hash, question_hash=question_hash, model=model or "default"
        )

    def to_filename(self) -> str:
        """Generate a filename from this cache key."""
        return (
            f"{self.repo_hash}_{self.question_hash}_{self.model.replace('/', '_')}.json"
        )


@dataclass
class CacheEntry:
    """
    A cached response entry.

    Attributes:
        response: The cached response text
        tool_calls: List of tool calls made during the response
        created_at: ISO timestamp when entry was created
        repo_path: Path to the repository (for reference)
    """

    response: str
    tool_calls: list[dict]
    created_at: str
    repo_path: str

    def is_expired(self, max_age_days: int = CACHE_EXPIRATION_DAYS) -> bool:
        """Check if this entry has expired."""
        try:
            created = datetime.fromisoformat(self.created_at)
            return datetime.now() - created > timedelta(days=max_age_days)
        except (ValueError, TypeError):
            return True


class ResponseCache:
    """
    File-based cache for agent responses.

    Stores cached responses as JSON files in a .cache directory.
    Automatically handles cache invalidation based on repository state.
    """

    def __init__(
        self, cache_dir: str | Path | None = None, repo_path: str | None = None
    ):
        """
        Initialize the cache.

        Args:
            cache_dir: Directory for cache files. If None, uses .cache in repo_path.
            repo_path: Repository path (used to determine cache location if cache_dir not set)
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        elif repo_path:
            self.cache_dir = Path(repo_path) / DEFAULT_CACHE_DIR
        else:
            # Fallback to temp directory
            import tempfile

            self.cache_dir = Path(tempfile.gettempdir()) / "codebase_onboarding_cache"

        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Add .gitignore to cache directory
            gitignore_path = self.cache_dir / ".gitignore"
            if not gitignore_path.exists():
                gitignore_path.write_text("*\n!.gitignore\n")
        except OSError as e:
            logger.warning(f"Could not create cache directory: {e}")

    def _get_cache_path(self, key: CacheKey) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / key.to_filename()

    def get(self, key: CacheKey) -> str | None:
        """
        Retrieve a cached response.

        Args:
            key: The cache key to look up

        Returns:
            Cached response string if found and valid, None otherwise
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            logger.debug(f"Cache miss: {key.to_filename()}")
            return None

        try:
            data = json.loads(cache_path.read_text())
            entry = CacheEntry(
                response=data["response"],
                tool_calls=data.get("tool_calls", []),
                created_at=data.get("created_at", ""),
                repo_path=data.get("repo_path", ""),
            )

            if entry.is_expired():
                logger.debug(f"Cache entry expired: {key.to_filename()}")
                cache_path.unlink(missing_ok=True)
                return None

            logger.info(f"Cache hit: {key.to_filename()}")
            return entry.response

        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(f"Error reading cache entry: {e}")
            cache_path.unlink(missing_ok=True)
            return None

    def get_with_tool_calls(self, key: CacheKey) -> tuple[str | None, list[dict]]:
        """
        Retrieve a cached response with its tool calls.

        Args:
            key: The cache key to look up

        Returns:
            Tuple of (response, tool_calls) if found, (None, []) otherwise
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None, []

        try:
            data = json.loads(cache_path.read_text())
            entry = CacheEntry(
                response=data["response"],
                tool_calls=data.get("tool_calls", []),
                created_at=data.get("created_at", ""),
                repo_path=data.get("repo_path", ""),
            )

            if entry.is_expired():
                cache_path.unlink(missing_ok=True)
                return None, []

            logger.info(f"Cache hit: {key.to_filename()}")
            return entry.response, entry.tool_calls

        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(f"Error reading cache entry: {e}")
            return None, []

    def set(
        self,
        key: CacheKey,
        response: str,
        tool_calls: list[dict] | None = None,
        repo_path: str | None = None,
    ) -> bool:
        """
        Store a response in the cache.

        Args:
            key: The cache key
            response: The response to cache
            tool_calls: List of tool calls made during the response
            repo_path: Repository path (for reference)

        Returns:
            True if successfully cached, False otherwise
        """
        cache_path = self._get_cache_path(key)

        entry = CacheEntry(
            response=response,
            tool_calls=tool_calls or [],
            created_at=datetime.now().isoformat(),
            repo_path=repo_path or "",
        )

        try:
            cache_path.write_text(json.dumps(asdict(entry), indent=2))
            logger.info(f"Cached response: {key.to_filename()}")
            return True
        except OSError as e:
            logger.warning(f"Could not write cache entry: {e}")
            return False

    def invalidate(self, repo_path: str) -> int:
        """
        Invalidate all cache entries for a repository.

        This is useful when the repository has changed and all cached
        responses should be considered stale.

        Args:
            repo_path: Path to the repository

        Returns:
            Number of entries invalidated
        """
        current_hash = get_repo_hash(repo_path)
        invalidated = 0

        try:
            for cache_file in self.cache_dir.glob("*.json"):
                if cache_file.name == ".gitignore":
                    continue

                # Extract repo hash from filename
                parts = cache_file.stem.split("_")
                if len(parts) >= 1:
                    file_repo_hash = parts[0]
                    if file_repo_hash != current_hash:
                        cache_file.unlink()
                        invalidated += 1
                        logger.debug(f"Invalidated cache entry: {cache_file.name}")
        except OSError as e:
            logger.warning(f"Error during cache invalidation: {e}")

        if invalidated > 0:
            logger.info(
                f"Invalidated {invalidated} cache entries for repo state change"
            )

        return invalidated

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        cleared = 0

        try:
            for cache_file in self.cache_dir.glob("*.json"):
                if cache_file.name == ".gitignore":
                    continue
                cache_file.unlink()
                cleared += 1
        except OSError as e:
            logger.warning(f"Error clearing cache: {e}")

        if cleared > 0:
            logger.info(f"Cleared {cleared} cache entries")

        return cleared

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats (entries, size, etc.)
        """
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            # Filter out .gitignore from count
            json_files = [f for f in cache_files if f.suffix == ".json"]

            total_size = sum(f.stat().st_size for f in json_files if f.exists())

            return {
                "entries": len(json_files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "cache_dir": str(self.cache_dir),
            }
        except OSError:
            return {
                "entries": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "cache_dir": str(self.cache_dir),
            }
