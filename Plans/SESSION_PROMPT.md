# SESSION PROMPT: Codebase-Onboarding-Agent v2.0 Implementation

**Copy everything below this line and paste into a new Claude Code session**

---

## CONTEXT

You are implementing improvements to the **Codebase-Onboarding-Agent** project based on a comprehensive analysis performed using THE ALGORITHM (DETERMINED mode) with Council debate and RedTeam adversarial analysis.

**Project Location:** `/home/ranomis/Projects/Codebase-Onboarding-Agent`

**Branch:** `feature/v2.0-improvements` (already created)

**Key Documents (READ THESE FIRST):**
1. `Plans/IMPROVEMENT_PLAN.md` - Analysis findings from Council + RedTeam
2. `Plans/PRD.md` - Product requirements with acceptance criteria
3. `Plans/BACKLOG.md` - 32 implementation tasks with **VERIFICATION sections**

---

## ENVIRONMENT SETUP (REQUIRED FIRST)

Before implementing anything, ensure environment is configured:

```bash
# 1. Checkout feature branch
cd /home/ranomis/Projects/Codebase-Onboarding-Agent
git checkout feature/v2.0-improvements

# 2. Create/update .env file with required keys
cat > .env << 'EOF'
# Required for agent operation
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Optional: LangSmith tracing (for SEC-006)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_your-key-here
LANGCHAIN_PROJECT=codebase-onboarding-agent

# Optional: Alternative providers
GROQ_API_KEY=gsk_your-key-here
EOF

# 3. Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov tenacity

# 4. Verify setup
python -c "import src.agent; print('Setup OK')"
```

**IMPORTANT:** Do NOT proceed until `.env` has valid `OPENROUTER_API_KEY`

## EXECUTION MODE

Use **THE ALGORITHM** in **DETERMINED** mode with **RALPH Loop** for persistent iteration.

```
/skill THEALGORITHM DETERMINED MODE: Implement Codebase-Onboarding-Agent v2.0 improvements
```

---

## TASK VERIFICATION PATTERN (CRITICAL)

Every task in BACKLOG.md has a **VERIFICATION** section with 5 automated checks (V1-V5).

### How to Verify a Task

```bash
# Example: Verify SEC-002 is complete
# Run ALL verification commands from BACKLOG.md

echo "=== SEC-002 Verification ==="

# V1: INJECTION_PATTERNS constant exists
echo -n "V1 - INJECTION_PATTERNS exists: "
[ $(grep -c "INJECTION_PATTERNS\s*=" src/tools/file_explorer.py) -ge 1 ] && echo "PASS" || echo "FAIL"

# V2: At least 5 patterns defined
echo -n "V2 - At least 5 patterns: "
[ $(grep -A30 "INJECTION_PATTERNS" src/tools/file_explorer.py | grep -c 'r"') -ge 5 ] && echo "PASS" || echo "FAIL"

# ... V3, V4, V5 from BACKLOG.md
```

### Verification Rules

1. **ALL 5 checks must PASS** before marking task complete
2. **Copy verification commands** directly from BACKLOG.md
3. **If ANY check fails**, fix the implementation and re-run ALL checks
4. **Manual tests** (marked "MANUAL") require human verification

### Task Completion Workflow

```
┌─────────────────────────────────────────────────────────┐
│  1. READ task from BACKLOG.md                           │
│  2. IMPLEMENT the changes                               │
│  3. RUN all V1-V5 verification commands                 │
│     ├─ ALL PASS? → Mark complete, commit, next task     │
│     └─ ANY FAIL? → Fix implementation, goto step 3     │
│  4. RUN manual tests if specified                       │
│  5. COMMIT with task ID in message                      │
│  6. UPDATE BACKLOG.md status checkbox                   │
└─────────────────────────────────────────────────────────┘
```

---

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
1. **READ** the task from `Plans/BACKLOG.md` (including VERIFICATION section)
2. **CHECK** dependencies are complete (run their verifications)
3. **READ** relevant source files before modifying
4. **UNDERSTAND** the V1-V5 verification checks you must pass

### During Implementation:
1. **IMPLEMENT** the changes as specified
2. **TEST** after each significant change: `python -c "import src.agent; print('OK')"`
3. **ITERATE** until implementation is complete

### After Each Task:
1. **RUN** all V1-V5 verification commands from BACKLOG.md
2. **FIX** any failures and re-run ALL verifications
3. **RUN** manual tests if specified
4. **UPDATE** `Plans/BACKLOG.md` - mark status checkbox `[x]`
5. **COMMIT** with task ID in message

### Testing Protocol:
```bash
# After each file change (sanity check):
python -c "import src.agent; print('Import OK')"

# After each task (REQUIRED):
# Copy and run ALL V1-V5 commands from BACKLOG.md for that task

# After each feature (unit tests):
pytest tests/test_<feature>.py -v

# After each sprint (full suite):
pytest tests/ -v --cov=src --cov-report=term-missing
python run_multi_eval.py
```

### Git Protocol:
```bash
# After each task (ALL verifications must pass first):
git add <specific files>
git commit -m "$(cat <<'EOF'
feat(SEC-001): Replace global state with Gradio session state

- Removed global current_agent dict from app.py
- Added gr.State() for per-session storage
- Updated all handler functions to use state parameter
- All V1-V5 verifications pass

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

### When Verification Fails:
```
V3 - sanitize_content exists: FAIL
                              ^^^^
1. Identify WHICH check failed (V3 in this case)
2. Read the check to understand what's missing
3. Fix the implementation
4. Re-run ALL V1-V5 checks (not just the failed one)
5. Repeat until ALL pass
```

---

## GIT COMMIT STRATEGY

### When to Commit

| Trigger | Commit Type | Example |
|---------|-------------|---------|
| Task complete (V1-V5 pass) | `feat(TASK-ID)` | `feat(SEC-001): Replace global state` |
| Bug fix during implementation | `fix(TASK-ID)` | `fix(SEC-002): Handle edge case` |
| Test file added | `test(TASK-ID)` | `test(SEC-008): Add security tests` |
| Sprint complete | `milestone` | `milestone: Sprint 1 complete` |
| Documentation update | `docs` | `docs: Update README metrics` |

### Commit After Each Task

```bash
# ALWAYS commit after a task's V1-V5 pass
git add <specific files changed for this task>
git commit -m "$(cat <<'EOF'
feat(SEC-002): Add prompt injection filter

- Added INJECTION_PATTERNS constant with 11 patterns
- Implemented sanitize_content() function
- Integrated into read_file() tool
- V1-V5 verifications: ALL PASS

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

### Commit Message Format

```
<type>(<task-id>): <short description>

- Bullet point of what changed
- Another change
- V1-V5 verifications: ALL PASS (or specific failures fixed)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

### Sprint Milestone Commits

After completing all tasks in a sprint:

```bash
# Run sprint-level verification first
pytest tests/ -v --cov=src
python run_multi_eval.py

# Then commit milestone
git add .
git commit -m "$(cat <<'EOF'
milestone: Sprint 1 Security Hardening complete

Completed tasks:
- SEC-001: Session state isolation
- SEC-002: Prompt injection filter
- SEC-003: Sensitive file blocklist
- SEC-004: README metrics fixed
- SEC-005: Baseline evals captured
- SEC-006: LangSmith tracing
- SEC-007: Request timeout
- SEC-008: Security test suite

All sprint verification gates pass.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

### Push Strategy

```bash
# Push after each sprint completion (not after every task)
git push -u origin feature/v2.0-improvements

# Or push after significant milestones
git push
```

### DO NOT Commit When:
- V1-V5 verifications have ANY failures
- Code doesn't import cleanly
- Tests are failing
- You're in the middle of implementing a task

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

## START HERE (Step by Step)

### Step 0: Environment Setup
```bash
cd /home/ranomis/Projects/Codebase-Onboarding-Agent
git checkout feature/v2.0-improvements

# Verify .env exists with OPENROUTER_API_KEY
cat .env | grep OPENROUTER_API_KEY

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov tenacity

# Verify setup
python -c "import src.agent; print('Setup OK')"
```

### Step 1: Read Planning Documents
```bash
# Read the plan documents to understand the full scope
cat Plans/IMPROVEMENT_PLAN.md   # Analysis findings
cat Plans/PRD.md                 # Requirements
cat Plans/BACKLOG.md             # Tasks with VERIFICATION sections
```

### Step 2: Run Baseline Evals (SEC-005)
```bash
# Capture current state before making changes
python run_multi_eval.py
cp evals/multi_repo_results.json evals/baseline_$(date +%Y%m%d).json
echo "Baseline captured"
```

### Step 3: Start Sprint 1
```bash
# Begin with SEC-001: Session State Isolation
# 1. Read the task from BACKLOG.md
# 2. Read app.py to understand current implementation
# 3. Implement the changes
# 4. Run V1-V5 verifications
# 5. Commit when all pass
```

### Step 4: Task Loop (Repeat for Each Task)
```
┌────────────────────────────────────────────────┐
│ For each task in sprint:                       │
│                                                │
│ 1. READ task + VERIFICATION from BACKLOG.md   │
│ 2. READ source files to modify                 │
│ 3. IMPLEMENT changes                           │
│ 4. RUN V1-V5 verifications                     │
│    ├── ALL PASS → Continue to step 5          │
│    └── ANY FAIL → Fix and retry step 4        │
│ 5. COMMIT with task ID                         │
│ 6. UPDATE BACKLOG.md checkbox to [x]           │
│ 7. NEXT task                                   │
└────────────────────────────────────────────────┘
```

### Step 5: Sprint Completion
```bash
# After all sprint tasks complete:

# Run full test suite
pytest tests/ -v --cov=src --cov-report=term-missing

# Run evals
python run_multi_eval.py

# Commit sprint milestone
git add .
git commit -m "milestone: Sprint N complete"

# Push to remote
git push -u origin feature/v2.0-improvements
```

### Step 6: Repeat for Next Sprint

---

## TROUBLESHOOTING

### Import Errors
```bash
# If "import src.agent" fails:
python -c "import sys; print(sys.path)"  # Check path
pip install -r requirements.txt           # Reinstall deps
```

### Verification Failures
```bash
# If V1-V5 checks fail:
# 1. Read the EXACT check that failed
# 2. Understand what it's looking for
# 3. Check if your implementation matches
# 4. Common issues:
#    - Wrong file path
#    - Missing function/constant name
#    - Function exists but not called
```

### API Errors
```bash
# If API calls fail:
echo $OPENROUTER_API_KEY  # Check key is set
# Test with curl:
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

### Test Failures
```bash
# If pytest fails:
pytest tests/test_<name>.py -v --tb=long  # Verbose output
pytest tests/test_<name>.py::test_specific -v  # Single test
```

---

## QUICK REFERENCE

| Task | Read | Implement | Verify | Commit |
|------|------|-----------|--------|--------|
| SEC-001 | app.py:74-75 | Remove global, add gr.State | V1-V5 | feat(SEC-001) |
| SEC-002 | file_explorer.py | Add INJECTION_PATTERNS | V1-V5 | feat(SEC-002) |
| SEC-003 | file_explorer.py | Add SENSITIVE_FILES | V1-V5 | feat(SEC-003) |
| ... | See BACKLOG.md | ... | V1-V5 | feat(TASK-ID) |

---

**GO!**
