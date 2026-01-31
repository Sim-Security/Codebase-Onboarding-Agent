# Phase 01: CLI Pattern Detection Enhancement

This phase addresses the highest-impact improvement: fixing CLI tool analysis. The agent currently struggles with decorator-based entry points (`@click.command()`, `@app.command()`) and confuses similar projects (click vs Flask). By adding robust CLI framework detection patterns to the `find_entry_points` tool, we'll improve the 33% click pass rate and 67% turborepo pass rate significantly.

## Tasks

- [x] Add CLI framework detection patterns to `src/tools/code_analyzer.py`:
  - Add a `CLI_FRAMEWORK_PATTERNS` dictionary at module level with regex patterns for:
    - click: `r"@click\.(command|group|option|argument)"`
    - typer: `r"@app\.(command|callback)"`
    - argparse: `r"ArgumentParser\(\)"`
    - fire: `r"fire\.Fire\("`
    - docopt: `r"docopt\(__doc__"`
    - rust clap: `r"#\[derive\(.*(?:Parser|Args|Subcommand)"`
    - rust structopt: `r"#\[structopt"`
    - go cobra: `r"cobra\.Command\{"`
    - go urfave/cli: `r"cli\.App\{"`
  - ✅ Completed: Added `CLI_FRAMEWORK_PATTERNS` dictionary at line 12-29 with all specified patterns organized by language (python, rust, go).

- [x] Enhance the `find_entry_points` function in `src/tools/code_analyzer.py`:
  - After the existing entry point file detection, add a new section that searches for CLI patterns
  - For Python files, search for `@click.command`, `@click.group`, `@app.command`, etc.
  - For Rust files, search for `#[derive(Parser)]` and similar clap patterns
  - For Go files, search for `cobra.Command` struct definitions
  - Add matches to `found_entries` with descriptive notes like "CLI command decorator"
  - Search in `setup.py` for `console_scripts` entry points
  - Check for `__main__.py` files that import CLI frameworks
  - ✅ Completed: Implementation already existed at lines 279-380. Added comprehensive test suite with 10 new tests covering all CLI frameworks (click, typer, argparse, fire, clap, structopt, cobra, urfave/cli) plus console_scripts and __main__.py detection. Tests added to `tests/test_tools.py::TestFindEntryPoints` and fixture `temp_repo_with_cli_frameworks` in `tests/conftest.py`. All 14 TestFindEntryPoints tests pass.

- [x] Add negative example disambiguation to `src/prompts/__init__.py`:
  - Add a new section in SYSTEM_PROMPT after the tool descriptions:
    ```
    ## CRITICAL: Project Identity Rules

    NEVER confuse similarly-named projects. Common confusions to avoid:
    - click (Python CLI framework) is NOT Flask (Python web framework)
    - cobra (Go CLI framework) is NOT gin (Go web framework)
    - typer (Python CLI) is NOT FastAPI (Python web)
    - clap (Rust CLI) is NOT actix/axum (Rust web)

    Before describing ANY project, verify by reading actual source files.
    If you see `@click.command` decorators, it's a CLI tool, not a web framework.
    If you see `app = Flask(__name__)`, it's a web framework, not a CLI tool.
    ```
  - ✅ Completed: Added "## CRITICAL: Project Identity Rules" section at lines 21-31 in `src/prompts/__init__.py`, placed after the tool descriptions and before the "## Approach" section. All 134 passing tests remain passing (5 pre-existing failures unrelated to this change).

- [x] Run the evaluation suite to verify improvements:
  - Execute: `python run_multi_eval.py --repos click,cobra --diverse`
  - Capture output to `Auto Run Docs/Initiation/Working/phase01_eval_results.txt`
  - Check that click pass rate improves from 33% baseline
  - Verify cobra maintains 100% pass rate (no regression)
  - ✅ Completed: Evaluation run on 2026-01-31 15:38:32
    - **click**: 100% pass rate (improved from 33% baseline - 3x improvement!)
    - **cobra**: 100% pass rate (maintained, no regression)
    - **CLI category overall**: 6/6 (100.0%)
    - **Citation precision**: 100% (improved from 96.5%)
    - Results saved to `Auto Run Docs/Initiation/Working/phase01_eval_results.txt`
