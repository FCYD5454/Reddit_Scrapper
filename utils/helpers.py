# utils/helpers.py

import tiktoken
import os
import json
import tiktoken
from datetime import datetime, timedelta, timezone

from config.config_loader import get_config
from utils.logger import setup_logger

# Setup logger and config
log = setup_logger()
config = get_config()

# Default tokenizer for GPT-4, GPT-3.5
DEFAULT_ENCODING = "cl100k_base"
ENCODER = tiktoken.get_encoding(DEFAULT_ENCODING)

def estimate_tokens(text: str, model: str = None) -> int:
    """Estimate number of tokens in a text string using GPT-4 tokenizer."""
    try:
        return len(ENCODER.encode(text or ""))
    except Exception as e:
        log.error(f"Token estimation failed: {e}")
        return config["openai"].get("max_tokens_per_post", 1000)

def ensure_directory_exists(path: str):
    """Ensure the directory exists."""
    os.makedirs(path, exist_ok=True)

def save_json(data: dict, filename: str):
    """Save dictionary as a JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def load_json(filename: str) -> dict:
    """Load dictionary from JSON file."""
    if not os.path.exists(filename):
        return {}
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def format_datetime(dt: datetime = None) -> str:
    """Return timezone-aware datetime in ISO 8601 format (UTC)."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.isoformat()

def days_ago(days: int) -> datetime:
    """Return timezone-aware datetime for N days ago."""
    return datetime.now(timezone.utc) - timedelta(days=days)

def truncate(text: str, max_tokens: int = 1000) -> str:
    """Truncate a string to fit within a token limit."""
    tokens = ENCODER.encode(text or "")
    if len(tokens) <= max_tokens:
        return text
    return ENCODER.decode(tokens[:max_tokens])
