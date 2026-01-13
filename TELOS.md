# Codebase Onboarding Agent - Telos Context File

> A structured context document following [Daniel Miessler's Telos framework](https://github.com/danielmiessler/Telos).

---

## Purpose

Help developers understand unfamiliar codebases in minutes instead of hours by providing an AI agent that systematically explores code and answers questions with grounded, cited responses.

---

## Problem Statement

**P1. Developer Onboarding Friction**
- New developers waste 2-5 hours per repository figuring out structure, patterns, and entry points
- Existing documentation is often outdated or incomplete
- RAG-based solutions hallucinate or return irrelevant chunks

**P2. Code Understanding Quality**
- Generic LLM responses lack specificity (no file:line citations)
- Models infer from file names instead of reading actual code
- Example outputs in documentation get copied verbatim

---

## Mission

Provide accurate, grounded codebase analysis through deterministic tool use and rigorous instruction following - every claim backed by code the agent actually read.

---

## Goals

| ID | Goal | Priority |
|----|------|----------|
| G1 | Produce accurate codebase overviews with zero hallucinations | 1.0 |
| G2 | Cite specific file:line references for every claim | 0.5 |
| G3 | Answer deep-dive questions with code snippets | 0.25 |
| G4 | Support multiple LLM providers (OpenRouter, Groq) | 0.125 |
| G5 | Deploy to Hugging Face Spaces | 0.0625 |
| G6 | Maintain sub-$0.01 cost per analysis | 0.03125 |

*Priority follows Telos convention: each item is half as important as the previous.*

---

## KPIs

| ID | Metric | Target | Current | Status |
|----|--------|--------|---------|--------|
| K1 | Hallucination rate (false claims) | <5% | 3.3% | ✓ |
| K2 | Citation rate (claims with file:line refs) | >80% | 600%+ | ✓ |
| K3 | Tool usage rate (calls tools before answering) | >90% | 100% | ✓ |
| K4 | Multi-repo pass rate (10 diverse repos, 3 tests each) | >90% | 96.7% | ✓ |

---

## Strategies

| ID | Strategy | Addresses |
|----|----------|-----------|
| S1 | **Meta-prompting** - Apply AdamOS prompt patterns (positive framing, explicit grounding, soft tool language) | G1, G2 |
| S2 | **Tool-first architecture** - 8 deterministic tools, no RAG/embeddings | G1, G3 |
| S3 | **Model flexibility** - Support multiple providers via OpenAI-compatible API | G4, G6 |
| S4 | **Eval-driven development** - Measure pass@k, hallucination rate systematically | K1-K4 |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Agent Framework | LangGraph |
| LLM Provider | OpenRouter (default), Groq (fallback) |
| Default Model | MiMo-V2-Flash (`xiaomi/mimo-v2-flash:free`) - **FREE** |
| UI | Gradio |
| Deployment | Hugging Face Spaces |
| Language | Python 3.11+ |
| **Total Cost** | **$0** - No API costs, no chargebacks |

---

## Architecture

```
User Request
     │
     ▼
┌─────────────┐
│   Gradio    │  ◄─── Web UI / Clone repos
│    app.py   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  LangGraph  │  ◄─── Agent orchestration
│  src/agent  │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│    Tools    │ ──► │   Context   │
│  src/tools  │     │  (loaded)   │
└─────────────┘     └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Response  │
                    │ (grounded)  │
                    └─────────────┘
```

---

## Current State

### Progress (January 2026)

| Date | Milestone |
|------|-----------|
| 2026-01-12 | Initial agent implementation with Groq |
| 2026-01-13 | Added OpenRouter support, meta-prompt patterns |
| 2026-01-13 | Model comparison: Grok 4.1 > Gemini 3 > Llama 70B |
| 2026-01-13 | Created Telos context file |
| 2026-01-13 | Built eval system, ran baseline measurements |
| 2026-01-13 | **K1 achieved: 0% hallucination rate** |
| 2026-01-13 | **K2 achieved: 360% citation rate** |
| 2026-01-13 | **K3 achieved: 100% tool usage rate** (fixed tracing) |
| 2026-01-13 | **K4 achieved: 96.7% multi-repo pass rate** (10 repos tested) |

### Multi-Repo Eval Results

Tested across 10 diverse codebases:

| Language | Pass Rate | Repos |
|----------|-----------|-------|
| Python | 93.3% | flask, httpx, click, langchain, fastapi |
| TypeScript | 100% | zustand |
| JavaScript | 100% | express |
| Go | 100% | gin, cobra |
| Rust | 100% | ripgrep |

| Category | Pass Rate |
|----------|-----------|
| Framework | 100% |
| Library | 88.9% |
| CLI | 100% |

### Known Issues

1. No streaming support yet
2. Private repo support not implemented
3. One edge case: httpx overview mentions "requests" (contextual comparison)

---

## Eval Tasks (see /evals/)

| Task | Graders | Description |
|------|---------|-------------|
| `overview-accuracy` | rubric, contains | Verify overview matches actual codebase |
| `citation-rate` | regex, count | Count file:line citations vs total claims |
| `tool-usage` | trace, count | Verify tools called before final answer |
| `no-hallucination` | rubric | Expert review for false claims |

---

## Next Steps

- [x] Create eval suite and run baseline measurements
- [x] Fix K3 tool tracing (actual LangGraph calls)
- [ ] Implement streaming responses
- [ ] Deploy to Hugging Face Spaces
- [ ] Add support for private repos (GitHub token)

---

*Last updated: 2026-01-13*
