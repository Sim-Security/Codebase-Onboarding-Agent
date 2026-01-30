# Product Requirements Document (PRD)
# Codebase Onboarding Agent v3.0

**Document Version:** 3.0
**Created:** 2026-01-29
**Updated:** 2026-01-29
**Status:** Draft - Pending Approval

---

## 1. Executive Summary

### 1.1 Product Vision

Transform the Codebase Onboarding Agent from a "dumb tool executor" into an **intelligent code explorer** that prioritizes important files, understands codebase architecture, and provides verified, grounded answers.

### 1.2 The Core Problem (V3 Focus)

> "The agent reads fairly pointless files like `__init__.py` and doesn't find useful things."

The current agent has tools, but lacks **intelligence** about:
- **What files are important** - Reads random files instead of architectural core
- **When to stop exploring** - Tool thrashing: 30-46 calls with 0 useful citations
- **What it already knows** - No working memory across tool calls
- **When answers are wrong** - Citation verification is broken

### 1.3 V3 Improvement Themes

| Theme | Problem | Solution |
|-------|---------|----------|
| **Smart File Discovery** | Reads `__init__.py` instead of core modules | Import graph analysis + file importance scoring |
| **Architecture Detection** | Doesn't understand project structure | Pattern detection for MVC, monorepo, etc. |
| **Tool Orchestration** | Random tool usage, thrashing | Plan-then-Execute pattern + circuit breakers |
| **Working Memory** | Forgets what it explored | Structured memory across tool calls |
| **Self-Correction** | Continues when stuck | Reflection checkpoints + off-track detection |
| **Citation Verification** | Soft verification passes invalid citations | Content-based semantic verification |

### 1.4 Success Metrics (OKRs)

| Objective | Key Result | Current | Target |
|-----------|------------|---------|--------|
| **Smarter Exploration** | Files read that are "important" (in import graph top 20) | ~30% | >70% |
| | Tool calls before useful answer | 15-46 | <10 |
| | `__init__.py` reads per session | 5-10 | 0-1 |
| **Better Answers** | Deep-dive pass rate | 40% | >85% |
| | Citation precision (verified/total) | Unknown | >90% |
| | Citation recall (cited claims/total claims) | Unknown | >70% |
| **Fewer Failures** | Tool thrashing incidents (>20 calls, 0 citations) | 8/10 repos | <1/10 repos |
| | Context overflow errors | Common | Graceful degradation |

---

## 2. Research Findings Summary

### 2.1 RedTeam Analysis (Adversarial Critique)

**Devastating Findings:**
- Claimed 96.7% pass rate is fabricated (actual: 73.3%)
- Citation verification has "soft verification" flaw - marks valid even when line not found
- Tool thrashing pattern: 30-46 tool calls producing 0 citations
- Security vulnerabilities: symlink escape, regex injection, bypassable prompt injection
- Test repos are artificially simple

### 2.2 Council Debate (Expert Perspectives)

**Prioritized Improvements:**
1. **AI/ML Engineering:** Fix eval metrics first - can't improve what you can't measure
2. **DevOps/SRE:** Add observability before scaling
3. **Performance:** Implement concurrent tool execution + caching
4. **Product/UX:** Citation enforcement at code level

### 2.3 Research Agents

**Claude Code Architecture:**
- Uses tool-based exploration (Glob, Grep, Read)
- No pre-indexing, explores on-demand
- LLM-driven navigation decisions

**File Prioritization Techniques:**
- Import graph centrality (PageRank-like)
- Git history analysis (frequently edited = important)
- File naming conventions (main.py > utils.py > __init__.py)
- Multi-signal importance scoring

**LangGraph Patterns:**
- Plan-and-Execute hybrid for complex tasks
- Tool routing rules (search before read)
- Working memory across tool calls
- Reflection checkpoints for self-correction
- Off-track detection heuristics

**Code Intelligence Systems:**
- LSP provides go-to-definition, find-references
- AST-based analysis with tree-sitter
- Semantic search beyond keyword matching

---

## 3. Functional Requirements

### 3.1 Epic: Smart File Discovery [P0 - V3 Core]

---

#### FR-SMART-001: File Importance Scoring

**As a** user exploring an unfamiliar codebase,
**I want** the agent to prioritize important files,
**So that** I understand the architecture without wading through boilerplate.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | Import graph built for repo | `grep -c "build_import_graph" src/tools/` |
| 2 | Files scored by centrality (in-degree) | `grep -c "calculate.*centrality\|in_degree" src/tools/` |
| 3 | High-importance files read first | Integration test |
| 4 | `__init__.py` marked as low priority | `grep -c "__init__.*low\|skip.*__init__" src/tools/` |
| 5 | Importance scores visible in overview | Manual check |

**Technical Approach:**
```python
class FileImportanceAnalyzer:
    """Score files by structural importance."""

    def __init__(self, repo_path: str):
        self.import_graph = self._build_import_graph(repo_path)
        self.scores = self._calculate_scores()

    def _build_import_graph(self, repo_path: str) -> dict:
        """Build graph of which files import which."""
        # Parse imports from Python, TypeScript, etc.
        pass

    def _calculate_scores(self) -> dict[str, float]:
        """Calculate importance using multiple signals."""
        scores = {}
        for file in self.import_graph:
            scores[file] = (
                0.4 * self._centrality_score(file) +
                0.25 * self._naming_score(file) +
                0.2 * self._size_score(file) +
                0.15 * self._git_activity_score(file)
            )
        return scores

    def get_top_files(self, n: int = 20) -> list[str]:
        """Return most important files to read first."""
        return sorted(self.scores.items(), key=lambda x: -x[1])[:n]
```

---

#### FR-SMART-002: Trivial File Skip List

**As a** user,
**I want** the agent to skip reading trivial files,
**So that** context isn't wasted on boilerplate.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | TRIVIAL_FILES constant defined | `grep -c "TRIVIAL_FILES" src/tools/` |
| 2 | `__init__.py` with <10 lines skipped | Unit test |
| 3 | Re-export `index.ts` files skipped | Unit test |
| 4 | Generated files detected and skipped | `grep -c "is_generated" src/tools/` |
| 5 | Skip decision logged | `grep -c "skipping.*trivial" src/tools/` |

**Technical Approach:**
```python
TRIVIAL_FILES = {
    "__init__.py": lambda content: len(content.strip().split('\n')) < 10,
    "index.ts": lambda content: is_reexport_only(content),
    "index.js": lambda content: is_reexport_only(content),
}

GENERATED_FILE_MARKERS = [
    "DO NOT EDIT", "AUTO-GENERATED", "@generated",
    "Generated by", "This file was automatically generated",
]

def should_skip_file(path: str, content: str) -> tuple[bool, str]:
    """Check if file should be skipped as trivial."""
    filename = Path(path).name

    # Check trivial patterns
    if filename in TRIVIAL_FILES:
        if TRIVIAL_FILES[filename](content):
            return True, f"Trivial {filename}"

    # Check generated markers
    header = content[:500]
    for marker in GENERATED_FILE_MARKERS:
        if marker.lower() in header.lower():
            return True, f"Generated file"

    return False, ""
```

---

#### FR-SMART-003: Architecture Pattern Detection

**As a** user,
**I want** the agent to identify the project's architecture,
**So that** I understand how components relate.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | Architecture patterns detected (MVC, monorepo, etc.) | `grep -c "detect_architecture" src/tools/` |
| 2 | Pattern reported in overview | Manual check |
| 3 | Layer boundaries identified | For MVC, models/views/controllers |
| 4 | Entry points clearly marked | Integration test |

**Detectable Patterns:**
- MVC: `models/`, `views/`, `controllers/`
- Monorepo: Multiple `package.json`, `lerna.json`, `nx.json`
- Clean/Hexagonal: `domain/`, `infrastructure/`, `application/`
- Frontend SPA: `src/components/`, `src/pages/`, router config
- Serverless: `serverless.yml`, `functions/`

---

### 3.2 Epic: Intelligent Tool Orchestration [P0 - V3 Core]

---

#### FR-ORCH-001: Plan-Then-Execute Pattern

**As a** user asking complex questions,
**I want** the agent to plan its exploration,
**So that** it doesn't waste context on random searches.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | Planning phase before deep exploration | `grep -c "create.*plan\|exploration_plan" src/agent.py` |
| 2 | Plan visible in response | Manual check |
| 3 | Plan adapts based on findings | Integration test |
| 4 | Complex questions use planning | Deep-dive eval |

**Technical Approach:**
```python
async def explore_with_plan(self, question: str):
    """Plan exploration before executing."""

    # Phase 1: Create plan
    plan = await self._create_exploration_plan(question)
    # Returns: ["1. Search for auth-related files",
    #          "2. Read authentication.py",
    #          "3. Trace auth flow from entry point"]

    # Phase 2: Execute with checkpoints
    findings = []
    for step in plan:
        result = await self._execute_step(step)
        findings.append(result)

        # Checkpoint: Do we need to adjust plan?
        if self._should_adjust_plan(findings, plan):
            plan = await self._adjust_plan(plan, findings)

    # Phase 3: Synthesize
    return self._synthesize_answer(question, findings)
```

---

#### FR-ORCH-002: Tool Routing Rules

**As a** user,
**I want** the agent to use tools efficiently,
**So that** it doesn't thrash between tools randomly.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | Search before read rule enforced | `grep -c "search.*before.*read\|prereq" src/agent.py` |
| 2 | Directory listing first for overview | Integration test |
| 3 | Tool chain validation | Unit test |
| 4 | Inefficient chains warned | Logging check |

**Tool Routing Rules:**
```python
TOOL_ROUTING_RULES = {
    "read_file": {
        "prerequisites": ["search_code", "find_files_by_pattern", "list_directory_structure"],
        "min_prerequisite_count": 1,
        "message": "Search for relevant files before reading them directly."
    },
    "get_function_signatures": {
        "prerequisites": ["list_directory_structure"],
        "min_prerequisite_count": 1,
        "message": "Understand project structure before diving into signatures."
    }
}
```

---

#### FR-ORCH-003: Tool Thrashing Circuit Breaker

**As a** user,
**I want** the agent to detect when it's stuck,
**So that** it stops wasting context and asks for clarification.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | Tool call budget (max 20 per question) | `grep -c "MAX_TOOL_CALLS\|tool.*budget" src/agent.py` |
| 2 | Repetitive pattern detection | `grep -c "thrashing\|repetitive" src/agent.py` |
| 3 | Graceful exit when stuck | Integration test |
| 4 | "I couldn't find X" instead of more thrashing | Manual check |

**Technical Approach:**
```python
class ToolUsageTracker:
    MAX_CALLS_PER_TOOL = 10
    MAX_TOTAL_CALLS = 25

    def check_thrashing(self) -> tuple[bool, str]:
        """Detect if we're stuck in a loop."""
        recent = self.call_history[-5:]

        # Same tool 3+ times in last 5 calls
        if len(recent) >= 5:
            tools = [c["name"] for c in recent]
            for tool in set(tools):
                if tools.count(tool) >= 3:
                    return True, f"Repetitive use of {tool}"

        # No new information in last 5 calls
        if self._no_new_info_in_recent(5):
            return True, "No new information being discovered"

        return False, ""
```

---

### 3.3 Epic: Working Memory [P0 - V3 Core]

---

#### FR-MEM-001: Structured Working Memory

**As a** user in a multi-turn conversation,
**I want** the agent to remember what it explored,
**So that** it doesn't re-read files or forget findings.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | WorkingMemory class implemented | `grep -c "class WorkingMemory" src/agent.py` |
| 2 | Files read tracked | `grep -c "files_read" src/agent.py` |
| 3 | Confirmed facts stored with citations | `grep -c "confirmed_facts" src/agent.py` |
| 4 | Memory persists across tool calls | Integration test |
| 5 | Memory summarized when large | `grep -c "summarize.*memory" src/agent.py` |

**Technical Approach:**
```python
@dataclass
class WorkingMemory:
    """Structured memory for exploration session."""

    # Project understanding
    project_type: Optional[str] = None
    primary_language: Optional[str] = None
    architecture_pattern: Optional[str] = None

    # What we've discovered
    key_files: list[dict] = field(default_factory=list)  # {path, importance, summary}
    confirmed_facts: list[dict] = field(default_factory=list)  # {fact, citation}

    # What we've explored (avoid re-reading)
    files_read: set[str] = field(default_factory=set)
    searches_performed: list[dict] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Convert to string for LLM context."""
        pass

    def add_fact(self, fact: str, citation: str):
        """Add confirmed fact with citation."""
        self.confirmed_facts.append({"fact": fact, "citation": citation})
```

---

#### FR-MEM-002: File Read Cache

**As a** user,
**I want** the agent to not re-read the same file,
**So that** context isn't wasted on duplicates.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | File content cached after first read | `grep -c "file_cache\|cache.*file" src/agent.py` |
| 2 | Cache hit returns cached content | Unit test |
| 3 | Cache respects context budget | `grep -c "cache.*evict\|LRU" src/agent.py` |
| 4 | Cache stats available | `grep -c "cache_hits\|cache_misses" src/agent.py` |

---

### 3.4 Epic: Self-Correction [P1]

---

#### FR-SELF-001: Reflection Checkpoints

**As a** user,
**I want** the agent to evaluate its progress,
**So that** it changes strategy when stuck.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | Reflection after every N tool calls | `grep -c "reflection\|checkpoint" src/agent.py` |
| 2 | "Am I making progress?" evaluation | Integration test |
| 3 | Strategy pivot when needed | Integration test |
| 4 | Reflection logged | Logging check |

**Reflection Prompt:**
```
Evaluate your recent exploration:

QUESTION: {question}
ACTIONS TAKEN: {last_5_tool_calls}
CURRENT FINDINGS: {working_memory}

Reflect on:
1. Am I making progress toward answering the question?
2. Have I been repeating similar actions without new insights?
3. Is there a more direct approach I'm missing?
4. Do I have enough information to answer now?

Recommended action: CONTINUE | PIVOT | SYNTHESIZE | ASK_USER
```

---

#### FR-SELF-002: Off-Track Detection

**As a** user,
**I want** the agent to notice when it's gone off-topic,
**So that** it refocuses on my question.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | Scope creep detection | `grep -c "scope_creep\|off_track" src/agent.py` |
| 2 | Keyword overlap check | Unit test |
| 3 | Refocusing message | Integration test |

---

### 3.5 Epic: Citation Verification [P1]

---

#### FR-CITE-001: Semantic Citation Verification

**As a** developer trusting the eval results,
**I want** citations to be verified for content accuracy,
**So that** the pass rate reflects actual correctness.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | verify_citation checks content, not just existence | `grep -c "content.*verify\|semantic.*verify" src/eval/` |
| 2 | Line number exists in tool output | Unit test |
| 3 | File was actually read (not inferred) | Unit test |
| 4 | Claim matches cited content | LLM-as-judge |
| 5 | Verification results in eval report | JSON check |

**Current Problem:**
```python
# BROKEN: Marks as valid even when line not found
if file_path in output:
    result["valid"] = True  # This is wrong!
```

**Fixed Approach:**
```python
def verify_citation(citation: dict, tool_outputs: list[str]) -> dict:
    """Verify citation against actual tool outputs."""
    result = {"valid": False, "file_read": False, "line_exists": False, "content_matches": False}

    for output in tool_outputs:
        # Check file was read
        if citation["file"] in output:
            result["file_read"] = True

            # Check line number exists
            line_pattern = rf'^\s*{citation["line"]}\s*\|'
            if re.search(line_pattern, output, re.MULTILINE):
                result["line_exists"] = True

                # Extract actual content at that line
                line_content = extract_line(output, citation["line"])
                result["actual_content"] = line_content

                # Only mark valid if both file read AND line exists
                result["valid"] = True

    return result
```

---

#### FR-CITE-002: Claim Grounding Verification

**As a** user,
**I want** the agent's claims to be verified against cited content,
**So that** citations actually support the claims.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | Claims extracted from response | `grep -c "extract_claims" src/eval/` |
| 2 | Claim-citation pairs matched | Unit test |
| 3 | LLM-as-judge for semantic match | `grep -c "judge\|grounding" src/eval/` |
| 4 | Grounding score in metrics | JSON check |

---

### 3.6 Epic: Security Hardening [P1]

---

#### FR-SEC-001: Symlink Escape Prevention

**As a** user analyzing untrusted repos,
**I want** symlinks to be resolved safely,
**So that** the agent can't read files outside the repo.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | path.resolve() before read | `grep -c "resolve()" src/tools/file_explorer.py` |
| 2 | Check path is within repo | `grep -c "is_relative_to\|starts_with.*repo" src/tools/` |
| 3 | Symlink attack test | Unit test |

---

#### FR-SEC-002: Improved Injection Filter

**As a** user,
**I want** prompt injection attempts to be reliably blocked,
**So that** malicious repos can't manipulate the agent.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | Unicode homoglyph detection | Unit test |
| 2 | Base64 encoded injection detection | Unit test |
| 3 | Case-insensitive patterns | Unit test |
| 4 | Character substitution handling | Unit test |
| 5 | Fuzzing test suite | `tests/test_injection_fuzz.py` |

---

### 3.7 Epic: Eval System [P1]

---

#### FR-EVAL-001: Meaningful Metrics

**As a** developer,
**I want** eval metrics that measure actual quality,
**So that** improvements are real, not cosmetic.

**Acceptance Criteria:**

| # | Criteria | Verification |
|---|----------|--------------|
| 1 | Precision: verified_citations / total_citations | `grep -c "precision" run_multi_eval.py` |
| 2 | Recall: cited_claims / total_claims | `grep -c "recall" run_multi_eval.py` |
| 3 | F1 score capped at 100% | Unit test |
| 4 | No impossible values (>200%) | JSON check |
| 5 | Historical comparison | `grep -c "baseline\|compare" run_multi_eval.py` |

---

#### FR-EVAL-002: Adversarial Test Suite

**As a** developer,
**I want** tests that stress the agent's weaknesses,
**So that** edge cases are caught before users hit them.

**Adversarial Tests:**
- Repo with confusing structure (no clear entry point)
- Repo with misleading READMEs
- Repo with injection attempts in comments
- Repo with symlinks to parent directory
- Repo with 10,000+ files (monorepo)
- Repo with non-UTF8 encoding

---

## 4. Implementation Phases

### Phase 1: Foundation (Sprint 1-2)
1. **File Importance Scoring** - Build import graph, score files
2. **Trivial File Skip List** - Stop reading `__init__.py`
3. **Working Memory** - Track what's been explored
4. **Citation Verification Fix** - Semantic verification

### Phase 2: Intelligence (Sprint 3-4)
5. **Architecture Detection** - MVC, monorepo, etc.
6. **Plan-Then-Execute** - Strategic exploration
7. **Tool Routing Rules** - Search before read
8. **Reflection Checkpoints** - Self-correction

### Phase 3: Hardening (Sprint 5-6)
9. **Thrashing Circuit Breaker** - Detect and exit loops
10. **Security Fixes** - Symlink, injection filter
11. **Adversarial Tests** - Stress testing
12. **Eval Overhaul** - Meaningful metrics

---

## 5. Verification Commands

### Smart Exploration Check
```bash
# Run agent on test repo, check file importance
python -c "
from src.tools.smart_discovery import FileImportanceAnalyzer
analyzer = FileImportanceAnalyzer('test_repo')
top_files = analyzer.get_top_files(10)
print('Top 10 important files:')
for f, score in top_files:
    print(f'  {score:.2f}: {f}')
"
```

### Tool Thrashing Check
```bash
# Run eval, check for thrashing incidents
python run_multi_eval.py
python -c "
import json
with open('evals/multi_repo_results.json') as f:
    data = json.load(f)
    thrashing = 0
    for repo in data['results']:
        tc = repo['tests']['deep_dive'].get('tool_calls', 0)
        cites = repo['tests']['deep_dive'].get('citations', 0)
        if tc > 20 and cites == 0:
            thrashing += 1
            print(f'Thrashing: {repo[\"repo\"]} - {tc} calls, {cites} citations')
    print(f'Total thrashing incidents: {thrashing}')
"
```

### Citation Verification Check
```bash
# Check that verification is semantic, not soft
python -c "
from src.eval.verification import verify_citation
# Should fail: file not read
result = verify_citation({'file': 'app.py', 'line': 42}, [])
assert result['valid'] == False, 'Should fail when file not read'

# Should fail: line doesn't exist
result = verify_citation({'file': 'app.py', 'line': 9999}, ['📄 app.py\n   1 | code'])
assert result['valid'] == False, 'Should fail when line not in output'

print('Citation verification is semantic: PASS')
"
```

---

## 6. Success Criteria (V3 Definition of Done)

| Criteria | Measurement | Target |
|----------|-------------|--------|
| Agent reads important files first | % of reads in top-20 by centrality | >70% |
| No trivial file reads | `__init__.py` reads per session | <1 |
| No tool thrashing | Incidents with >20 calls, 0 citations | <1/10 repos |
| Working memory persists | Files not re-read in session | 100% |
| Citations verified semantically | Soft verification bugs | 0 |
| Deep-dive pass rate | Eval suite | >85% |
| Hallucination rate | Eval suite | <5% |

---

*Document generated by THE ALGORITHM - DETERMINED mode analysis*
*V3 focus: Intelligent exploration over raw tool access*
