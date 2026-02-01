# Phase 05: Performance and Streaming Improvements

This phase addresses Priority 5 from the improvement plan: performance improvements including streaming responses, caching, and parallel tool calls. The agent currently operates synchronously without streaming, which hurts user experience. We'll enhance the Gradio UI to show real-time progress and add caching for repeated queries.

## Tasks

- [x] Implement streaming in the Gradio UI (`app.py`):
  - The agent already has `stream()` and `stream_overview()` methods in `src/agent.py`
  - Update the Gradio chat interface to use streaming:
    - Replace `agent.ask()` calls with `async for event in agent.stream_ask(question)`
    - Yield partial responses as they arrive (`type: "token"`)
    - Show tool usage indicators when `type: "tool_start"` events occur
    - Clear tool indicators when `type: "tool_end"` events occur
  - Add a status indicator showing:
    - "🔍 Exploring codebase..." when tools are running
    - "📖 Reading file.py..." when reading a specific file
    - "🔎 Searching for X..." when searching

  **COMPLETED (2026-01-31):**
  - Added `_get_tool_status_indicator()` helper function in `app.py` with contextual status messages for all 9 tools:
    - 📖 Reading {filename}... for `read_file`
    - 🔎 Searching for '{pattern}'... for `search_code`
    - 🔎 Finding files matching '{pattern}'... for `find_files_by_pattern`
    - 📂 Exploring directory structure... for `list_directory_structure`
    - 📦 Analyzing imports in {filename}... for `get_imports`
    - 🚀 Finding entry points... for `find_entry_points`
    - 🔗 Analyzing dependencies... for `analyze_dependencies`
    - 📝 Getting function signatures from {filename}... for `get_function_signatures`
    - ⭐ Identifying important files... for `get_important_files`
    - 🔍 {tool_name}... for unknown tools
  - Updated `chat_stream()` and `overview_stream()` to use the contextual status indicator
  - Streaming was already implemented via `agent.stream()` - this enhancement adds user-friendly tool status messages
  - Added tests in `tests/test_streaming.py`

- [x] Add response caching based on repo state:
  - Create `src/cache.py` with:
    - `get_repo_hash(repo_path: str) -> str`: Compute hash of repo state (git HEAD + file mtimes for key files)
    - `CacheKey` dataclass: `{repo_hash: str, question_hash: str, model: str}`
    - `ResponseCache` class with:
      - `get(key: CacheKey) -> str | None`
      - `set(key: CacheKey, response: str, tool_calls: list)`
      - `invalidate(repo_path: str)` when repo changes
    - Use file-based cache in `.cache/` directory (simple JSON)
  - Integrate caching into `CodebaseOnboardingAgent`:
    - Check cache before calling `_run()`
    - Store results after successful runs
    - Add `--no-cache` flag to bypass cache

  **COMPLETED (2026-01-31):**
  - Created `src/cache.py` with comprehensive caching infrastructure:
    - `get_repo_hash()`: Computes SHA256 hash based on git HEAD + key file mtimes (requirements.txt, pyproject.toml, package.json, etc.)
    - `CacheKey` dataclass with `repo_hash`, `question_hash`, `model` fields and factory method `create()`
    - `CacheEntry` dataclass with expiration checking (7 day default)
    - `ResponseCache` class with:
      - `get(key)` / `get_with_tool_calls(key)`: Retrieve cached responses
      - `set(key, response, tool_calls)`: Store responses
      - `invalidate(repo_path)`: Remove entries with stale repo hash
      - `clear()`: Remove all entries
      - `get_stats()`: Return cache statistics
    - File-based cache in `.cache/` directory with auto-created `.gitignore`
  - Integrated caching into `CodebaseOnboardingAgent`:
    - Added `use_cache` parameter (default: True)
    - Cache check at start of `_run()` method
    - Cache storage after successful responses
    - Added `was_cache_hit()`, `invalidate_cache()`, `get_cache_stats()` methods
    - `reset_conversation()` resets cache hit flag
  - Added `--no-cache` CLI flag to disable caching
  - Added comprehensive tests in `tests/test_cache.py` (30 tests, all passing):
    - `TestGetRepoHash`: 5 tests for hash generation
    - `TestCacheKey`: 6 tests for key creation
    - `TestCacheEntry`: 3 tests for expiration
    - `TestResponseCache`: 9 tests for cache operations
    - `TestAgentCacheIntegration`: 7 tests for agent integration

- [ ] Add progress tracking for long operations:
  - In `src/agent.py`, add progress callbacks:
    - Create `ProgressCallback` protocol: `def __call__(self, step: str, detail: str)`
    - Pass optional callback to `_run()` method
    - Call progress callback when:
      - Tool is about to be called
      - Tool returns results
      - Agent is thinking
  - In Gradio UI, display progress in a status component:
    - Show which tool is being called
    - Show file being read
    - Show search pattern being used

- [ ] Optimize tool execution where possible:
  - In `src/agent.py`, identify opportunities for parallel tool calls:
    - `find_entry_points` + `analyze_dependencies` can run in parallel
    - Multiple `get_imports` calls can be parallelized
  - Document which tools are independent vs dependent
  - Consider using `asyncio.gather` for parallel execution in future iteration

- [ ] Test streaming and caching:
  - Run the Gradio app locally: `python app.py`
  - Test that responses stream in real-time
  - Test that cached responses are returned quickly
  - Verify cache invalidation works when repo changes
  - Document any issues in `Auto Run Docs/Initiation/Working/phase05_testing_notes.txt`
