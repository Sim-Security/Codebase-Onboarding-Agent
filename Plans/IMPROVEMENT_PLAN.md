# Codebase-Onboarding-Agent: Comprehensive Improvement Plan

**Generated:** 2026-01-29
**Methodology:** THE ALGORITHM (DETERMINED mode) + Council Debate + RedTeam Analysis
**Analysis Scope:** Full codebase deep dive with 3 Opus agents + multi-perspective debate

---

## Executive Summary

This plan synthesizes findings from:
1. **Codebase Exploration** - Architecture, tools, evals, performance patterns
2. **Council Debate** - 4 expert perspectives (AI/ML, Performance, UX, DevOps)
3. **RedTeam Analysis** - Adversarial critique finding blind spots and vulnerabilities

**Current State:** The agent has a sound architectural foundation (tool-first > RAG) but suffers from:
- **Critical security vulnerabilities** (P0): Global state corruption, prompt injection risk
- **Misleading metrics** (P0): 96.7% claim vs 73.3% reality, false "0% hallucination" claim
- **Poor user experience** (P1): Synchronous blocking, no streaming, weak error handling
- **Eval methodology gaps** (P1): Syntactic checks, no semantic verification

---

## Part 1: What's Good (Keep These)

| Component | Why It Works | Location |
|-----------|--------------|----------|
| **Tool-first architecture** | LLM reasoning + deterministic tools beats RAG for code understanding | `src/agent.py:55-151` |
| **8 well-designed tools** | Cover core exploration needs, stateless, predictable | `src/tools/` |
| **Anti-hallucination prompts** | Explicit grounding rules, citation requirements | `src/prompts/__init__.py` |
| **Multi-repo eval suite** | Tests across 10 repos, 5 languages - more than most similar projects | `run_multi_eval.py` |
| **Cost-effective defaults** | Free models, no vector DB, $0 operation | Throughout |
| **Shallow cloning** | `--depth=1` reduces clone time significantly | `app.py:53` |
| **Docker hardening** | Multi-stage build, non-root user, health checks | `Dockerfile` |

---

## Part 2: Critical Issues (P0 - Fix Immediately)

### Issue 2.1: Global State Corruption (Concurrency)

**Problem:** The Gradio app uses a global `current_agent` dictionary that will corrupt when multiple users interact simultaneously.

**Evidence:**
```python
# app.py:74-75
current_agent = {"agent": None, "repo_path": None}
```

**Impact:** User A's queries execute against User B's repository. Complete chaos in production.

**Fix:**
```python
# Option A: Gradio State (Recommended)
def initialize_agent(repo_url, api_key, model, state):
    # Use gr.State() for per-session storage
    state["agent"] = agent
    return state

# Option B: Session-based dictionary
import uuid
sessions = {}
session_id = str(uuid.uuid4())
sessions[session_id] = {"agent": agent, "repo_path": repo_path}
```

**Location:** `app.py:74-75, 119-120, 145, 162`

---

### Issue 2.2: Prompt Injection via Repository Contents

**Problem:** Agent reads arbitrary file contents and passes them directly to LLM without sanitization.

**Evidence:**
```python
# src/tools/file_explorer.py:178-182
with open(path, "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
# Content passed directly to LLM - no filtering
```

**Impact:** Malicious repo could include `# IGNORE ALL PREVIOUS INSTRUCTIONS` in code comments.

**Fix:**
```python
# Add content sanitization
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(all\s+)?previous",
    r"system\s*:\s*you\s+are",
    # ... more patterns
]

def sanitize_content(content: str) -> str:
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return "[CONTENT FILTERED - Potential injection detected]"
    return content
```

**Location:** `src/tools/file_explorer.py:178-182`

---

### Issue 2.3: False Metrics in README

**Problem:** README claims "0% hallucination rate" and "96.7% pass rate" but actual data shows:
- 2/10 repos had hallucinations (zustand→Redux, langchain→Express)
- 22/30 tests passed = 73.3%, not 96.7%
- 8/10 repos had at least one failure

**Evidence:** `evals/multi_repo_results.json:5-8`
```json
"repos_passed": 2,
"repos_failed": 8,
"tests_passed": 22,
"tests_failed": 8
```

**Impact:** Undermines credibility of the entire project.

**Fix:**
1. Re-run evals with latest code
2. Update README with accurate metrics:
   - "73.3% individual test pass rate (22/30)"
   - "X% hallucination rate (varies by run)"
3. Add date of last eval run
4. Consider reporting repo-level pass rate separately

**Location:** `README.md`, `evals/multi_repo_results.json`

---

## Part 3: High Priority Issues (P1)

### Issue 3.1: No Streaming Responses

**Problem:** `agent.invoke()` blocks for 10-30 seconds with no progress indication.

**Evidence:**
```python
# src/agent.py:190
result = self.agent.invoke(state)  # Blocking call
```

**Impact:** Users stare at blank screen, poor perceived performance.

**Council Consensus:** Top priority (Marcus + Priya champion)

**Fix:**
```python
# src/agent.py - Add streaming support
async def _stream(self, initial_state: dict):
    async for event in self.agent.astream(initial_state):
        if "messages" in event:
            yield event["messages"][-1].content

# app.py - Use Gradio streaming
def chat_stream(message, history, state):
    for chunk in agent.stream(message):
        yield chunk
```

**Location:** `src/agent.py:181-216`, `app.py:153-164`

---

### Issue 3.2: Deep-Dive Questions Fail 60% of the Time

**Problem:** When users ask follow-up questions, 6/10 repos return 0 citations.

**Evidence:** From `multi_repo_results.json`:
- flask deep_dive: citations=0
- click deep_dive: citations=0
- express deep_dive: citations=0
- gin deep_dive: citations=0
- cobra deep_dive: citations=0
- ripgrep deep_dive: citations=0

**Impact:** The actual use case (asking questions) fails more often than the demo (overview).

**Fix:**
1. Improve `DEEP_DIVE_PROMPT` to enforce tool usage:
```python
DEEP_DIVE_PROMPT = """
BEFORE answering, you MUST:
1. Call list_directory_structure to find relevant files
2. Call search_code to find related code
3. Call read_file on at least 2 relevant files
4. Only then provide your answer with file:line citations

If you answer without calling tools, your response is INVALID.
"""
```

2. Add tool-call validation in agent loop:
```python
if not state.get("tool_calls") and "deep_dive" in prompt_type:
    return {"error": "Agent must use tools before answering"}
```

**Location:** `src/prompts/__init__.py:75-91`, `src/agent.py`

---

### Issue 3.3: No Semantic Correctness Verification

**Problem:** Evals check if citations exist but not if they're accurate.

**Evidence:**
```python
# run_evals.py:39-43
def count_citations(text: str) -> int:
    pattern = r'[a-zA-Z0-9_/.-]+\.(py|ts|js|...):\d+'
    return len(re.findall(pattern, text))
# Only counts format, not accuracy
```

**Impact:** Agent could cite `app.py:42` but line 42 might be a comment or unrelated code.

**Council Consensus:** Tool-output-to-claim verification (Elena + Jordan)

**Fix:**
```python
def verify_citation(citation: str, tool_outputs: list[str]) -> bool:
    """Verify cited file:line was actually read."""
    file_path, line_num = citation.rsplit(":", 1)
    for output in tool_outputs:
        if f"--- {file_path} ---" in output:
            lines = output.split("\n")
            for line in lines:
                if line.startswith(f"{line_num}:") or f" {line_num}|" in line:
                    return True
    return False
```

**Location:** `run_evals.py`, `run_multi_eval.py`

---

### Issue 3.4: Large Repo Context Overflow

**Problem:** No limit on total context. Agent can make 50+ read_file calls, exceeding LLM limits.

**Evidence:** ripgrep deep_dive had 46 tool calls. 500 lines × 46 = 23,000 lines potential context.

**Impact:** Large repos (monorepos) will hit context limits and fail with no graceful handling.

**Fix:**
```python
# src/agent.py - Add context budget tracking
class CodebaseOnboardingAgent:
    MAX_CONTEXT_TOKENS = 100000  # Leave room for response
    context_tokens = 0

    def _track_context(self, content: str):
        # Rough estimate: 1 token ≈ 4 chars
        self.context_tokens += len(content) // 4
        if self.context_tokens > self.MAX_CONTEXT_TOKENS:
            raise ContextLimitExceeded(
                f"Context limit reached ({self.context_tokens} tokens). "
                "Try a more specific question."
            )
```

**Location:** `src/agent.py`

---

### Issue 3.5: No Observability

**Problem:** Zero instrumentation. No way to debug production issues or track performance.

**Evidence:** No metrics, tracing, or structured logging anywhere in codebase.

**Council Consensus:** Add LangSmith integration (Jordan + Marcus)

**Fix:**
```python
# app.py - Add LangSmith tracing
from langsmith import traceable

@traceable(name="generate_overview")
def generate_overview():
    ...

# Or via environment:
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=...
# LANGCHAIN_PROJECT=codebase-onboarding-agent
```

**Location:** `app.py`, `.env.example`

---

### Issue 3.6: Weak Error Handling

**Problem:** Users get raw exception messages. No retry logic in production (only in evals).

**Evidence:**
```python
# app.py:147
except Exception as e:
    return f"Error generating overview: {e}"
```

**Fix:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def generate_overview_with_retry():
    ...

# Better error messages
FRIENDLY_ERRORS = {
    "rate_limit": "The AI service is busy. Please try again in a moment.",
    "context_length": "This repository is too large. Try asking about a specific component.",
    "timeout": "The request timed out. Please try a simpler question.",
}
```

**Location:** `app.py:142-150`

---

## Part 4: Medium Priority Issues (P2)

### Issue 4.1: Empty Test Suite

**Problem:** CI runs `pytest tests/` but the directory doesn't exist. Tests pass with `|| true`.

**Fix:** Create actual tests:
```
tests/
├── test_tools.py         # Unit tests for 8 tools
├── test_agent.py         # Agent integration tests
├── test_prompts.py       # Prompt behavior tests
└── conftest.py           # Fixtures
```

**Location:** `tests/` (create), `.github/workflows/deploy.yml:95`

---

### Issue 4.2: Citation Rate Metric is Meaningless

**Problem:** Citation rates of 250%, 350%, 466% are mathematically nonsensical.

**Fix:** Change metric to:
```python
# Precision: What % of citations are accurate?
# Recall: What % of claims have citations?
precision = verified_citations / total_citations
recall = citations / claims
f1 = 2 * (precision * recall) / (precision + recall)
```

**Location:** `run_evals.py:60-72`

---

### Issue 4.3: No Response Caching

**Problem:** Same repo analyzed from scratch every session.

**Fix:**
```python
import hashlib
from functools import lru_cache

def get_repo_hash(repo_path: str) -> str:
    """Hash based on file structure and mtimes."""
    ...

@lru_cache(maxsize=100)
def cached_overview(repo_hash: str, model: str) -> str:
    ...
```

**Location:** `src/agent.py`

---

### Issue 4.4: Temp Directory Secrets Exposure

**Problem:** Cloned repos in `/tmp/codebase_*` may contain `.env` files readable by other processes.

**Fix:**
```python
# Add sensitive file blocklist to read_file
SENSITIVE_FILES = {".env", ".env.local", "credentials.json", "secrets.yaml"}

def read_file(file_path: str, ...):
    if Path(file_path).name in SENSITIVE_FILES:
        return "Error: Cannot read potentially sensitive file"
```

**Location:** `src/tools/file_explorer.py`

---

## Part 5: Implementation Roadmap

### Week 1: Critical Security + Metrics Fix

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| 1 | Fix global state → Gradio State | - | `app.py` updated |
| 1 | Add prompt injection filtering | - | `file_explorer.py` updated |
| 2 | Re-run full eval suite | - | Fresh `multi_repo_results.json` |
| 2 | Update README with accurate metrics | - | README updated |
| 3 | Add LangSmith tracing | - | Observability live |
| 3 | Add sensitive file blocklist | - | Security hardened |

### Week 2: User Experience

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| 1-2 | Implement streaming responses | - | `agent.py` streaming |
| 2-3 | Update Gradio to use streaming | - | `app.py` streaming UI |
| 3 | Add retry logic with tenacity | - | Error handling improved |
| 4 | Improve error messages | - | Friendly errors |

### Week 3: Eval System Overhaul

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| 1-2 | Add tool-output-to-claim verification | - | Semantic correctness check |
| 2-3 | Fix citation rate metric | - | Precision/Recall/F1 |
| 3-4 | Improve DEEP_DIVE_PROMPT | - | Better follow-up responses |
| 4 | Add context budget tracking | - | Large repo handling |

### Week 4: Testing + Polish

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| 1-2 | Create unit test suite | - | `tests/` directory |
| 2-3 | Add integration tests | - | Agent behavior tests |
| 3 | Remove `|| true` from CI | - | Real test pipeline |
| 4 | Add adversarial test cases | - | Edge case coverage |

---

## Part 6: Success Metrics (Post-Improvement)

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| **Test Pass Rate** | 73.3% (22/30) | >90% | `run_multi_eval.py` |
| **Repo Pass Rate** | 20% (2/10) | >80% | All 3 tests pass |
| **Deep-Dive Citations** | 40% have citations | >80% | Citation count > 0 |
| **Response Latency (p50)** | Unknown | <5s first token | LangSmith traces |
| **Hallucination Rate** | 20% (2/10 repos) | <5% | Eval with new verifier |
| **Unit Test Coverage** | 0% | >70% | pytest-cov |
| **Security Vulns** | 3 (global state, injection, secrets) | 0 | Manual audit |

---

## Part 7: Files to Modify

### High Priority (P0-P1)

| File | Changes | Lines Affected |
|------|---------|----------------|
| `app.py` | Global state → Gradio State, streaming, error handling | 74-75, 119-120, 142-175, 249-319 |
| `src/agent.py` | Streaming support, context budget | 181-216, new methods |
| `src/tools/file_explorer.py` | Injection filter, secrets blocklist | 178-182, new functions |
| `src/prompts/__init__.py` | Improved DEEP_DIVE_PROMPT | 75-91 |
| `run_multi_eval.py` | Semantic verification, fix metrics | 209-256, 188-205 |
| `README.md` | Accurate metrics | Throughout |
| `.env.example` | LangSmith vars | Add lines |

### Medium Priority (P2)

| File | Changes |
|------|---------|
| `tests/` | Create entire directory |
| `.github/workflows/deploy.yml` | Remove `|| true` |
| `run_evals.py` | Better claim counting |

---

## Appendix A: Council Debate Summary

**Participants:**
- Dr. Elena (AI/ML) - Championed semantic verification, eval rigor
- Marcus (Performance) - Championed streaming, parallelization
- Priya (Product/UX) - Championed error handling, user experience
- Jordan (DevOps/SRE) - Championed observability, testing

**Consensus Priorities:**
1. Streaming responses (Marcus + Priya)
2. LangSmith observability (Jordan + Marcus)
3. Tool-output-to-claim verification (Elena + Jordan)
4. Error handling with retry (Priya)
5. Actual test suite (Jordan)

**Dissent:** Marcus wanted tool parallelization but council felt streaming addressed perceived latency more directly.

---

## Appendix B: RedTeam Critical Findings

| Finding | Severity | Status |
|---------|----------|--------|
| Global state corruption | P0 | Plan: Week 1 |
| Prompt injection risk | P0 | Plan: Week 1 |
| False metrics in README | P0 | Plan: Week 1 |
| Deep-dive 60% failure rate | P1 | Plan: Week 3 |
| No semantic verification | P1 | Plan: Week 3 |
| Large repo context overflow | P1 | Plan: Week 3 |
| Temp directory secrets | P2 | Plan: Week 1 |
| Meaningless citation metric | P2 | Plan: Week 3 |

**Core Vulnerability Identified:** Agent cannot distinguish between "code the LLM read" and "code the LLM believes exists." Citation presence ≠ citation accuracy.

---

## Appendix C: Architecture Diagram (Post-Improvement)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Gradio Web Interface                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Session     │  │ Streaming   │  │ Retry + Error Handling  │ │
│  │ State       │  │ Chat UI     │  │ (tenacity)              │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Agent                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Context     │  │ Streaming   │  │ LangSmith Tracing       │ │
│  │ Budget      │  │ Support     │  │ (Observability)         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    8 Deterministic Tools                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Injection   │  │ Secrets     │  │ Result Caching          │ │
│  │ Filter      │  │ Blocklist   │  │ (LRU)                   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Evaluation System                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Semantic    │  │ Tool-Claim  │  │ Precision/Recall        │ │
│  │ Verification│  │ Matching    │  │ Metrics                 │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

**End of Improvement Plan**

*Generated by THE ALGORITHM (DETERMINED mode) with Council + RedTeam analysis*
