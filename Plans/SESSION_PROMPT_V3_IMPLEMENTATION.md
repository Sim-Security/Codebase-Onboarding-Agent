# V3 Implementation Session Prompt

**Mode:** RALPH (Run Autonomously Like a Professional Human)
**Effort:** DETERMINED (Maximum capability - Opus agents, unlimited parallel, all tools)
**Duration:** Overnight autonomous execution
**Human Intervention:** NONE until complete

---

## Instructions

You are executing THE ALGORITHM in DETERMINED mode to implement the Codebase-Onboarding-Agent V3 backlog autonomously. This is a RALPH-mode session - proceed without asking questions, make reasonable decisions, and only stop when ALL tasks are complete and verified.

## Context & Motivation

The Codebase-Onboarding-Agent currently has critical issues:
- Agent reads trivial files (`__init__.py`) instead of important ones
- Tool thrashing: 30-46 calls with 0 citations
- Eval metrics fabricated (claimed 96.7%, actual 73.3%)
- Citation verification broken (soft verification passes invalid citations)
- No working memory across tool calls

V3 transforms this from a "dumb tool executor" into an "intelligent code explorer." The principal is sleeping and expects to wake up to a COMPLETE implementation.

## Background

**Project:** `/home/ranomis/Projects/Codebase-Onboarding-Agent`
**PRD:** `Plans/PRD_V3.md` (707 lines, 7 epics, complete requirements)
**Backlog:** `Plans/BACKLOG_V3.md` (663 lines, 31 tasks, 124 story points)

### Epic Summary

| Epic | Priority | Tasks | Points |
|------|----------|-------|--------|
| Smart File Discovery | P0 | 6 | 26 |
| Intelligent Tool Orchestration | P0 | 6 | 24 |
| Working Memory | P0 | 4 | 16 |
| Self-Correction | P1 | 4 | 16 |
| Citation Verification | P1 | 4 | 18 |
| Security Hardening | P1 | 10 | 10 |
| Eval System | P1 | 4 | 14 |

---

## Execution Protocol

### Phase 1: OBSERVE
```bash
# Start Algorithm display
bun run ~/.claude/skills/THEALGORITHM/Tools/AlgorithmDisplay.ts start DETERMINED -r "Implement V3 Backlog autonomously"

# Read and internalize the requirements
Read: Plans/PRD_V3.md
Read: Plans/BACKLOG_V3.md
Read: src/agent.py
Read: src/tools/file_explorer.py
Read: src/tools/code_analyzer.py
```

### Phase 2: BUILD ISC from Backlog
Convert BACKLOG_V3.md tasks into ISC rows. Each task becomes an ISC row with:
- Description from task
- Verification method: Run the VERIFICATION commands
- Status: PENDING

### Phase 3: EXECUTE (Parallel Opus Agents)

**For EACH epic, spawn parallel Opus agents:**

```
# Example: Smart File Discovery Epic (6 tasks)
Spawn Agent 1 (Opus): SMART-001 - Build Import Graph Analyzer
Spawn Agent 2 (Opus): SMART-002 - Calculate File Importance Scores
Spawn Agent 3 (Opus): SMART-003 - Trivial File Skip List
[Wait for dependencies to complete]
Spawn Agent 4 (Opus): SMART-004 - Integrate into read_file
Spawn Agent 5 (Opus): SMART-005 - Architecture Pattern Detection
Spawn Agent 6 (Opus): SMART-006 - Smart Discovery Tool
```

**Agent Instructions Template:**
```
You are implementing task {TASK_ID} from BACKLOG_V3.md.

TASK: {task description}
FILE(S) TO CREATE/MODIFY: {files}
ACCEPTANCE CRITERIA: {criteria from backlog}

MANDATORY VERIFICATION:
After implementing, run ALL verification commands from the backlog task.
If ANY verification fails, fix the code and re-verify.
ONLY report success when ALL verifications pass.

When complete, update BACKLOG_V3.md:
- Change status from "[ ] Not Started" to "[x] Complete"
- Add completion timestamp
```

### Phase 4: VERIFY (After Each Task)

**Verification Protocol:**
1. Run ALL verification commands from the backlog task
2. If ANY fail → fix and re-run
3. Run `pytest tests/` to ensure no regressions
4. Only proceed when ALL pass

**After Each Epic:**
```bash
# Run full test suite
pytest tests/ -v --tb=short

# Run linter
ruff check src/

# Git commit the epic
git add -A
git commit -m "feat(v3): Complete {EPIC_NAME} epic

Implemented:
- {task 1}
- {task 2}
- ...

All verification commands pass.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

### Phase 5: Browser Verification

**After core implementation, verify UI:**
```
Use Browser skill to:
1. Start the Gradio app: python app.py
2. Navigate to http://localhost:7860
3. Test: Initialize agent with a test repo
4. Test: Generate overview (verify streaming works)
5. Test: Ask a question (verify citations appear)
6. Screenshot results for verification
```

---

## Decision Rules (RALPH Mode)

When encountering decisions, apply these rules WITHOUT asking:

| Situation | Decision |
|-----------|----------|
| Unclear requirement | Check PRD_V3.md first, then use most reasonable interpretation |
| Multiple implementation approaches | Choose simplest that passes all verifications |
| Test failure | Fix and re-run, do NOT skip |
| Dependency not met | Wait for dependent task to complete |
| External service unavailable | Implement with mock, add TODO for integration |
| Merge conflict | Resolve favoring the new V3 code |
| Performance concern | Implement correct first, optimize if tests pass |

---

## Completion Criteria

The session is COMPLETE when:

1. **All 31 tasks** have status `[x] Complete` in BACKLOG_V3.md
2. **All verification commands** pass for every task
3. **Full test suite** passes: `pytest tests/ -v`
4. **Linter passes**: `ruff check src/`
5. **Browser tests** confirm UI works
6. **Git commits** exist for each epic
7. **Final commit** summarizes V3 completion

---

## Final Actions

When ALL above criteria are met:

```bash
# Final test run
pytest tests/ -v --cov=src --cov-report=term

# Create V3 completion commit
git add -A
git commit -m "feat(v3): Complete V3 implementation - Intelligent Code Explorer

## Summary
- Smart File Discovery: Import graph centrality, trivial file detection
- Intelligent Tool Orchestration: Working memory, tool routing, circuit breakers
- Self-Correction: Reflection checkpoints, off-track detection
- Citation Verification: Semantic verification, claim grounding
- Security Hardening: Symlink protection, injection filter improvements
- Eval System: Meaningful P/R/F1 metrics, adversarial tests

## Metrics
- 31 tasks completed
- 124 story points delivered
- All verification commands pass
- Full test suite passes

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

# Update README with new metrics
# Run final eval to capture new baseline
python run_multi_eval.py

# Voice notification of completion
curl -s -X POST http://localhost:8888/notify \
  -H "Content-Type: application/json" \
  -d '{"message": "V3 Implementation complete. All 31 tasks done. Tests passing."}' \
  > /dev/null 2>&1 &
```

---

## Output Format

After each major milestone, output:

```
## Progress Update

**Phase:** {current phase}
**Epic:** {current epic}
**Tasks Completed:** {X}/{31}
**Current Task:** {task ID and name}
**Status:** {PASS/FAIL with details}

### Recent Completions
- [x] SMART-001: Build Import Graph Analyzer ✓
- [x] SMART-002: Calculate File Importance Scores ✓
- [ ] SMART-003: Trivial File Skip List (IN PROGRESS)

### Next Steps
1. {next action}
2. {next action}
```

---

## Emergency Protocols

**If stuck for >30 minutes on one task:**
1. Log the blocker in BACKLOG_V3.md as a comment
2. Move to next non-blocked task
3. Return to blocked task after other tasks complete

**If critical system failure:**
1. Git commit current progress: `git commit -m "WIP: V3 progress before failure"`
2. Log failure details in `Plans/V3_IMPLEMENTATION_LOG.md`
3. Continue with remaining tasks

---

## BEGIN EXECUTION

Start THE ALGORITHM now. Read the backlog, spawn agents, implement tasks, verify, commit, repeat until COMPLETE.

The principal is sleeping. When they wake up, V3 should be DONE.

**GO.**
