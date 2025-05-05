# utils/helpers.py

import tiktoken
import re

def estimate_tokens(text: str, model: str = "gpt-4.1") -> int:
    """Roughly estimates the number of tokens in a text."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def clean_text(text: str) -> str:
    """Removes extra whitespace, markdown, and control characters."""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\u200b", "")  # remove zero-width space
    return text.strip()

def truncate(text: str, max_chars: int = 2000) -> str:
    """Truncates text safely without cutting mid-word."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."

def safe_json_parse(content: str):
    """Safely loads a JSON string or returns {}."""
    import json
    try:
        return json.loads(content)
    except Exception:
        return {}
