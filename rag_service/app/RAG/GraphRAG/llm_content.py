"""Safe extraction of visible text from LangChain message responses."""

from langchain_core.messages import BaseMessage


class LlmContentError(ValueError):
    """Raised when an LLM response has no usable visible text."""


def require_message_text(message: BaseMessage, *, operation: str) -> str:
    """Return canonical visible message text or fail without exposing content."""
    try:
        text = getattr(message, "text", None)
    except Exception:
        text = None

    if isinstance(text, str) and text.strip():
        return text

    # Fallback: inspect content if it is a list of dicts (e.g. thinking + text blocks)
    content = getattr(message, "content", None)
    if isinstance(content, list):
        extracted_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                extracted_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                extracted_parts.append(block)
        joined = "".join(extracted_parts).strip()
        if joined:
            return joined
    elif isinstance(content, str) and content.strip():
        return content.strip()

    raise LlmContentError(f"{operation} returned no usable text")
