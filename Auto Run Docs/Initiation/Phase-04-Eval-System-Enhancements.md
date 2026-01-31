# Phase 04: Evaluation System Enhancements

This phase implements the eval system improvements from the improvement plan's TODO section. We'll add per-category metrics tracking, regression detection, and flaky test identification. These improvements will make it easier to measure progress on specific problem areas like CLI tools and code_flow questions.

## Tasks

- [x] Add per-category metrics tracking to the eval system:
  - Create `src/eval/category_metrics.py` with:
    - `CategoryMetrics` dataclass: `{category: str, total: int, passed: int, pass_rate: float, avg_citations: float}`
    - `aggregate_by_category(results: list[dict]) -> dict[str, CategoryMetrics]` function
    - Categories to track: "architecture", "dependencies", "code_flow", "debugging", "specific_file", "overview", "language_detection"
  - Modify `run_multi_eval.py` to:
    - Call `aggregate_by_category` after running all tests
    - Print a summary table showing pass rate per category
    - Output category breakdown to JSON results file

  **Completed 2026-01-31**: Created `src/eval/category_metrics.py` with:
  - `CategoryMetrics` dataclass with computed properties (pass_rate, avg_citations, citation_accuracy)
  - `aggregate_by_category()` function that processes both standard tests and diverse questions
  - `format_category_metrics_table()` for table display with color-coded indicators
  - `identify_problem_categories()` to flag categories below threshold
  - Integration in `run_multi_eval.py` with summary output to JSON
  - 18 unit tests in `tests/test_category_metrics.py` (all passing)

- [x] Add eval history tracking for regression detection:
  - Create or update `evals/eval_history.json` structure:
    ```json
    {
      "runs": [
        {
          "date": "2026-01-31",
          "model": "x-ai/grok-4.1-fast",
          "overall_pass_rate": 0.788,
          "citation_precision": 0.965,
          "by_category": {...},
          "by_repo": {...}
        }
      ]
    }
    ```
  - Add function `detect_regressions(current: dict, history: list[dict]) -> list[str]`:
    - Compare current run to last 3 runs
    - Flag if any category drops >10% from average
    - Flag if any repo drops >20% from previous run
    - Return list of regression warnings
  - Integrate into `run_multi_eval.py` to show regression warnings at end

  **Completed 2026-01-31**: Created `src/eval/regression.py` with:
  - `RegressionWarning` dataclass to represent detected regressions
  - `get_category_averages(history, last_n=3)` to compute rolling averages
  - `get_repo_pass_rates(run)` to extract per-language pass rates
  - `detect_regressions(current, history, category_threshold=10.0, repo_threshold=20.0)` function
  - `format_regression_warnings()` for formatted console output
  - `regression_warnings_to_dict()` for JSON serialization
  - Integration in `run_multi_eval.py` after historical comparison section
  - 18 unit tests in `tests/test_regression.py` (all passing)
  - Leverages existing `evals/eval_history.json` structure (flat list format)

- [x] Add flaky test detection:
  - In `src/eval/pass_at_k.py`, add flaky test tracking:
    - `detect_flaky_tests(results: list[dict], k: int) -> list[dict]` function
    - A test is flaky if it passes some runs but fails others (0 < pass_count < k)
    - Return list of flaky tests with pass/fail breakdown
  - Add `--detect-flaky` flag to `run_multi_eval.py`:
    - Runs each test 3 times
    - Reports which tests are inconsistent
    - Suggests investigation for flaky tests

  **Completed 2026-01-31**: Created flaky test detection functionality:
  - `FlakyTest` dataclass with fields: test_id, pass_count, fail_count, total_runs, pass_rate, errors, avg_duration_ms
  - `flakiness_score` property (0-1 scale, 1.0 = maximally flaky at 50/50 pass/fail)
  - `detect_flaky_tests(results, k)` function that identifies tests with 0 < passes < k
  - `format_flaky_tests_report()` for human-readable output with investigation suggestions
  - `flaky_tests_to_dict()` for JSON serialization
  - `--detect-flaky` flag (implies --pass-at-k with k=3) in run_multi_eval.py
  - Integration outputs flaky test report and adds to JSON summary
  - 18 unit tests in `tests/test_flaky_detection.py` (all passing)

- [ ] Add question difficulty analysis:
  - In `src/eval/questions.py`, update `QuestionTemplate` to include:
    - `actual_difficulty: str | None` field (computed from eval results)
  - Add function `compute_difficulty_from_results(template_id: str, results: list) -> str`:
    - If pass_rate > 90%: "easy"
    - If pass_rate 70-90%: "medium"
    - If pass_rate < 70%: "hard"
  - Compare computed difficulty vs expected difficulty
  - Report mismatches (questions marked "easy" that actually fail often)

- [ ] Run comprehensive eval with new metrics:
  - Execute: `python run_multi_eval.py --diverse --repos flask,express,gin,click,ripgrep`
  - Verify per-category metrics are displayed
  - Check regression detection works (compare to previous results in evals/)
  - Save enhanced results to `Auto Run Docs/Initiation/Working/phase04_eval_results.txt`
