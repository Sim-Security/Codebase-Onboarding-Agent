"""
UX-004: Friendly error messages for the Codebase Onboarding Agent.
Converts raw exceptions to user-friendly messages with suggested actions.
"""

import logging

logger = logging.getLogger(__name__)

ERROR_MESSAGES = {
    "rate_limit": {
        "patterns": ["rate limit", "429", "too many requests", "quota exceeded"],
        "message": "The AI service is busy right now.",
        "action": "Wait 30-60 seconds and try again. If using a free model, try a different one.",
    },
    "context_length": {
        "patterns": [
            "context length",
            "maximum context",
            "too long",
            "token limit",
            "context window",
        ],
        "message": "This repository is too large for a complete analysis.",
        "action": "Try asking about a specific component or file instead of the whole codebase.",
    },
    "auth": {
        "patterns": [
            "invalid api key",
            "unauthorized",
            "401",
            "authentication",
            "invalid_api_key",
        ],
        "message": "Your API key appears to be invalid or expired.",
        "action": "Check your key at openrouter.ai/settings or console.groq.com and make sure it's still active.",
    },
    "timeout": {
        "patterns": ["timeout", "timed out", "deadline exceeded", "request timed out"],
        "message": "The request took too long to complete.",
        "action": "Try a simpler question, or check if the AI service is experiencing issues.",
    },
    "clone_failed": {
        "patterns": [
            "clone",
            "git",
            "repository not found",
            "could not read",
            "fatal:",
        ],
        "message": "Couldn't clone this repository.",
        "action": "Make sure the URL is correct and the repository is public. Private repos require authentication.",
    },
    "network": {
        "patterns": [
            "connection",
            "network",
            "unreachable",
            "dns",
            "ssl",
            "certificate",
        ],
        "message": "Network connection issue.",
        "action": "Check your internet connection and try again.",
    },
    "model_not_found": {
        "patterns": [
            "model not found",
            "invalid model",
            "model_not_found",
            "no such model",
        ],
        "message": "The selected model is not available.",
        "action": "Try a different model from the dropdown, or check openrouter.ai/models for available options.",
    },
    "insufficient_quota": {
        "patterns": ["insufficient", "quota", "credits", "balance", "payment"],
        "message": "Your API account may have insufficient credits.",
        "action": "Check your balance at openrouter.ai/settings. Try using a free model instead.",
    },
    "service_unavailable": {
        "patterns": [
            "502",
            "503",
            "504",
            "service unavailable",
            "temporarily unavailable",
            "overloaded",
        ],
        "message": "The AI service is temporarily unavailable.",
        "action": "The service may be experiencing high load. Wait a minute and try again.",
    },
}


def get_friendly_error(error: Exception) -> str:
    """
    Convert exception to user-friendly message with suggested action.

    Args:
        error: The exception that occurred

    Returns:
        User-friendly error message with suggestion
    """
    error_str = str(error).lower()
    logger.error(f"Original error: {error}")

    for error_type, config in ERROR_MESSAGES.items():
        if any(p in error_str for p in config["patterns"]):
            return (
                f"**Error:** {config['message']}\n\n**Suggestion:** {config['action']}"
            )

    # Generic fallback - truncate long error messages
    error_text = str(error)
    if len(error_text) > 300:
        error_text = error_text[:300] + "..."

    return f"**Error:** Something went wrong.\n\n**Details:** {error_text}\n\n**Suggestion:** Try again or ask a simpler question."


def is_retryable_error(error: Exception) -> bool:
    """
    Check if an error should trigger a retry.

    Args:
        error: The exception that occurred

    Returns:
        True if the error is transient and should be retried
    """
    error_str = str(error).lower()
    retryable_patterns = [
        "rate limit",
        "429",
        "502",
        "503",
        "504",
        "temporarily unavailable",
        "capacity",
        "timeout",
        "timed out",
        "overloaded",
        "too many requests",
    ]
    return any(p in error_str for p in retryable_patterns)


class RetryableError(Exception):
    """Errors that should trigger automatic retry."""

    pass


class ContextLimitError(Exception):
    """Raised when context budget is exhausted."""

    pass
