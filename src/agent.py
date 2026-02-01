"""
LangGraph agent for codebase onboarding.
Uses tools + context + model intelligence (no RAG).
Supports multiple LLM providers: OpenRouter (default), Groq.
"""

import logging
import os
from pathlib import Path
from typing import (
    Annotated,
    AsyncIterator,
    Callable,
    Protocol,
    TypedDict,
    runtime_checkable,
)

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .cache import CacheKey, ResponseCache
from .errors import (
    ContextLimitError,
    RetryableError,
    get_friendly_error,
    is_retryable_error,
)
from .eval.verification import filter_ungrounded_citations, validate_tool_usage
from .memory import WorkingMemory
from .tool_router import ToolRouter, ToolUsageTracker

logger = logging.getLogger(__name__)


# =============================================================================
# UX-010: Progress Tracking for Long Operations
# =============================================================================


@runtime_checkable
class ProgressCallback(Protocol):
    """
    Protocol for progress callbacks during long-running operations.

    UX-010: Provides real-time progress updates to UI components.

    The callback receives:
        step: A short identifier for the current step type
              - "thinking": Agent is processing/reasoning
              - "tool_start": A tool is about to be called
              - "tool_end": A tool has finished executing
        detail: Human-readable detail about the step
              - For tool_start: Tool name and key arguments
              - For tool_end: Brief summary of result
              - For thinking: What the agent is considering
    """

    def __call__(self, step: str, detail: str) -> None:
        """
        Called when progress occurs.

        Args:
            step: The step type (e.g., "thinking", "tool_start", "tool_end")
            detail: Human-readable description of the progress
        """
        ...


# Type alias for progress callback functions
ProgressCallbackType = Callable[[str, str], None] | ProgressCallback | None


def _format_tool_detail(tool_name: str, tool_args: dict) -> str:
    """
    Format tool call details for progress display.

    Args:
        tool_name: Name of the tool being called
        tool_args: Arguments passed to the tool

    Returns:
        Human-readable description of the tool call
    """
    if tool_name == "read_file":
        file_path = tool_args.get("file_path", "unknown")
        filename = Path(file_path).name if file_path else "file"
        return f"Reading {filename}"

    elif tool_name == "search_code":
        pattern = tool_args.get("pattern", "")
        return f"Searching for '{pattern}'"

    elif tool_name == "find_files_by_pattern":
        pattern = tool_args.get("pattern", "")
        return f"Finding files matching '{pattern}'"

    elif tool_name == "list_directory_structure":
        return "Exploring directory structure"

    elif tool_name == "get_imports":
        file_path = tool_args.get("file_path", "unknown")
        filename = Path(file_path).name if file_path else "file"
        return f"Analyzing imports in {filename}"

    elif tool_name == "find_entry_points":
        return "Finding entry points"

    elif tool_name == "analyze_dependencies":
        return "Analyzing dependencies"

    elif tool_name == "get_function_signatures":
        file_path = tool_args.get("file_path", "unknown")
        filename = Path(file_path).name if file_path else "file"
        return f"Getting function signatures from {filename}"

    elif tool_name == "get_important_files":
        return "Identifying important files"

    else:
        return f"Running {tool_name}"


# ORCH-005: Planning prompt for plan-then-execute pattern
PLANNING_PROMPT = """You are planning how to explore a codebase to answer a question.

QUESTION: {question}

CURRENT KNOWLEDGE:
{memory_context}

Create a brief exploration plan (3-5 steps) to answer this question.
Each step should be a specific action like:
- "Search for authentication-related files"
- "Read the main entry point"
- "Check the database models"

Return ONLY the numbered plan, nothing else.
"""

# SELF-001: Reflection prompt for evaluating exploration progress
REFLECTION_PROMPT = """Evaluate your recent exploration:

QUESTION: {question}
ACTIONS TAKEN: {recent_actions}
CURRENT FINDINGS: {memory_context}
STATS: {stats}

Reflect on:
1. Am I making progress toward answering the question?
2. Have I been repeating similar actions without new insights?
3. Is there a more direct approach I'm missing?
4. Do I have enough information to answer now?

Based on your reflection, recommend ONE action:
- CONTINUE: Keep exploring, making good progress
- PIVOT: Change strategy, current approach isn't working
- SYNTHESIZE: Have enough info, ready to answer

Reply with ONLY: CONTINUE, PIVOT, or SYNTHESIZE
"""

from .prompts import CODE_FLOW_PROMPT, DEEP_DIVE_PROMPT, OVERVIEW_PROMPT, SYSTEM_PROMPT
from .tools import (
    analyze_dependencies,
    find_entry_points,
    find_files_by_pattern,
    get_function_signatures,
    get_imports,
    list_directory_structure,
    read_file,
    search_code,
)
from .tools.smart_discovery import get_important_files

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
    get_important_files,
]

# Default models per provider
DEFAULT_MODELS = {
    "openrouter": "x-ai/grok-4.1-fast",  # Fast, affordable, excellent for code
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
    api_key: str | None = None, model: str | None = None, provider: str = "openrouter"
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
        raise ValueError(
            f"API key not provided and not found in environment for {provider}"
        )

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
        provider: str = "openrouter",
        use_cache: bool = True,
    ):
        """
        Initialize the agent for a specific repository.

        Args:
            repo_path: Path to the repository to analyze
            api_key: API key (uses env var if not provided)
            model: Model to use (defaults based on provider)
            provider: LLM provider - "openrouter" or "groq"
            use_cache: Whether to use response caching (default: True)
        """
        self.repo_path = str(Path(repo_path).resolve())
        if not Path(self.repo_path).exists():
            raise ValueError(f"Repository path does not exist: {self.repo_path}")

        # Store model identifier for caching
        self.model = model or DEFAULT_MODELS.get(provider, DEFAULT_MODELS["openrouter"])
        self.provider = provider

        self.agent = create_agent(api_key, model, provider)
        self.conversation_history: list = []
        self.last_tool_calls: list[dict] = []  # Track tool calls from last run
        self.last_tool_outputs: list[
            str
        ] = []  # Track tool outputs for citation verification (EVAL-005)
        # EVAL-003: Context budget tracking
        self.context_tokens = 0
        self.context_warning_shown = False
        # ORCH-002: Working memory for tracking exploration
        self.working_memory = WorkingMemory()
        # ORCH-005: Tool tracking for plan-then-execute
        self.tool_router = ToolRouter()
        self.tool_tracker = ToolUsageTracker()

        # UX-009: Response caching
        self.use_cache = use_cache
        self.cache = ResponseCache(repo_path=self.repo_path) if use_cache else None
        self._cache_hit = False  # Track if last response was from cache

    def _run(
        self, user_message: str, progress_callback: ProgressCallbackType = None
    ) -> str:
        """
        Run a single interaction with the agent.

        Args:
            user_message: The user's message/question
            progress_callback: Optional callback for progress updates (UX-010)

        Returns:
            The agent's response string
        """
        self._cache_hit = False  # Reset cache hit flag

        # UX-010: Helper to safely call progress callback
        def notify_progress(step: str, detail: str) -> None:
            if progress_callback:
                try:
                    progress_callback(step, detail)
                except Exception as e:
                    logger.debug(f"Progress callback error: {e}")

        # UX-009: Check cache before running
        if self.use_cache and self.cache:
            notify_progress("thinking", "Checking cache...")
            cache_key = CacheKey.create(self.repo_path, user_message, self.model)
            cached_response, cached_tool_calls = self.cache.get_with_tool_calls(
                cache_key
            )
            if cached_response:
                logger.info("Returning cached response")
                notify_progress("thinking", "Found cached response")
                self._cache_hit = True
                self.last_tool_calls = cached_tool_calls
                # Add to conversation history for context continuity
                self.conversation_history.append(HumanMessage(content=user_message))
                self.conversation_history.append(AIMessage(content=cached_response))
                self._prune_history()
                return cached_response

        # ORCH-006: Check circuit breaker before continuing
        is_thrashing, reason = self.tool_tracker.check_thrashing()
        if is_thrashing:
            logger.warning(f"Circuit breaker: {reason}")
            return self.tool_tracker.get_graceful_exit_message(user_message)

        # CITE-FIX: Inject working memory context into prompt so model knows what it can cite
        memory_context = self.working_memory.to_context_string()
        if memory_context and self.working_memory.files_read:
            augmented_message = f"{user_message}\n\n{memory_context}"
        else:
            # First call - remind about citation rules
            augmented_message = f"""{user_message}

## CITATION REMINDER
You MUST call `read_file` on any file BEFORE citing its line numbers.
You CANNOT cite lines from files you only saw in search results or directory listings.
Start by exploring, then READ key files, then answer with citations from files you read."""

        self.conversation_history.append(HumanMessage(content=augmented_message))

        state = {
            "messages": self.conversation_history.copy(),
            "repo_path": self.repo_path,
        }

        notify_progress("thinking", "Analyzing codebase...")

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
            # ORCH-006: Track tool calls for circuit breaker
            if (
                isinstance(msg, AIMessage)
                and hasattr(msg, "tool_calls")
                and msg.tool_calls
            ):
                for tc in msg.tool_calls:
                    tool_name = tc.get("name") or tc.get("function", {}).get("name")
                    tool_args = tc.get("args") or tc.get("function", {}).get(
                        "arguments"
                    )
                    self.last_tool_calls.append(
                        {
                            "name": tool_name,
                            "args": tool_args,
                        }
                    )
                    if tool_name:
                        self.tool_router.record_tool_call(tool_name)
                        # UX-010: Notify about tool call (after the fact for sync)
                        notify_progress(
                            "tool_end",
                            _format_tool_detail(
                                tool_name, tool_args if tool_args else {}
                            ),
                        )
            # Capture tool outputs from ToolMessages (EVAL-005)
            elif isinstance(msg, ToolMessage) and hasattr(msg, "content"):
                self.last_tool_outputs.append(msg.content)
                # ORCH-006: Track tool output for circuit breaker
                if self.last_tool_calls:
                    last_tool_name = self.last_tool_calls[-1].get("name", "unknown")
                    last_tool_input = str(self.last_tool_calls[-1].get("args", ""))
                    self.tool_tracker.record_call(
                        last_tool_name, last_tool_input, msg.content
                    )
                    # Update memory
                    self._update_memory_from_tool_call(
                        last_tool_name,
                        self.last_tool_calls[-1].get("args", {}),
                        msg.content,
                    )

        # Find final response (last AIMessage without tool calls)
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and not (
                hasattr(msg, "tool_calls") and msg.tool_calls
            ):
                final_response = msg.content
                break

        if final_response:
            # EVAL-005: Validate tool usage - ensure read_file was called before citations
            validation_result = validate_tool_usage(
                self.last_tool_calls, final_response
            )

            if validation_result["citations_count"] > 0:
                if not validation_result["has_read_file"]:
                    logger.warning(
                        f"VALIDATION FAILURE: Response has {validation_result['citations_count']} citations "
                        f"but no read_file calls were made"
                    )
                    self.tool_tracker.circuit_breaker.validation_failures += 1
                elif not validation_result["valid"]:
                    logger.warning(
                        f"VALIDATION FAILURE: Citations reference unread files: "
                        f"{validation_result['unread_cited_files']}"
                    )
                    self.tool_tracker.circuit_breaker.validation_failures += 1
                else:
                    logger.debug(
                        f"Validation passed: {validation_result['files_read_count']} files read, "
                        f"{validation_result['citations_count']} citations verified"
                    )

            # CITE-FIX: Validate and filter citations
            from .eval.verification import extract_citations

            citations_in_response = extract_citations(final_response)
            read_file_calls = [
                tc for tc in self.last_tool_calls if tc.get("name") == "read_file"
            ]

            # Check if citations exist but no read_file was called
            if citations_in_response and not read_file_calls:
                logger.warning(
                    f"Response has {len(citations_in_response)} citations but no read_file calls - filtering all"
                )
                # Filter ALL citations since none are grounded
                for citation in citations_in_response:
                    file_path = citation.get("file", "")
                    line_num = citation.get("line", 0)
                    import re

                    patterns = [
                        rf"`{re.escape(file_path)}:{line_num}`",
                        rf"\[{re.escape(file_path)}:{line_num}\]",
                        rf"\({re.escape(file_path)}:{line_num}\)",
                        rf"{re.escape(file_path)}:{line_num}",
                        # Backtick-hyphen format
                        rf"``{re.escape(file_path)}`-{line_num}`",
                        rf"`{re.escape(file_path)}`-{line_num}",
                    ]
                    for pattern in patterns:
                        if re.search(pattern, final_response):
                            final_response = re.sub(
                                pattern, f"`{file_path}`", final_response, count=1
                            )
                            break
            elif self.last_tool_outputs:
                # Normal case: verify citations against tool outputs
                filtered_response, removed = filter_ungrounded_citations(
                    final_response, self.last_tool_outputs, add_warning=False
                )
                if removed > 0:
                    logger.info(
                        f"Filtered {removed} ungrounded citations from response"
                    )
                    final_response = filtered_response

            self.conversation_history.append(AIMessage(content=final_response))

            # UX-009: Cache successful response
            if self.use_cache and self.cache:
                cache_key = CacheKey.create(self.repo_path, user_message, self.model)
                self.cache.set(
                    cache_key,
                    final_response,
                    tool_calls=self.last_tool_calls,
                    repo_path=self.repo_path,
                )

        # UX-006: Prune history to prevent context overflow
        self._prune_history()

        notify_progress("thinking", "Response complete")
        return final_response or "No response generated"

    def get_overview(self, progress_callback: ProgressCallbackType = None) -> str:
        """
        Generate a comprehensive overview of the codebase.

        Args:
            progress_callback: Optional callback for progress updates (UX-010)

        Returns:
            Overview of the codebase
        """
        return self._run(OVERVIEW_PROMPT, progress_callback=progress_callback)

    def _is_code_flow_question(self, question: str) -> bool:
        """Detect if the question is about code flow tracing."""
        flow_keywords = [
            "trace",
            "flow",
            "what happens",
            "how does",
            "execution",
            "call sequence",
            "step by step",
            "walk through",
            "execution path",
            "called in what order",
            "sequence of calls",
        ]
        q_lower = question.lower()
        return any(kw in q_lower for kw in flow_keywords)

    def ask(
        self,
        question: str,
        use_self_correction: bool = False,
        progress_callback: ProgressCallbackType = None,
    ) -> str:
        """
        Ask a specific question about the codebase.

        Args:
            question: The question to ask
            use_self_correction: Whether to use self-correction mode
            progress_callback: Optional callback for progress updates (UX-010)

        Returns:
            Answer to the question
        """
        if use_self_correction:
            return self.run_with_self_correction(question)

        # Use CODE_FLOW_PROMPT for code flow questions
        if self._is_code_flow_question(question):
            prompt = CODE_FLOW_PROMPT.format(question=question)
        else:
            prompt = DEEP_DIVE_PROMPT.format(question=question)
        return self._run(prompt, progress_callback=progress_callback)

    def chat(self, message: str, progress_callback: ProgressCallbackType = None) -> str:
        """
        General chat about the codebase.

        Args:
            message: The chat message
            progress_callback: Optional callback for progress updates (UX-010)

        Returns:
            Chat response
        """
        return self._run(message, progress_callback=progress_callback)

    def reset_conversation(self):
        """Reset conversation and memory."""
        self.conversation_history = []
        self.last_tool_calls = []
        self.last_tool_outputs = []
        self.working_memory = WorkingMemory()
        self.tool_router.reset()
        self.tool_tracker.reset()
        self._cache_hit = False

    def was_cache_hit(self) -> bool:
        """Check if the last response was served from cache."""
        return self._cache_hit

    def invalidate_cache(self) -> int:
        """
        Invalidate cache entries for this repository.

        Call this when the repository has changed and cached responses
        may be stale.

        Returns:
            Number of entries invalidated
        """
        if self.cache:
            return self.cache.invalidate(self.repo_path)
        return 0

    def get_cache_stats(self) -> dict:
        """Get statistics about the response cache."""
        if self.cache:
            return self.cache.get_stats()
        return {"entries": 0, "total_size_bytes": 0, "cache_enabled": False}

    def _update_memory_from_tool_call(
        self, tool_name: str, tool_input: dict, tool_output: str
    ):
        """Update working memory based on tool results."""
        if tool_name == "read_file":
            file_path = tool_input.get("file_path", "")
            lines = tool_output.count("\n")
            # Extract max line number from output
            # Format: "📄 file.py (123 lines)" or line numbers like "  42 | code"
            max_line = 0
            import re

            # Try to get from header "(N lines)"
            header_match = re.search(r"\((\d+) lines?\)", tool_output)
            if header_match:
                max_line = int(header_match.group(1))
            else:
                # Extract from last line number in content
                line_nums = re.findall(r"^\s*(\d+)\s*\|", tool_output, re.MULTILINE)
                if line_nums:
                    max_line = max(int(n) for n in line_nums)

            # Extract brief summary (first non-empty line of content)
            output_lines = tool_output.split("\n")
            summary = output_lines[2] if len(output_lines) > 2 else ""
            self.working_memory.add_file_read(file_path, lines, summary[:100], max_line)

        elif tool_name == "search_code":
            pattern = tool_input.get("pattern", "")
            # Count results
            results = tool_output.count("\n") - 2  # Minus header lines
            # Extract file paths from results
            import re

            files = re.findall(r"^([^:]+):", tool_output, re.MULTILINE)
            self.working_memory.add_search(
                pattern, max(0, results), list(set(files))[:5]
            )

        elif tool_name == "get_important_files":
            # Extract architecture if present
            if "Architecture:" in tool_output:
                arch_line = [l for l in tool_output.split("\n") if "Architecture:" in l]
                if arch_line:
                    self.working_memory.architecture_pattern = arch_line[0]

    def _should_skip_file_read(self, file_path: str) -> bool:
        """Check if file was already read."""
        return self.working_memory.was_file_read(file_path)

    def get_memory_stats(self) -> dict:
        """Get current memory statistics."""
        return self.working_memory.get_stats()

    def create_exploration_plan(self, question: str) -> list[str]:
        """Create a plan for exploring the codebase."""
        memory_context = self.working_memory.to_context_string()

        prompt = PLANNING_PROMPT.format(
            question=question,
            memory_context=memory_context if memory_context else "No prior knowledge",
        )

        # Use synchronous call for planning
        from langchain_core.messages import HumanMessage

        response = self.agent.invoke(
            {"messages": [HumanMessage(content=prompt)], "repo_path": self.repo_path}
        )

        # Extract plan from response
        last_message = response["messages"][-1]
        plan_text = (
            last_message.content
            if hasattr(last_message, "content")
            else str(last_message)
        )

        # Parse numbered list
        lines = plan_text.strip().split("\n")
        plan = []
        for line in lines:
            # Remove numbering
            cleaned = line.strip().lstrip("0123456789.-) ")
            if cleaned and len(cleaned) > 5:  # Skip very short lines
                plan.append(cleaned)

        self.working_memory.exploration_plan = plan[:5]  # Limit to 5 steps
        return plan[:5]

    def reflection_checkpoint(self, question: str) -> str:
        """
        Reflect on exploration progress and decide next action.

        Returns:
            "CONTINUE", "PIVOT", or "SYNTHESIZE"
        """
        # Check circuit breaker first
        is_thrashing, reason = self.tool_tracker.check_thrashing()
        if is_thrashing:
            logger.warning(f"Circuit breaker tripped: {reason}")
            return "SYNTHESIZE"  # Force synthesis when thrashing

        # Get context for reflection
        memory_context = self.working_memory.to_context_string()
        stats = self.get_tool_stats()

        # Format recent actions
        recent_actions = []
        for tc in self.last_tool_calls[-5:]:
            recent_actions.append(
                f"- {tc.get('name', 'unknown')}: {str(tc.get('args', ''))[:50]}"
            )

        prompt = REFLECTION_PROMPT.format(
            question=question,
            recent_actions="\n".join(recent_actions) if recent_actions else "None yet",
            memory_context=memory_context if memory_context else "No findings yet",
            stats=f"Files read: {stats.get('files_read', 0)}, Tool calls: {stats.get('total_calls', 0)}",
        )

        # Use agent for reflection
        try:
            from langchain_core.messages import HumanMessage

            response = self.agent.invoke(
                {
                    "messages": [HumanMessage(content=prompt)],
                    "repo_path": self.repo_path,
                }
            )

            last_message = response["messages"][-1]
            reflection = (
                last_message.content
                if hasattr(last_message, "content")
                else str(last_message)
            )

            # Parse recommendation
            reflection_upper = reflection.upper()
            if "SYNTHESIZE" in reflection_upper:
                logger.info(f"Reflection checkpoint: SYNTHESIZE - {reflection[:100]}")
                return "SYNTHESIZE"
            elif "PIVOT" in reflection_upper:
                logger.info(f"Reflection checkpoint: PIVOT - {reflection[:100]}")
                return "PIVOT"
            else:
                logger.info(f"Reflection checkpoint: CONTINUE - {reflection[:100]}")
                return "CONTINUE"

        except Exception as e:
            logger.warning(f"Reflection failed: {e}")
            # Default based on stats
            if stats.get("files_read", 0) >= 5 and stats.get("facts_confirmed", 0) >= 3:
                return "SYNTHESIZE"
            return "CONTINUE"

    def get_tool_stats(self) -> dict:
        """Get combined tool and memory statistics."""
        memory_stats = self.working_memory.get_stats()
        tracker_stats = self.tool_tracker.get_stats()
        return {**memory_stats, **tracker_stats}

    def detect_off_track(self, question: str) -> tuple[bool, str]:
        """
        Detect if exploration has gone off-track from the original question.

        Returns:
            (is_off_track, reason)
        """
        # Extract keywords from question (simple approach)
        import re

        question_words = set(re.findall(r"\b\w{4,}\b", question.lower()))
        question_words -= {
            "what",
            "where",
            "when",
            "which",
            "does",
            "have",
            "this",
            "that",
            "with",
            "from",
            "about",
        }

        if not question_words:
            return False, "Cannot analyze - question too short"

        # Check recent tool calls for relevance
        recent_tools = self.last_tool_calls[-10:]
        if len(recent_tools) < 5:
            return False, "Not enough data yet"

        # Analyze what we've been searching/reading
        explored_content = []
        for tc in recent_tools:
            args = tc.get("args", {})
            if isinstance(args, dict):
                for v in args.values():
                    if isinstance(v, str):
                        explored_content.append(v.lower())
            elif isinstance(args, str):
                explored_content.append(args.lower())

        explored_text = " ".join(explored_content)
        explored_words = set(re.findall(r"\b\w{4,}\b", explored_text))

        # Calculate overlap
        overlap = question_words & explored_words
        overlap_ratio = len(overlap) / len(question_words) if question_words else 0

        # Check confirmed facts relevance
        facts = self.working_memory.confirmed_facts
        fact_text = " ".join(f.fact.lower() for f in facts) if facts else ""
        fact_words = set(re.findall(r"\b\w{4,}\b", fact_text))
        fact_overlap = question_words & fact_words

        # Off-track if:
        # 1. Low overlap with question keywords AND
        # 2. Many tool calls without relevant findings
        if overlap_ratio < 0.2 and len(fact_overlap) == 0:
            if len(recent_tools) >= 8:
                return (
                    True,
                    f"Explored content ({len(explored_words)} terms) has low overlap with question keywords ({len(question_words)} terms)",
                )

        # Check for scope creep (reading many files without pattern)
        files_read = list(self.working_memory.files_read)[-10:]
        if len(files_read) > 5:
            # Check if files are scattered (many different directories)
            dirs = set()
            for f in files_read:
                parts = f.split("/")
                if len(parts) > 1:
                    dirs.add(parts[0])
            if len(dirs) > 4:
                return (
                    True,
                    f"Scope creep: exploring {len(dirs)} different directories without focus",
                )

        return False, "On track"

    def pivot_strategy(self, question: str, reason: str = "") -> list[str]:
        """
        Pivot exploration strategy when current approach isn't working.

        Args:
            question: The original question being explored
            reason: Why we're pivoting (from reflection/off-track detection)

        Returns:
            New exploration plan
        """
        logger.info(f"Pivoting strategy: {reason}")

        # Analyze what we've tried
        tools_used = [tc.get("name") for tc in self.last_tool_calls[-10:]]
        files_explored = list(self.working_memory.files_read)[-5:]

        # Determine pivot type based on patterns
        pivot_suggestions = []

        # If we've been doing too much searching without reading
        search_count = tools_used.count("search_code") + tools_used.count(
            "find_files_by_pattern"
        )
        read_count = tools_used.count("read_file")

        if search_count > 5 and read_count < 2:
            pivot_suggestions.append("Read the files found instead of more searching")
            pivot_suggestions.append("Focus on entry points: main.py, app.py, index.ts")

        # If we've been reading many files without finding answers
        if read_count > 5 and len(self.working_memory.confirmed_facts) < 2:
            pivot_suggestions.append(
                "Try searching for specific keywords from the question"
            )
            pivot_suggestions.append("Look at configuration files for hints")
            pivot_suggestions.append("Check import statements to find related modules")

        # If we seem stuck on one area
        if len(set(tools_used[-5:])) < 2:  # Same tool repeated
            pivot_suggestions.append("Try a different tool approach")
            pivot_suggestions.append("Step back and look at directory structure")

        # If exploring scattered files (scope creep)
        if "Scope creep" in reason:
            pivot_suggestions.append("Focus on one directory at a time")
            pivot_suggestions.append("Start from entry point and follow imports")

        # Default suggestions if no specific pattern detected
        if not pivot_suggestions:
            pivot_suggestions = [
                "Use get_important_files to find key files",
                "Search for keywords from the question",
                "Check the README or documentation",
                "Look at the main entry point",
            ]

        # Update working memory with new plan
        self.working_memory.exploration_plan = pivot_suggestions[:5]

        # Clear some state to allow fresh exploration
        self.tool_tracker.circuit_breaker.calls_without_new_info = 0

        logger.info(f"New strategy: {pivot_suggestions[:3]}")
        return pivot_suggestions[:5]

    def run_with_self_correction(self, question: str, max_iterations: int = 3) -> str:
        """Run exploration with self-correction capabilities."""
        self.working_memory.current_question = question
        for iteration in range(1, max_iterations + 1):
            logger.info(f"Self-correction iteration {iteration}/{max_iterations}")
            if iteration == 1:
                try:
                    self.create_exploration_plan(question)
                except Exception as e:
                    logger.warning(f"Planning failed: {e}")
            result = self._run(question)
            if (
                "explored extensively" in result.lower()
                or "couldn't find" in result.lower()
            ):
                return result
            recommendation = self.reflection_checkpoint(question)
            if recommendation == "SYNTHESIZE":
                return result
            elif recommendation == "PIVOT":
                is_off_track, reason = self.detect_off_track(question)
                if is_off_track:
                    logger.warning(f"Off-track detected: {reason}")
                new_plan = self.pivot_strategy(
                    question, reason if is_off_track else "Reflection recommended pivot"
                )
                continue
            else:
                stats = self.get_tool_stats()
                if stats.get("facts_confirmed", 0) >= 3:
                    return result
                continue
        logger.warning(f"Max iterations ({max_iterations}) reached")
        return self._run(f"Based on what you've learned, answer: {question}")

    def _prune_history(self):
        """
        UX-006: Keep conversation history within limits to prevent context overflow.

        Preserves system messages and keeps the most recent messages.
        """
        if len(self.conversation_history) <= MAX_HISTORY_MESSAGES:
            return

        # Separate system messages from others
        system_msgs = [
            m for m in self.conversation_history if isinstance(m, SystemMessage)
        ]
        other_msgs = [
            m for m in self.conversation_history if not isinstance(m, SystemMessage)
        ]

        # Keep last (MAX - len(system_msgs)) non-system messages
        keep_count = MAX_HISTORY_MESSAGES - len(system_msgs)
        if keep_count > 0:
            other_msgs = other_msgs[-keep_count:]

        self.conversation_history = system_msgs + other_msgs
        logger.info(
            f"Pruned conversation history to {len(self.conversation_history)} messages"
        )

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
            logger.warning(
                f"Context usage at {usage_pct:.1%} of {MAX_CONTEXT_TOKENS:,} tokens"
            )

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
            "percentage": round(self.context_tokens / MAX_CONTEXT_TOKENS * 100, 1),
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
                    self.last_tool_calls.append(
                        {
                            "name": tool_name,
                            "args": tool_input,
                        }
                    )
                    yield {"type": "tool_start", "name": tool_name, "input": tool_input}

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = str(event.get("data", {}).get("output", ""))
                    # Store tool output for citation verification
                    self.last_tool_outputs.append(tool_output)
                    yield {
                        "type": "tool_end",
                        "name": tool_name,
                        "output": tool_output[:500],  # Truncate for display
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
        # Use CODE_FLOW_PROMPT for code flow questions
        if self._is_code_flow_question(question):
            prompt = CODE_FLOW_PROMPT.format(question=question)
        else:
            prompt = DEEP_DIVE_PROMPT.format(question=question)
        async for event in self.stream(prompt):
            yield event


def run_cli():
    """Simple CLI for testing the agent."""
    import argparse

    parser = argparse.ArgumentParser(description="Codebase Onboarding Agent")
    parser.add_argument("repo_path", help="Path to the repository to analyze")
    parser.add_argument(
        "--overview", action="store_true", help="Generate codebase overview"
    )
    parser.add_argument("--ask", type=str, help="Ask a specific question")
    parser.add_argument(
        "--provider",
        type=str,
        default="openrouter",
        choices=["openrouter", "groq"],
        help="LLM provider (default: openrouter)",
    )
    parser.add_argument(
        "--model", type=str, help="Model to use (defaults based on provider)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable response caching",
    )
    args = parser.parse_args()

    agent = CodebaseOnboardingAgent(
        args.repo_path,
        provider=args.provider,
        model=args.model,
        use_cache=not args.no_cache,
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
        print(
            "Type 'overview' for a full overview, 'quit' to exit, or ask any question.\n"
        )

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
