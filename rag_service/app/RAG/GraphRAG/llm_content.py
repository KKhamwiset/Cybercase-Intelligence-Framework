"""Safe extraction of visible text from LangChain message responses."""

from langchain_core.messages import BaseMessage


class LlmContentError(ValueError):
    """Raised when an LLM response has no usable visible text."""


def require_message_text(message: BaseMessage, *, operation: str) -> str:
    """Return canonical visible message text or fail without exposing content."""
    try:
        text = message.text
    except Exception:
        raise LlmContentError(f"{operation} returned no usable text") from None

    if not isinstance(text, str) or not text.strip():
        raise LlmContentError(f"{operation} returned no usable text")

    return text
