# utils/helpers.py

import tiktoken
import os
import json
from datetime import datetime, timedelta

def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string."""
    encoding = tiktoken.get_encoding("cl100k_base")  # Default for gpt-4 models
    tokens = encoding.encode(text)
    return len(tokens)

def ensure_directory_exists(path: str):
    """Make sure a directory exists, creating it if needed."""
    os.makedirs(path, exist_ok=True)

def save_json(data: dict, filename: str):
    """Save dict as a JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def load_json(filename: str) -> dict:
    """Load JSON file as dict."""
    if not os.path.exists(filename):
        return {}
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def format_datetime(dt=None):
    """Format datetime with ISO format."""
    if dt is None:
        dt = datetime.utcnow()
    return dt.isoformat()

def days_ago(days: int) -> datetime:
    """Return datetime object for N days ago."""
    return datetime.utcnow() - timedelta(days=days)

def truncate(text: str, max_tokens: int = 1000) -> str:
    """Truncate a string to fit within a maximum token count."""
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text
    truncated = encoding.decode(tokens[:max_tokens])
    return truncated
