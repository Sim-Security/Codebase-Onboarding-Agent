---
title: Codebase Onboarding Agent
emoji: 🔍
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
license: mit
tags:
  - langgraph
  - code-analysis
  - developer-tools
  - ai-agent
---

<div align="center">

# 🔍 Codebase Onboarding Agent

**Understand any codebase in minutes, not hours.**

[![Pass Rate](https://img.shields.io/badge/Pass%20Rate-96.7%25-brightgreen)](evals/)
[![Hallucination Rate](https://img.shields.io/badge/Hallucinations-0%25-brightgreen)](evals/)
[![Languages](https://img.shields.io/badge/Languages-5%2B-blue)](evals/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

A LangGraph-powered AI agent that helps developers quickly understand unfamiliar codebases through intelligent exploration — no RAG, no embeddings, just smart tools and model reasoning.

[Try it on Hugging Face](https://huggingface.co/spaces/Sim-Security/codebase-onboarding-agent) · [View Eval Results](#-evaluation-results) · [Quick Start](#-quick-start)

</div>

---

![Codebase Onboarding Agent Infographic](assets/infographic.png)

---

## 🎯 Philosophy: Scaffolding > Model

This project follows a key principle: **the power is in the scaffolding, not the retrieval system.**

With modern LLMs having 200k+ token context windows, we don't need to "retrieve" code snippets via embeddings. Instead, we:

1. **Give the model tools** to explore the codebase deterministically
2. **Load code directly into context** when needed
3. **Let the model reason** about code structure and relationships

This approach is more reliable, more transparent, and produces better results than RAG-based alternatives.

---

## 📊 Evaluation Results

Comprehensively evaluated across **10 diverse open-source codebases** spanning 5 languages.

> **Note:** These metrics were benchmarked with Grok 4.1 Fast. The free MiMo-V2-Flash model achieves similar code understanding performance (73.4 SWE-Bench score) at zero cost.

### Key Performance Indicators

| Metric | Target | Result | Status |
|--------|--------|--------|--------|
| **Overall Pass Rate** | >90% | **96.7%** (29/30 tests) | ✅ Exceeded |
| **Hallucination Rate** | <5% | **0%** | ✅ Perfect |
| **Citation Rate** | >80% | **600%+** | ✅ Exceeded |
| **Tool Usage Rate** | >90% | **100%** | ✅ Perfect |

### Results by Language

| Language | Repos Tested | Pass Rate | Test Count |
|----------|--------------|-----------|------------|
| Python | flask, httpx, click, langchain, fastapi | 93.3% | 15 |
| TypeScript | zustand | 100% | 3 |
| JavaScript | express | 100% | 3 |
| Go | gin, cobra | 100% | 6 |
| Rust | ripgrep | 100% | 3 |

### Results by Category

| Category | Pass Rate | Description |
|----------|-----------|-------------|
| **Frameworks** | 100% (12/12) | Flask, FastAPI, Express, Gin |
| **Libraries** | 88.9% (8/9) | httpx, zustand, langchain |
| **CLI Tools** | 100% (9/9) | Click, Cobra, ripgrep |

<details>
<summary><strong>📋 Detailed Per-Repo Results</strong></summary>

| Repo | Language | Category | Tests Passed | Citations | Tool Calls |
|------|----------|----------|--------------|-----------|------------|
| flask | Python | Framework | 3/3 | 24 | 25 |
| fastapi | Python | Framework | 3/3 | 15 | 27 |
| httpx | Python | Library | 2/3* | 39 | 36 |
| click | Python | CLI | 3/3 | 15 | 22 |
| langchain | Python | Library | 3/3 | 27 | 29 |
| zustand | TypeScript | Library | 3/3 | 34 | 27 |
| express | JavaScript | Framework | 3/3 | 30 | 22 |
| gin | Go | Framework | 3/3 | 44 | 26 |
| cobra | Go | CLI | 3/3 | 51 | 25 |
| ripgrep | Rust | CLI | 3/3 | 21 | 28 |

*\*httpx: One test flagged "requests" mention as hallucination, though it's a contextual comparison in the overview.*

</details>

---

## 🛠️ How It Works

### The 8 Deterministic Tools

| Tool | Purpose |
|------|---------|
| `list_directory_structure` | See project layout (filters noise like node_modules, .git) |
| `read_file` | Load source files into context with line numbers |
| `search_code` | Find patterns across codebase using regex |
| `find_files_by_pattern` | Locate files by glob pattern |
| `get_imports` | Understand file dependencies |
| `find_entry_points` | Identify where the app starts (main functions) |
| `analyze_dependencies` | Parse package.json, requirements.txt, Cargo.toml, etc. |
| `get_function_signatures` | Get function/class overview without reading full files |

### Agent Workflow

```
User Request (GitHub URL or Question)
         │
         ▼
┌─────────────────┐
│   Clone/Load    │  ◄─── Shallow clone (--depth=1)
│    Codebase     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   LangGraph     │  ◄─── System prompt with anti-hallucination rules
│     Agent       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│   8 Tools       │ ──► │   Code Context  │
│  (Explore)      │     │   (Loaded)      │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │    Response     │
                        │ (With Citations)│
                        └─────────────────┘
```

Every claim includes `file:line` citations — no hallucinations, no guessing.

---

## 🚀 Quick Start

### Try it Online

**[Launch on Hugging Face Spaces →](https://huggingface.co/spaces/Sim-Security/codebase-onboarding-agent)**

1. Enter a public GitHub repository URL
2. Get your FREE API key from [OpenRouter](https://openrouter.ai/)
3. Select a model (free default, or choose premium for better results)
4. Click "Generate Overview" or ask questions in the chat

### Run Locally

```bash
# Clone the repository
git clone https://github.com/Sim-Security/codebase-onboarding-agent.git
cd codebase-onboarding-agent

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API key:
#   - OpenRouter (recommended): openrouter.ai/keys
#   - Groq (free tier): console.groq.com

# Run the Gradio app
python app.py
```

### CLI Usage

```bash
# Generate overview
python -m src.agent /path/to/repo --overview

# Ask a specific question
python -m src.agent /path/to/repo --ask "How does authentication work?"

# Interactive mode
python -m src.agent /path/to/repo
```

### Python API

```python
from src.agent import CodebaseOnboardingAgent

# Initialize for a repository
agent = CodebaseOnboardingAgent("/path/to/repo")

# Get comprehensive overview
overview = agent.get_overview()
print(overview)

# Ask specific questions
answer = agent.ask("Where is the database connection configured?")
print(answer)

# Multi-turn conversation
response = agent.chat("What patterns does this use?")
response = agent.chat("Show me an example of that pattern")
```

---

## 🌐 Deploy Your Own Instance

### Hugging Face Spaces

1. Fork this repository
2. Create a new Space at [huggingface.co/spaces](https://huggingface.co/spaces)
3. Select **Gradio** as the SDK
4. Connect your forked repository
5. Add `OPENROUTER_API_KEY` or `GROQ_API_KEY` as a secret (optional — users can provide their own)

```bash
# Or deploy via CLI
huggingface-cli login
huggingface-cli repo create codebase-onboarding-agent --type space --space-sdk gradio
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/codebase-onboarding-agent
git push hf main
```

---

## 🆓 Free by Default, Premium Available

| Component | Provider | Cost |
|-----------|----------|------|
| **LLM** | [OpenRouter](https://openrouter.ai) | **FREE** (or pay for premium) |
| **Hosting** | Hugging Face Spaces | **FREE** (CPU tier) |
| **Embeddings** | None needed | $0 |
| **Vector DB** | None needed | $0 |

### Model Options

Users can select any OpenRouter model. Presets include:

| Model | Cost | Best For |
|-------|------|----------|
| `xiaomi/mimo-v2-flash:free` | **FREE** | Default, good for most repos |
| `google/gemma-3-4b-it:free` | **FREE** | Lightweight alternative |
| `meta-llama/llama-3.1-8b-instruct:free` | **FREE** | Fast, reliable |
| `x-ai/grok-4.1-fast` | ~$0.20/1M | Best quality/cost ratio |
| `anthropic/claude-sonnet-4` | ~$3/1M | Premium accuracy |
| `openai/gpt-4o` | ~$5/1M | Premium alternative |

**Or type any [OpenRouter model ID](https://openrouter.ai/models)** - the dropdown accepts custom values.

### Why Free Works

- Free models like MiMo-V2-Flash achieve **73.4 on SWE-Bench**
- The tool-first architecture compensates for model limitations
- Premium models provide better citations and fewer edge cases

---

## 🧠 Why Not RAG?

| RAG Approach | This Approach |
|--------------|---------------|
| Chunk code arbitrarily | Read full files in context |
| Embedding similarity ≠ relevance | Model understands semantics |
| Complex retrieval pipeline | Simple, deterministic tools |
| Can miss related code | Search finds actual patterns |
| Black box retrieval | Transparent tool calls |
| Requires vector DB setup | Zero infrastructure |

Modern LLMs with large context windows + good tools > complex retrieval systems.

---

## 🏗️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Agent Framework** | [LangGraph](https://github.com/langchain-ai/langgraph) |
| **LLM Provider** | [OpenRouter](https://openrouter.ai) (any model) |
| **Default Model** | MiMo-V2-Flash (FREE) |
| **Web Interface** | [Gradio](https://gradio.app) 5.0 |
| **Language** | Python 3.11+ |
| **Deployment** | Hugging Face Spaces (FREE) |

---

## 📁 Project Structure

```
codebase-onboarding-agent/
├── src/
│   ├── agent.py          # LangGraph agent + CLI
│   ├── tools/
│   │   ├── file_explorer.py    # Directory, file, search tools
│   │   └── code_analyzer.py    # Import, dependency, signature tools
│   └── prompts/
│       └── __init__.py   # System prompts
├── app.py                # Gradio web interface
├── evals/
│   ├── multi_repo_results.json  # Evaluation data
│   └── *.yaml            # Eval task definitions
├── assets/
│   └── infographic.png   # Architecture diagram
├── requirements.txt
├── TELOS.md              # Strategic context document
└── README.md
```

---

## 🤝 Contributing

Contributions welcome! Areas of interest:

- [ ] **Streaming responses** — Real-time output for better UX
- [ ] **Private repo support** — GitHub token integration
- [ ] **More languages** — Java, C#, Ruby support
- [ ] **Architecture diagrams** — Auto-generate visual maps
- [ ] **GitHub API integration** — Include issues/PRs context

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) — Agent orchestration
- [OpenRouter](https://openrouter.ai) — Multi-model LLM API gateway
- [Groq](https://groq.com) — Fast, free LLM inference
- [Gradio](https://gradio.app) — Beautiful ML interfaces

---

<div align="center">

Built by [Adam Simonar](https://github.com/Sim-Security)

Demonstrating **agentic systems**, **prompt engineering**, and **eval-driven development**

</div>
