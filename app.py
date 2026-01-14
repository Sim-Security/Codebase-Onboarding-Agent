"""
Gradio UI for the Codebase Onboarding Agent.
Deployable to Hugging Face Spaces.
"""

# Load .env BEFORE any LangChain imports (required for LangSmith tracing)
from dotenv import load_dotenv
load_dotenv()

import os
import tempfile
import shutil
import subprocess
from pathlib import Path

import gradio as gr

from src.agent import CodebaseOnboardingAgent


# Available models - users can also type any OpenRouter model ID
MODEL_OPTIONS = [
    # Free models
    "xiaomi/mimo-v2-flash:free",
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    # Paid but affordable
    "x-ai/grok-4.1-fast",
    "anthropic/claude-sonnet-4",
    "openai/gpt-4o-mini",
    "google/gemini-2.0-flash-001",
    # Premium
    "anthropic/claude-opus-4",
    "openai/gpt-4o",
]


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

        return temp_dir, f"✅ Cloned successfully to temporary directory"

    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, "Clone timed out (120s). Try a smaller repository."
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None, f"Error cloning repository: {e}"


# Global state for the current agent
current_agent = {"agent": None, "repo_path": None}


def initialize_agent(repo_url: str, api_key: str, model: str) -> str:
    """Initialize the agent for a repository."""
    # User MUST provide their own API key - no default to avoid chargebacks
    if not api_key or not api_key.strip():
        return """❌ **API Key Required**

Please provide your own API key (it's FREE!):

**Option 1: OpenRouter (Recommended)**
1. Go to [openrouter.ai](https://openrouter.ai/)
2. Sign up (free)
3. Get your API key from Settings

**Option 2: Groq**
1. Go to [console.groq.com](https://console.groq.com/)
2. Sign up (free)
3. Get your API key

Both options are completely free with generous rate limits!"""

    # Detect provider from key format
    api_key = api_key.strip()
    if api_key.startswith("gsk_"):
        provider = "groq"
    else:
        provider = "openrouter"

    # Use selected model or default
    model = model.strip() if model else None

    # Clean up previous temp directory if exists
    if current_agent["repo_path"] and current_agent["repo_path"].startswith(tempfile.gettempdir()):
        shutil.rmtree(current_agent["repo_path"], ignore_errors=True)

    # Clone the repository
    repo_path, message = clone_repo(repo_url)
    if not repo_path:
        return message

    try:
        agent = CodebaseOnboardingAgent(repo_path, api_key=api_key, model=model, provider=provider)
        current_agent["agent"] = agent
        current_agent["repo_path"] = repo_path

        # Get repo name for display
        repo_name = Path(repo_url.rstrip("/")).name.replace(".git", "")

        # Determine model display name
        if model:
            model_display = model
            if ":free" in model:
                model_display += " (FREE)"
        elif provider == "groq":
            model_display = "Llama 3.1 8B (FREE)"
        else:
            model_display = "xiaomi/mimo-v2-flash:free (FREE)"

        return f"✅ Agent initialized for **{repo_name}**\n\n**Model:** {model_display}\n\n{message}\n\nYou can now:\n- Click 'Generate Overview' for a comprehensive analysis\n- Ask specific questions in the chat"

    except Exception as e:
        shutil.rmtree(repo_path, ignore_errors=True)
        return f"❌ Failed to initialize agent: {e}"


def generate_overview() -> str:
    """Generate a codebase overview."""
    if not current_agent["agent"]:
        return "❌ Please initialize the agent first by entering a repository URL"

    try:
        return current_agent["agent"].get_overview()
    except Exception as e:
        return f"❌ Error generating overview: {e}"


def chat(message: str, history: list) -> str:
    """Chat with the agent about the codebase."""
    if not current_agent["agent"]:
        return "❌ Please initialize the agent first by entering a repository URL"

    if not message.strip():
        return "Please enter a question"

    try:
        return current_agent["agent"].chat(message)
    except Exception as e:
        return f"❌ Error: {e}"


def reset_agent() -> str:
    """Reset the agent and clean up."""
    if current_agent["repo_path"] and current_agent["repo_path"].startswith(tempfile.gettempdir()):
        shutil.rmtree(current_agent["repo_path"], ignore_errors=True)

    current_agent["agent"] = None
    current_agent["repo_path"] = None

    return "🔄 Agent reset. Enter a new repository URL to start."


# Build the Gradio interface
with gr.Blocks(title="Codebase Onboarding Agent") as app:

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
                info="Enter any public GitHub repository"
            )
        with gr.Column(scale=1):
            api_key_input = gr.Textbox(
                label="API Key (FREE)",
                placeholder="sk-or-... or gsk_...",
                type="password",
                info="Get FREE key: openrouter.ai or console.groq.com"
            )

    with gr.Row():
        with gr.Column(scale=2):
            model_input = gr.Dropdown(
                label="Model",
                choices=MODEL_OPTIONS,
                value="xiaomi/mimo-v2-flash:free",
                allow_custom_value=True,
                info="Select a model or type any OpenRouter model ID. Models with ':free' are FREE."
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
        chatbot = gr.Chatbot(
            label="Ask questions about the codebase",
            height=400
        )
        with gr.Row():
            chat_input = gr.Textbox(
                label="Your question",
                placeholder="How does authentication work? What's the database schema? Where are the API routes?",
                scale=4
            )
            chat_btn = gr.Button("Ask", variant="primary", scale=1)

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

    # Event handlers
    init_btn.click(
        fn=initialize_agent,
        inputs=[repo_input, api_key_input, model_input],
        outputs=[status_output]
    )

    reset_btn.click(
        fn=reset_agent,
        inputs=[],
        outputs=[status_output]
    )

    overview_btn.click(
        fn=generate_overview,
        inputs=[],
        outputs=[overview_output]
    )

    def respond(message, history):
        if not message.strip():
            return history, ""
        response = chat(message, history)
        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response}
        ]
        return history, ""

    chat_btn.click(
        fn=respond,
        inputs=[chat_input, chatbot],
        outputs=[chatbot, chat_input]
    )

    chat_input.submit(
        fn=respond,
        inputs=[chat_input, chatbot],
        outputs=[chatbot, chat_input]
    )


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860, ssr_mode=False)
