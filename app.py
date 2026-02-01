"""
Gradio UI for the Codebase Onboarding Agent.
Deployable to Hugging Face Spaces.
"""

# Load .env BEFORE any LangChain imports (required for LangSmith tracing)
from dotenv import load_dotenv

load_dotenv()

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import gradio as gr

from src.agent import CodebaseOnboardingAgent
from src.errors import get_friendly_error


def _get_tool_status_indicator(tool_name: str, tool_input: dict) -> str:
    """
    Generate contextual status indicator based on tool type.

    UX-002: Provides user-friendly status messages during tool execution.

    Args:
        tool_name: Name of the tool being called
        tool_input: Input arguments to the tool

    Returns:
        Formatted status string with appropriate emoji
    """
    if tool_name == "read_file":
        file_path = tool_input.get("file_path", "file")
        # Extract just the filename for cleaner display
        filename = Path(file_path).name if file_path else "file"
        return f"\n\n`📖 Reading {filename}...`"

    elif tool_name == "search_code":
        pattern = tool_input.get("pattern", "")
        return f"\n\n`🔎 Searching for '{pattern}'...`"

    elif tool_name == "find_files_by_pattern":
        pattern = tool_input.get("pattern", "")
        return f"\n\n`🔎 Finding files matching '{pattern}'...`"

    elif tool_name == "list_directory_structure":
        return "\n\n`📂 Exploring directory structure...`"

    elif tool_name == "get_imports":
        file_path = tool_input.get("file_path", "file")
        filename = Path(file_path).name if file_path else "file"
        return f"\n\n`📦 Analyzing imports in {filename}...`"

    elif tool_name == "find_entry_points":
        return "\n\n`🚀 Finding entry points...`"

    elif tool_name == "analyze_dependencies":
        return "\n\n`🔗 Analyzing dependencies...`"

    elif tool_name == "get_function_signatures":
        file_path = tool_input.get("file_path", "file")
        filename = Path(file_path).name if file_path else "file"
        return f"\n\n`📝 Getting function signatures from {filename}...`"

    elif tool_name == "get_important_files":
        return "\n\n`⭐ Identifying important files...`"

    else:
        return f"\n\n`🔍 {tool_name}...`"


# Available models - users can also type any OpenRouter model ID
MODEL_OPTIONS = [
    # Default - fast and affordable
    "x-ai/grok-4.1-fast",
    # Free models
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    # Paid but affordable
    "anthropic/claude-sonnet-4",
    "openai/gpt-4o-mini",
    "google/gemini-2.0-flash-001",
    # Premium
    "anthropic/claude-opus-4",
    "openai/gpt-4o",
]


def get_model_display(model: str, provider: str = "openrouter") -> str:
    """
    UX-008: Generate display string for model with cost indicator.

    Args:
        model: Model ID
        provider: LLM provider

    Returns:
        Display string with FREE/paid indicator
    """
    if not model:
        if provider == "groq":
            return "Llama 3.1 8B (FREE via Groq)"
        return "x-ai/grok-4.1-fast (default)"

    if ":free" in model.lower():
        return f"{model} (FREE)"

    # Known free models
    free_models = ["llama-3.1-8b-instant", "gemma-3-4b-it"]
    if any(fm in model.lower() for fm in free_models):
        return f"{model} (FREE)"

    return f"{model} (paid via {provider.title()})"


def clone_repo(repo_url: str) -> tuple[str, str]:
    """Clone a GitHub repository to a temporary directory."""
    if not repo_url:
        return None, "Please enter a GitHub repository URL"

    # Clean up URL
    repo_url = repo_url.strip()
    if not repo_url.startswith(("http://", "https://", "git@")):
        repo_url = f"https://github.com/{repo_url}"

    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="codebase_")

    try:
        # Clone with depth=1 for speed
        result = subprocess.run(
            ["git", "clone", "--depth=1", repo_url, temp_dir],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None, f"Failed to clone repository:\n{result.stderr}"

        return temp_dir, "✅ Cloned successfully to temporary directory"

    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, "Clone timed out (120s). Try a smaller repository."
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, f"Error cloning repository: {e}"


def initialize_agent(
    repo_url: str, api_key: str, model: str, state: dict, progress=gr.Progress()
) -> tuple[str, dict]:
    """Initialize the agent for a repository.

    UX-005: Uses Gradio Progress API for visual feedback during initialization.
    Uses per-session state instead of global state for session isolation.
    """
    progress(0.05, desc="Validating inputs...")

    # User MUST provide their own API key - no default to avoid chargebacks
    if not api_key or not api_key.strip():
        return (
            """❌ **API Key Required**

Please provide your own API key (it's FREE!):

**Option 1: OpenRouter (Recommended)**
1. Go to [openrouter.ai](https://openrouter.ai/)
2. Sign up (free)
3. Get your API key from Settings

**Option 2: Groq**
1. Go to [console.groq.com](https://console.groq.com/)
2. Sign up (free)
3. Get your API key

Both options are completely free with generous rate limits!""",
            state,
        )

    # Detect provider from key format
    api_key = api_key.strip()
    if api_key.startswith("gsk_"):
        provider = "groq"
    else:
        provider = "openrouter"

    # Use selected model or default
    model = model.strip() if model else None

    # Clean up previous temp directory if exists (from this session)
    if state["repo_path"] and state["repo_path"].startswith(tempfile.gettempdir()):
        shutil.rmtree(state["repo_path"], ignore_errors=True)

    progress(0.1, desc="Cloning repository...")

    # Clone the repository
    repo_path, message = clone_repo(repo_url)
    if not repo_path:
        return message, state

    progress(0.6, desc="Initializing agent...")

    try:
        agent = CodebaseOnboardingAgent(
            repo_path, api_key=api_key, model=model, provider=provider
        )
        progress(0.9, desc="Almost ready...")
        # Update session state (not global state)
        new_state = {"agent": agent, "repo_path": repo_path}

        # Get repo name for display
        repo_name = Path(repo_url.rstrip("/")).name.replace(".git", "")

        # UX-008: Use get_model_display for consistent model info
        model_display = get_model_display(model, provider)

        return (
            f"✅ Agent initialized for **{repo_name}**\n\n**Model:** {model_display}\n\n{message}\n\nYou can now:\n- Click 'Generate Overview' for a comprehensive analysis\n- Ask specific questions in the chat",
            new_state,
        )

    except Exception as e:
        shutil.rmtree(repo_path, ignore_errors=True)
        return f"❌ Failed to initialize agent: {e}", state


def generate_overview(state: dict) -> str:
    """Generate a codebase overview using session state."""
    if not state["agent"]:
        return "❌ Please initialize the agent first by entering a repository URL"

    try:
        return state["agent"].get_overview()
    except Exception as e:
        # UX-004: Use friendly error messages
        return get_friendly_error(e)


def chat(message: str, history: list, state: dict) -> str:
    """Chat with the agent about the codebase using session state."""
    if not state["agent"]:
        return "❌ Please initialize the agent first by entering a repository URL"

    if not message.strip():
        return "Please enter a question"

    try:
        return state["agent"].chat(message)
    except Exception as e:
        # UX-004: Use friendly error messages
        return get_friendly_error(e)


async def chat_stream(message: str, history: list, state: dict):
    """
    UX-002: Stream chat responses to UI for real-time display.

    Yields updated history with streaming content.
    """
    if not state.get("agent"):
        history = history + [
            {"role": "user", "content": message},
            {
                "role": "assistant",
                "content": "❌ Please initialize the agent first by entering a repository URL",
            },
        ]
        yield history
        return

    if not message.strip():
        yield history
        return

    agent = state["agent"]
    current_response = ""
    tool_status = ""

    # Add user message to history
    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": ""},
    ]

    try:
        async for event in agent.stream(message):
            if event["type"] == "token":
                current_response += event["content"]
                history[-1]["content"] = current_response + tool_status
                yield history

            elif event["type"] == "tool_start":
                tool_name = event.get("name", "tool")
                tool_input = event.get("input", {})
                # Show contextual tool status based on tool type
                tool_status = _get_tool_status_indicator(tool_name, tool_input)
                history[-1]["content"] = current_response + tool_status
                yield history

            elif event["type"] == "tool_end":
                # Clear tool status when done
                tool_status = ""
                history[-1]["content"] = current_response
                yield history

            elif event["type"] == "error":
                error_msg = event.get("content", "Unknown error")
                history[-1]["content"] = f"❌ Error: {error_msg}"
                yield history
                return

            elif event["type"] == "done":
                # Final update
                history[-1]["content"] = current_response
                yield history

    except Exception as e:
        history[-1]["content"] = f"❌ Error: {e}"
        yield history


async def overview_stream(state: dict):
    """
    UX-002: Stream overview generation for real-time display.

    Yields markdown content as it's generated.
    """
    if not state.get("agent"):
        yield "❌ Please initialize the agent first by entering a repository URL"
        return

    agent = state["agent"]
    current_content = ""
    tool_status = ""

    try:
        async for event in agent.stream_overview():
            if event["type"] == "token":
                current_content += event["content"]
                yield current_content + tool_status

            elif event["type"] == "tool_start":
                tool_name = event.get("name", "tool")
                tool_input = event.get("input", {})
                tool_status = _get_tool_status_indicator(tool_name, tool_input)
                yield current_content + tool_status

            elif event["type"] == "tool_end":
                tool_status = ""
                yield current_content

            elif event["type"] == "error":
                yield f"❌ Error: {event.get('content', 'Unknown error')}"
                return

            elif event["type"] == "done":
                yield current_content

    except Exception as e:
        yield f"❌ Error generating overview: {e}"


def reset_agent(state: dict) -> tuple[str, dict]:
    """Reset the agent and clean up session state."""
    if state["repo_path"] and state["repo_path"].startswith(tempfile.gettempdir()):
        shutil.rmtree(state["repo_path"], ignore_errors=True)

    new_state = {"agent": None, "repo_path": None}
    return "🔄 Agent reset. Enter a new repository URL to start.", new_state


def clear_chat(state: dict) -> tuple[list, dict]:
    """
    UX-007: Clear chat history without resetting the agent.

    Preserves the agent connection but clears conversation history.
    """
    if state.get("agent"):
        state["agent"].reset_conversation()
    return [], state  # Return empty chatbot history and unchanged state


# Build the Gradio interface
with gr.Blocks(title="Codebase Onboarding Agent") as app:
    # Per-session state for agent isolation (replaces global current_agent)
    agent_state = gr.State({"agent": None, "repo_path": None})

    gr.Markdown(
        """
        # 🔍 Codebase Onboarding Agent

        **Understand any codebase in minutes, not hours.**

        This agent uses intelligent tools to explore codebases - no RAG, no embeddings.
        Just smart tools + large context windows + model reasoning.

        ### How it works:
        1. Enter a public GitHub repository URL
        2. **Get your FREE API key** from [OpenRouter](https://openrouter.ai/) or [Groq](https://console.groq.com/)
        3. Select a model (free models available, or use premium for better results)
        4. Click 'Initialize' and wait for the clone
        5. Generate an overview or ask specific questions

        *Free by default • Supports any OpenRouter model • Built with LangGraph & Gradio*
        """
    )

    with gr.Row():
        with gr.Column(scale=2):
            repo_input = gr.Textbox(
                label="GitHub Repository URL",
                placeholder="https://github.com/username/repo or username/repo",
                info="Enter any public GitHub repository",
            )
        with gr.Column(scale=1):
            api_key_input = gr.Textbox(
                label="API Key (FREE)",
                placeholder="sk-or-... or gsk_...",
                type="password",
                info="Get FREE key: openrouter.ai or console.groq.com",
            )

    with gr.Row():
        with gr.Column(scale=2):
            model_input = gr.Dropdown(
                label="Model",
                choices=MODEL_OPTIONS,
                value="x-ai/grok-4.1-fast",
                allow_custom_value=True,
                info="Select a model or type any OpenRouter model ID. Models with ':free' are FREE.",
            )
        with gr.Column(scale=1):
            gr.Markdown(
                """
                **Model Guide:**
                - 🆓 `:free` models = $0 cost
                - 💰 Others = pay-per-use via OpenRouter
                - [Browse all models →](https://openrouter.ai/models)
                """
            )

    with gr.Row():
        init_btn = gr.Button("🚀 Initialize Agent", variant="primary")
        reset_btn = gr.Button("🔄 Reset", variant="secondary")

    status_output = gr.Markdown(
        value="👋 Enter a repository URL and click Initialize to get started."
    )

    gr.Markdown("---")

    with gr.Tab("📊 Overview"):
        overview_btn = gr.Button("Generate Codebase Overview", variant="primary")
        overview_output = gr.Markdown(label="Overview")

    with gr.Tab("💬 Chat"):
        chatbot = gr.Chatbot(label="Ask questions about the codebase", height=400)
        with gr.Row():
            chat_input = gr.Textbox(
                label="Your question",
                placeholder="How does authentication work? What's the database schema? Where are the API routes?",
                scale=4,
            )
            chat_btn = gr.Button("Ask", variant="primary", scale=1)
            # UX-007: Clear chat button
            clear_chat_btn = gr.Button("🗑️ Clear Chat", variant="secondary", scale=1)

    gr.Markdown(
        """
        ---
        ### Example Questions:
        - "How is the project structured?"
        - "Where is authentication handled?"
        - "What database is used and how does it connect?"
        - "Explain the main entry point"
        - "What are the key dependencies?"
        - "How do the API routes work?"
        - "Where are the tests located?"

        ---
        **Note:** This agent works best with small to medium repositories.
        Very large repositories may take longer to analyze or hit context limits.
        """
    )

    # Event handlers - all use agent_state for session isolation
    init_btn.click(
        fn=initialize_agent,
        inputs=[repo_input, api_key_input, model_input, agent_state],
        outputs=[status_output, agent_state],
    )

    reset_btn.click(
        fn=reset_agent, inputs=[agent_state], outputs=[status_output, agent_state]
    )

    # UX-002: Use streaming for overview generation
    overview_btn.click(
        fn=overview_stream, inputs=[agent_state], outputs=[overview_output]
    )

    # UX-002: Streaming chat response function
    async def respond_stream(message, history, state):
        """Streaming chat respond function using session state."""
        if not message.strip():
            yield history, "", state
            return

        # Stream the response
        async for updated_history in chat_stream(message, history, state):
            yield updated_history, "", state

    # Use streaming for chat
    chat_btn.click(
        fn=respond_stream,
        inputs=[chat_input, chatbot, agent_state],
        outputs=[chatbot, chat_input, agent_state],
    )

    chat_input.submit(
        fn=respond_stream,
        inputs=[chat_input, chatbot, agent_state],
        outputs=[chatbot, chat_input, agent_state],
    )

    # UX-007: Clear chat button handler
    clear_chat_btn.click(
        fn=clear_chat, inputs=[agent_state], outputs=[chatbot, agent_state]
    )


if __name__ == "__main__":
    # Cloud Run sets PORT env var; default to 7860 for local development
    port = int(os.environ.get("PORT", 7860))
    app.launch(server_name="0.0.0.0", server_port=port, ssr_mode=False)
