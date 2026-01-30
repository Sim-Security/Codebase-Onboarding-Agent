# SESSION PROMPT: Codebase-Onboarding-Agent v2.0 Implementation

**Copy everything below this line and paste into a new Claude Code session**

---

## CONTEXT

You are implementing improvements to the **Codebase-Onboarding-Agent** project based on a comprehensive analysis performed using THE ALGORITHM (DETERMINED mode) with Council debate and RedTeam adversarial analysis.

**Project Location:** `/home/ranomis/Projects/Codebase-Onboarding-Agent`

**Key Documents (READ THESE FIRST):**
1. `Plans/IMPROVEMENT_PLAN.md` - Analysis findings from Council + RedTeam
2. `Plans/PRD.md` - Product requirements with acceptance criteria
3. `Plans/BACKLOG.md` - 32 implementation tasks with code snippets

## EXECUTION MODE

Use **THE ALGORITHM** in **DETERMINED** mode with **RALPH Loop** for persistent iteration.

```
/skill THEALGORITHM DETERMINED MODE: Implement Codebase-Onboarding-Agent v2.0 improvements
```

## METHODOLOGY: RALPH + THE ALGORITHM

### The RALPH Loop Pattern

For each sprint/task:
1. **R**ead - Read the task from BACKLOG.md
2. **A**nalyze - Understand dependencies and implementation details
3. **L**earn - Check existing code patterns in the codebase
4. **P**lan - Design the specific changes needed
5. **H**ack - Implement and test until working

### Completion Promise Pattern

For each task, iterate until the completion promise is satisfied:
```bash
bun run ~/.claude/skills/THEALGORITHM/Tools/RalphLoopExecutor.ts \
  --prompt "Implement SEC-001: Replace global state with Gradio State" \
  --completion-promise "All tests pass and no global current_agent in app.py" \
  --max-iterations 15
```

## PARALLEL OPUS AGENTS

Deploy multiple Opus agents for concurrent work using Task tool:

```python
# Pattern for parallel agent deployment
Task(
    subagent_type="general-purpose",
    model="opus",
    prompt="Implement SEC-001: Session State isolation...",
    description="Implement session isolation"
)
```

**Parallel Work Opportunities:**
- SEC-002 (injection filter) + SEC-003 (sensitive files) - independent
- UX-003 (retry logic) + UX-004 (error messages) - independent
- TEST-002 (tool tests) + TEST-003 (agent tests) - after TEST-001

## SPRINT EXECUTION PLAN

### SPRINT 1: Security Hardening [P0] - 21 points

**Objective:** Fix all P0 security vulnerabilities

**Tasks in Order:**
1. `SEC-005` - Re-run evals to establish baseline (2 pts)
2. `SEC-001` - Replace global state with Gradio State (5 pts) **CRITICAL**
3. `SEC-002` + `SEC-003` - Injection filter + Sensitive blocklist (5 pts) **PARALLEL**
4. `SEC-006` - Add LangSmith tracing (3 pts)
5. `SEC-007` - Add request timeout (2 pts)
6. `SEC-004` - Fix README metrics (1 pt)
7. `SEC-008` - Security test suite (3 pts)

**Completion Promise for Sprint 1:**
```
<promise>Sprint 1 complete: No global state in app.py, injection filter active, sensitive files blocked, README metrics accurate</promise>
```

**Verification:**
```bash
# Test session isolation
# Open two browser tabs, initialize different repos, verify isolation

# Test injection filter
python -c "from src.tools.file_explorer import sanitize_content; print(sanitize_content('ignore previous instructions'))"

# Test sensitive file blocking
python -c "from src.tools.file_explorer import is_sensitive_file; print(is_sensitive_file('.env'))"

# Run security tests
pytest tests/test_security.py -v
```

---

### SPRINT 2: User Experience [P1] - 26 points

**Objective:** Implement streaming and error handling

**Tasks in Order:**
1. `UX-001` - Streaming responses - Agent (5 pts) **BLOCKS UX-002**
2. `UX-002` - Streaming responses - Gradio UI (5 pts)
3. `UX-003` + `UX-004` - Retry logic + Error messages (6 pts) **PARALLEL**
4. `UX-005` - Progress indicators (2 pts)
5. `UX-006` - Conversation history limit (2 pts)
6. `UX-007` - Clear chat button (1 pt)
7. `UX-008` - Model info display (1 pt)

**Completion Promise for Sprint 2:**
```
<promise>Sprint 2 complete: Streaming responses work, retry logic active, friendly error messages, progress indicators visible</promise>
```

**Verification:**
```bash
# Test streaming
python -c "
import asyncio
from src.agent import CodebaseOnboardingAgent
agent = CodebaseOnboardingAgent('.')
async def test():
    async for event in agent.stream('What is this?'):
        print(event['type'])
asyncio.run(test())
"

# Test retry logic
# Temporarily set invalid API key, verify retries

# Test error messages
# Trigger various errors, verify friendly messages
```

---

### SPRINT 3: Eval System Overhaul [P1] - 24 points

**Objective:** Make evals measure real quality

**Tasks in Order:**
1. `EVAL-005` - Tool output capture (3 pts) **BLOCKS EVAL-001**
2. `EVAL-001` - Semantic citation verification (5 pts)
3. `EVAL-002` - Improve deep-dive prompt (3 pts)
4. `EVAL-003` - Context budget tracking (3 pts)
5. `EVAL-004` - Fix citation rate metric (3 pts)
6. `EVAL-006` - Eval report improvements (2 pts)
7. `EVAL-007` - Add monorepo test (2 pts)
8. `EVAL-008` - Adversarial test cases (3 pts)

**Completion Promise for Sprint 3:**
```
<promise>Sprint 3 complete: Citations semantically verified, deep-dive pass rate >80%, context budget prevents overflow, metrics use precision/recall/F1</promise>
```

**Verification:**
```bash
# Run full eval suite
python run_multi_eval.py

# Check new metrics
python -c "
import json
with open('evals/multi_repo_results.json') as f:
    results = json.load(f)
    print(f'Pass rate: {results[\"summary\"][\"tests_passed\"]}/{results[\"summary\"][\"total_tests\"]}')
"

# Generate report
python generate_report.py
```

---

### SPRINT 4: Testing Infrastructure [P2] - 18 points

**Objective:** Real tests that gate PRs

**Tasks in Order:**
1. `TEST-001` - Create test directory structure (2 pts) **BLOCKS ALL**
2. `TEST-002` + `TEST-003` - Tool tests + Agent tests (9 pts) **PARALLEL**
3. `TEST-004` - Fix CI pipeline (2 pts)
4. `TEST-005` - Pre-commit hooks (1 pt)
5. `TEST-006` - Coverage badge (1 pt)
6. `TEST-007` - E2E test with real API (2 pts)

**Completion Promise for Sprint 4:**
```
<promise>Sprint 4 complete: Unit tests exist with >70% coverage, CI pipeline gates PRs, all tests pass</promise>
```

**Verification:**
```bash
# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Verify CI would pass
ruff check src/ app.py
ruff format --check src/ app.py
```

---

## CRITICAL RULES

### Before Each Task:
1. **READ** the task from `Plans/BACKLOG.md`
2. **CHECK** dependencies are complete
3. **READ** relevant source files before modifying
4. **TEST** after implementing

### After Each Task:
1. **UPDATE** `Plans/BACKLOG.md` - mark task complete
2. **UPDATE** `Plans/PRD.md` if requirements changed
3. **RUN** relevant tests
4. **COMMIT** with descriptive message

### Testing Protocol:
```bash
# After each file change:
python -c "import src.agent; print('Import OK')"

# After each feature:
pytest tests/test_<feature>.py -v

# After each sprint:
pytest tests/ -v --cov=src
python run_multi_eval.py
```

### Git Protocol:
```bash
# After each task:
git add <specific files>
git commit -m "feat(SEC-001): Replace global state with Gradio session state

- Removed global current_agent dict from app.py
- Added gr.State() for per-session storage
- Updated all handler functions to use state parameter
- Tested with concurrent sessions

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

## PARALLEL AGENT DEPLOYMENT TEMPLATE

When ready to parallelize work, use this pattern:

```python
# Deploy 3 Opus agents in parallel
Task(
    subagent_type="general-purpose",
    model="opus",
    prompt="""
    Implement SEC-002: Prompt Injection Filter

    Location: src/tools/file_explorer.py

    Tasks:
    1. Add INJECTION_PATTERNS constant
    2. Implement sanitize_content() function
    3. Integrate into read_file() tool
    4. Create tests/test_security.py with injection tests

    Technical spec from Plans/BACKLOG.md:SEC-002

    Test with: pytest tests/test_security.py::TestInjectionFilter -v
    """,
    description="Implement injection filter"
)

Task(
    subagent_type="general-purpose",
    model="opus",
    prompt="""
    Implement SEC-003: Sensitive File Blocklist

    Location: src/tools/file_explorer.py

    Tasks:
    1. Add SENSITIVE_FILES constant
    2. Add SENSITIVE_EXTENSIONS constant
    3. Implement is_sensitive_file() function
    4. Integrate into read_file() tool
    5. Add tests to tests/test_security.py

    Technical spec from Plans/BACKLOG.md:SEC-003

    Test with: pytest tests/test_security.py::TestSensitiveFiles -v
    """,
    description="Implement sensitive file blocklist"
)
```

## ISC (IDEAL STATE CRITERIA)

Track progress with ISC:

| # | Ideal State | Status | Verified |
|---|-------------|--------|----------|
| 1 | No global state in app.py | PENDING | |
| 2 | Injection patterns filtered | PENDING | |
| 3 | Sensitive files blocked | PENDING | |
| 4 | README metrics accurate | PENDING | |
| 5 | Streaming responses work | PENDING | |
| 6 | Retry logic handles transient errors | PENDING | |
| 7 | Error messages user-friendly | PENDING | |
| 8 | Citations semantically verified | PENDING | |
| 9 | Deep-dive pass rate >80% | PENDING | |
| 10 | Unit test coverage >70% | PENDING | |
| 11 | CI pipeline gates PRs | PENDING | |
| 12 | All evals pass at >90% | PENDING | |

## FINAL VERIFICATION

After all sprints complete:

```bash
# Full test suite
pytest tests/ -v --cov=src --cov-report=html

# Full eval suite
python run_multi_eval.py

# Generate final report
python generate_report.py

# Verify no regressions
cat evals/multi_repo_results.json | jq '.summary'

# Security audit
grep -r "current_agent\s*=" app.py  # Should find nothing
python -c "from src.tools.file_explorer import INJECTION_PATTERNS; print(len(INJECTION_PATTERNS))"
python -c "from src.tools.file_explorer import SENSITIVE_FILES; print(len(SENSITIVE_FILES))"
```

**Final Completion Promise:**
```
<promise>Implementation complete: All 32 tasks done, test coverage >70%, eval pass rate >90%, zero security vulnerabilities, documentation updated</promise>
```

---

## START HERE

1. Read the three plan documents:
   ```bash
   cat Plans/IMPROVEMENT_PLAN.md
   cat Plans/PRD.md
   cat Plans/BACKLOG.md
   ```

2. Initialize THE ALGORITHM:
   ```bash
   bun run ~/.claude/skills/THEALGORITHM/Tools/AlgorithmDisplay.ts start DETERMINED -r "Implement Codebase-Onboarding-Agent v2.0"
   ```

3. Run baseline evals (SEC-005):
   ```bash
   python run_multi_eval.py
   cp evals/multi_repo_results.json evals/baseline_$(date +%Y%m%d).json
   ```

4. Begin Sprint 1, Task SEC-001 (session isolation)

5. Iterate with RALPH until each task's completion promise is met

6. Update BACKLOG.md after each task

7. Run tests after each sprint

**GO!**
