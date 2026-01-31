# Phase 02: Deep-Dive Tool Usage Enforcement

This phase addresses the second high-impact issue: the agent sometimes answers deep-dive questions without calling `read_file`, resulting in 0 citations. The improvement plan identifies this in Priority 2. We'll strengthen the DEEP_DIVE_PROMPT and add validation to ensure the agent actually reads files before making claims.

## Tasks

- [x] Strengthen DEEP_DIVE_PROMPT in `src/prompts/__init__.py`:
  - Add an explicit "MANDATORY STEPS" section at the top that emphasizes:
    - STEP 1: SEARCH - Use `search_code` with keywords from the question
    - STEP 2: READ - Call `read_file` on AT LEAST 2 files before answering
    - STEP 3: ANSWER - Only after reading files, with citations from files you read
  - Add a "FAILURE MODES TO AVOID" section:
    - "Answering based on file names alone without reading content"
    - "Citing line numbers from files you never called read_file on"
    - "Providing generic answers that could apply to any codebase"
  - Add explicit instruction: "If you haven't called read_file on a file, you CANNOT cite its line numbers. Period."

  **Completed:** Enhanced DEEP_DIVE_PROMPT with prominent MANDATORY STEPS section, FAILURE MODES TO AVOID section (3 anti-patterns), ABSOLUTE RULE section emphasizing the read_file requirement, and added a VALIDATION CHECKLIST for agent self-verification.

- [x] Add tool usage validation helper in `src/eval/verification.py`:
  - Create function `validate_tool_usage(tool_calls: list[dict], response: str) -> dict`:
    - Check if `read_file` was called before any citations appear
    - Count number of unique files read
    - Return `{"has_read_file": bool, "files_read_count": int, "citations_count": int, "valid": bool}`
  - Create function `get_files_read_from_tool_calls(tool_calls: list[dict]) -> set[str]`:
    - Extract file paths from all `read_file` tool calls
    - Return set of file paths that were actually read

  **Completed:** Added `get_files_read_from_tool_calls()` that extracts file paths from read_file tool calls, and `validate_tool_usage()` that validates citations are properly grounded in files that were actually read. Also added `ToolUsageValidationResult` dataclass. Functions include path matching that handles both exact paths and basename matching for flexibility. Added 6 unit tests to `tests/test_agent.py` covering: unique file extraction, empty tool calls, valid citations, invalid citations (no read_file), no citations case, and partial read scenarios.

- [x] Add validation in `CodebaseOnboardingAgent._run()` in `src/agent.py`:
  - After extracting the final response and before returning it, add validation:
    - Get citations from response using `extract_citations()`
    - Get files read from `self.last_tool_calls` by filtering for `read_file` calls
    - If citations exist but no `read_file` calls were made, log a warning
    - Consider filtering all citations if no files were read (already partially implemented at line ~390)
  - Add a counter for validation failures to `self.tool_tracker` for debugging

  **Completed:** Implemented comprehensive validation in `_run()` using the new `validate_tool_usage()` function. Added `validation_failures` counter to `CircuitBreakerState` in `tool_router.py`. The validation logs warnings for two failure cases: (1) citations exist but no read_file calls were made, and (2) citations reference files that were never read. The counter is incremented via `self.tool_tracker.circuit_breaker.validation_failures` and exposed in `get_stats()`. Also fixed pytest.ini ROS plugin conflict.

- [ ] Add tool usage metrics to eval runner:
  - In `run_multi_eval.py` or create a new `src/eval/tool_metrics.py`:
    - Track `read_file_calls` count per question
    - Track `search_code_calls` count per question
    - Flag questions where answer had citations but no `read_file` calls
    - Output metrics alongside pass/fail in eval results

- [ ] Run evaluation to verify improvements:
  - Execute: `python run_multi_eval.py --repos click,turborepo --diverse`
  - Check that deep_dive questions now have >0 citations
  - Verify tool usage metrics show `read_file` being called before citations
  - Save results to `Auto Run Docs/Initiation/Working/phase02_eval_results.txt`
