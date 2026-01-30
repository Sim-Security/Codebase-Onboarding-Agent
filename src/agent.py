"""
LangGraph agent for codebase onboarding.
Uses tools + context + model intelligence (no RAG).
Supports multiple LLM providers: OpenRouter (default), Groq.
"""

import os
import logging
from typing import Annotated, TypedDict, AsyncIterator
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .errors import RetryableError, ContextLimitError, is_retryable_error, get_friendly_error

logger = logging.getLogger(__name__)

from .tools import (
    list_directory_structure,
    read_file,
    search_code,
    find_files_by_pattern,
    get_imports,
    find_entry_points,
    analyze_dependencies,
    get_function_signatures,
)
from .prompts import SYSTEM_PROMPT, OVERVIEW_PROMPT, DEEP_DIVE_PROMPT


# All available tools
TOOLS = [
    list_directory_structure,
    read_file,
    search_code,
    find_files_by_pattern,
    get_imports,
    find_entry_points,
    analyze_dependencies,
    get_function_signatures,
]

# Default models per provider
DEFAULT_MODELS = {
    "openrouter": "xiaomi/mimo-v2-flash:free",  # FREE model, excellent for code
    "groq": "llama-3.1-8b-instant",  # Free tier
}

# UX-006: Maximum conversation history to prevent context overflow
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))

# EVAL-003: Context budget tracking
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "100000"))
CONTEXT_WARNING_THRESHOLD = 0.8  # Warn at 80%
CONTEXT_SUMMARY_THRESHOLD = 0.95  # Truncate at 95%


class AgentState(TypedDict):
    """State for the onboarding agent."""
    messages: Annotated[list, add_messages]
    repo_path: str


def create_agent(
    api_key: str | None = None,
    model: str | None = None,
    provider: str = "openrouter"
):
    """
    Create the codebase onboarding agent.

    Args:
        api_key: API key (uses env var if not provided)
        model: Model to use (defaults based on provider)
        provider: LLM provider - "openrouter" or "groq"

    Returns:
        Compiled LangGraph agent
    """
    # Determine API key
    if api_key is None:
        if provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
        else:
            api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(f"API key not provided and not found in environment for {provider}")

    # Determine model
    if model is None:
        model = DEFAULT_MODELS.get(provider, DEFAULT_MODELS["openrouter"])

    # Initialize LLM based on provider
    # SEC-007: Add request timeout to prevent hanging requests
    if provider == "openrouter":
        llm = ChatOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            model=model,
            temperature=0,
            timeout=120,  # 2 minute timeout
            max_retries=2,
        )
    else:
        # Groq uses OpenAI-compatible API too
        llm = ChatOpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            model=model,
            temperature=0,
            timeout=120,  # 2 minute timeout
            max_retries=2,
        )

    llm_with_tools = llm.bind_tools(TOOLS)

    def agent_node(state: AgentState) -> AgentState:
        """Main agent reasoning node."""
        messages = state["messages"]
        repo_path = state["repo_path"]

        # Add system prompt if not present
        if not any(isinstance(m, SystemMessage) for m in messages):
            system = SystemMessage(content=SYSTEM_PROMPT.format(repo_path=repo_path))
            messages = [system] + messages

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        """Determine if we should continue with tools or end."""
        messages = state["messages"]
        last_message = messages[-1]

        # If the last message has tool calls, continue to tools
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    # Create the tool node
    tool_node = ToolNode(TOOLS)

    # Build the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    # Set entry point
    graph.set_entry_point("agent")

    # Add edges
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END,
        },
    )
    graph.add_edge("tools", "agent")

    return graph.compile()


# UX-003: Retry decorator for transient errors
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    retry=retry_if_exception_type(RetryableError),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def invoke_with_retry(agent, state):
    """
    Invoke agent with automatic retry on transient errors.

    UX-003: Implements exponential backoff for rate limits, timeouts, etc.
    """
    try:
        return agent.invoke(state)
    except Exception as e:
        if is_retryable_error(e):
            logger.warning(f"Retryable error encountered: {e}")
            raise RetryableError(str(e)) from e
        raise


class CodebaseOnboardingAgent:
    """High-level interface for the codebase onboarding agent."""

    def __init__(
        self,
        repo_path: str,
        api_key: str | None = None,
        model: str | None = None,
        provider: str = "openrouter"
    ):
        """
        Initialize the agent for a specific repository.

        Args:
            repo_path: Path to the repository to analyze
            api_key: API key (uses env var if not provided)
            model: Model to use (defaults based on provider)
            provider: LLM provider - "openrouter" or "groq"
        """
        self.repo_path = str(Path(repo_path).resolve())
        if not Path(self.repo_path).exists():
            raise ValueError(f"Repository path does not exist: {self.repo_path}")

        self.agent = create_agent(api_key, model, provider)
        self.conversation_history: list = []
        self.last_tool_calls: list[dict] = []  # Track tool calls from last run
        self.last_tool_outputs: list[str] = []  # Track tool outputs for citation verification (EVAL-005)
        # EVAL-003: Context budget tracking
        self.context_tokens = 0
        self.context_warning_shown = False

    def _run(self, user_message: str) -> str:
        """Run a single interaction with the agent."""
        self.conversation_history.append(HumanMessage(content=user_message))

        state = {
            "messages": self.conversation_history.copy(),
            "repo_path": self.repo_path,
        }

        try:
            # UX-003: Use retry wrapper for transient errors
            result = invoke_with_retry(self.agent, state)
        except RetryableError as e:
            # UX-004: Return friendly error after retries exhausted
            return get_friendly_error(e)
        except Exception as e:
            # UX-004: Return friendly error for non-retryable errors
            return get_friendly_error(e)

        # Extract the final response and track tool calls
        messages = result["messages"]
        self.last_tool_calls = []  # Reset for this run
        self.last_tool_outputs = []  # Reset tool outputs for this run

        # Find the last AI message that isn't a tool call
        final_response = None
        for msg in messages:
            # Extract tool calls from AIMessages
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    self.last_tool_calls.append({
                        "name": tc.get("name") or tc.get("function", {}).get("name"),
                        "args": tc.get("args") or tc.get("function", {}).get("arguments"),
                    })
            # Capture tool outputs from ToolMessages (EVAL-005)
            elif isinstance(msg, ToolMessage) and hasattr(msg, "content"):
                self.last_tool_outputs.append(msg.content)

        # Find final response (last AIMessage without tool calls)
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and not (hasattr(msg, "tool_calls") and msg.tool_calls):
                final_response = msg.content
                break

        if final_response:
            self.conversation_history.append(AIMessage(content=final_response))

        # UX-006: Prune history to prevent context overflow
        self._prune_history()

        return final_response or "No response generated"

    def get_overview(self) -> str:
        """Generate a comprehensive overview of the codebase."""
        return self._run(OVERVIEW_PROMPT)

    def ask(self, question: str) -> str:
        """Ask a specific question about the codebase."""
        prompt = DEEP_DIVE_PROMPT.format(question=question)
        return self._run(prompt)

    def chat(self, message: str) -> str:
        """General chat about the codebase."""
        return self._run(message)

    def reset_conversation(self):
        """Reset the conversation history and tool call log."""
        self.conversation_history = []
        self.last_tool_calls = []
        self.last_tool_outputs = []

    def _prune_history(self):
        """
        UX-006: Keep conversation history within limits to prevent context overflow.

        Preserves system messages and keeps the most recent messages.
        """
        if len(self.conversation_history) <= MAX_HISTORY_MESSAGES:
            return

        # Separate system messages from others
        system_msgs = [m for m in self.conversation_history if isinstance(m, SystemMessage)]
        other_msgs = [m for m in self.conversation_history if not isinstance(m, SystemMessage)]

        # Keep last (MAX - len(system_msgs)) non-system messages
        keep_count = MAX_HISTORY_MESSAGES - len(system_msgs)
        if keep_count > 0:
            other_msgs = other_msgs[-keep_count:]

        self.conversation_history = system_msgs + other_msgs
        logger.info(f"Pruned conversation history to {len(self.conversation_history)} messages")

    def _estimate_tokens(self, content: str) -> int:
        """
        EVAL-003: Rough token estimate (1 token ≈ 4 chars).
        """
        return len(content) // 4

    def _track_context(self, content: str) -> str:
        """
        EVAL-003: Track context usage and potentially truncate.

        Args:
            content: Content being added to context

        Returns:
            Content (possibly truncated if near limit)

        Raises:
            ContextLimitError: If context budget is exhausted
        """
        tokens = self._estimate_tokens(content)
        self.context_tokens += tokens

        usage_pct = self.context_tokens / MAX_CONTEXT_TOKENS

        if usage_pct >= 1.0:
            raise ContextLimitError(
                f"Context limit reached ({self.context_tokens:,} tokens). "
                "Try asking about a specific component or file."
            )

        if usage_pct >= CONTEXT_SUMMARY_THRESHOLD:
            # Truncate to prevent overflow
            truncated = content[:4000] + "\n\n[TRUNCATED - Context limit approaching]"
            logger.warning(f"Content truncated at {usage_pct:.1%} context usage")
            return truncated

        if usage_pct >= CONTEXT_WARNING_THRESHOLD and not self.context_warning_shown:
            self.context_warning_shown = True
            logger.warning(f"Context usage at {usage_pct:.1%} of {MAX_CONTEXT_TOKENS:,} tokens")

        return content

    def get_context_usage(self) -> dict:
        """
        EVAL-003: Get current context usage stats.

        Returns:
            {"tokens_used": int, "limit": int, "percentage": float}
        """
        return {
            "tokens_used": self.context_tokens,
            "limit": MAX_CONTEXT_TOKENS,
            "percentage": round(self.context_tokens / MAX_CONTEXT_TOKENS * 100, 1)
        }

    def get_tool_calls(self) -> list[dict]:
        """Get the tool calls from the last run."""
        return self.last_tool_calls

    def get_tool_names(self) -> list[str]:
        """Get unique tool names from the last run."""
        return list(set(tc["name"] for tc in self.last_tool_calls if tc["name"]))

    def get_tool_outputs(self) -> list[str]:
        """Get tool outputs from the last run (EVAL-005: for citation verification)."""
        return self.last_tool_outputs

    async def stream(self, message: str) -> AsyncIterator[dict]:
        """
        Stream response chunks for real-time display.

        UX-001: Streaming responses for better user experience.

        Yields:
            {"type": "token", "content": "..."}
            {"type": "tool_start", "name": "read_file", "input": {...}}
            {"type": "tool_end", "name": "read_file", "output": "..."}
            {"type": "done", "content": "full response"}
        """
        self.conversation_history.append(HumanMessage(content=message))

        state = {
            "messages": self.conversation_history.copy(),
            "repo_path": self.repo_path,
        }

        full_response = ""
        self.last_tool_calls = []  # Reset for this run
        self.last_tool_outputs = []  # Reset tool outputs

        try:
            async for event in self.agent.astream_events(state, version="v2"):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        full_response += chunk.content
                        yield {"type": "token", "content": chunk.content}

                elif kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    self.last_tool_calls.append({
                        "name": tool_name,
                        "args": tool_input,
                    })
                    yield {
                        "type": "tool_start",
                        "name": tool_name,
                        "input": tool_input
                    }

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = str(event.get("data", {}).get("output", ""))
                    # Store tool output for citation verification
                    self.last_tool_outputs.append(tool_output)
                    yield {
                        "type": "tool_end",
                        "name": tool_name,
                        "output": tool_output[:500]  # Truncate for display
                    }

        except Exception as e:
            yield {"type": "error", "content": str(e)}
            return

        # Update conversation history with final response
        if full_response:
            self.conversation_history.append(AIMessage(content=full_response))

        # UX-006: Prune history to prevent context overflow
        self._prune_history()

        yield {"type": "done", "content": full_response}

    async def stream_overview(self) -> AsyncIterator[dict]:
        """Stream overview generation."""
        async for event in self.stream(OVERVIEW_PROMPT):
            yield event

    async def stream_ask(self, question: str) -> AsyncIterator[dict]:
        """Stream a question response."""
        prompt = DEEP_DIVE_PROMPT.format(question=question)
        async for event in self.stream(prompt):
            yield event


def run_cli():
    """Simple CLI for testing the agent."""
    import argparse

    parser = argparse.ArgumentParser(description="Codebase Onboarding Agent")
    parser.add_argument("repo_path", help="Path to the repository to analyze")
    parser.add_argument("--overview", action="store_true", help="Generate codebase overview")
    parser.add_argument("--ask", type=str, help="Ask a specific question")
    parser.add_argument("--provider", type=str, default="openrouter",
                        choices=["openrouter", "groq"],
                        help="LLM provider (default: openrouter)")
    parser.add_argument("--model", type=str, help="Model to use (defaults based on provider)")
    args = parser.parse_args()

    agent = CodebaseOnboardingAgent(
        args.repo_path,
        provider=args.provider,
        model=args.model
    )

    if args.overview:
        print("\n🔍 Generating codebase overview...\n")
        print(agent.get_overview())
    elif args.ask:
        print(f"\n🔍 Investigating: {args.ask}\n")
        print(agent.ask(args.ask))
    else:
        # Interactive mode
        print(f"\n📁 Analyzing: {args.repo_path}")
        print("Type 'overview' for a full overview, 'quit' to exit, or ask any question.\n")

        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() == "quit":
                    break
                if user_input.lower() == "overview":
                    print("\n🔍 Generating overview...\n")
                    print(agent.get_overview())
                else:
                    print("\n🤖 Agent:\n")
                    print(agent.chat(user_input))
                print()
            except KeyboardInterrupt:
                break

    print("\nGoodbye! 👋")


if __name__ == "__main__":
    run_cli()
