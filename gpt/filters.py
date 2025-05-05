import os
from typing import List, Dict
from utils.helpers import estimate_tokens
from utils.logger import setup_logger
from config.config_loader import get_config

log = setup_logger()
config = get_config()
PROMPT_PATH = "gpt/prompts/filter_prompt.txt"


def load_filter_prompt_template():
    """Load the filter prompt template from file."""
    try:
        with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        log.error(f"Error loading filter prompt template: {str(e)}")
        return (
            "You are a marketing assistant scoring Reddit posts for product relevance.\n\n"
            "Analyze:\n"
            "- Is the post about automation, cron jobs, scheduling tasks, or running scripts?\n"
            "- Does the user express frustration, confusion, or a need for a solution?\n"
            "- How emotionally charged is the post?\n\n"
            "Respond with JSON including relevance_score, emotional_intensity, pain_point_clarity, and summary."
        )


FILTER_PROMPT_TEMPLATE = load_filter_prompt_template()


def build_filter_prompt(post: dict) -> List[Dict]:
    """Constructs the GPT-4.1 Mini prompt for a Reddit post using template."""
    return [
        {"role": "system", "content": "You are a marketing assistant scoring Reddit posts for product relevance."},
        {"role": "user", "content": f"Post title: {post['title']}\nPost body: {post['body']}\n\n{FILTER_PROMPT_TEMPLATE}"}
    ]


def prepare_batch_payload(posts: List[dict]) -> List[Dict]:
    """Returns list of payloads for batch submission."""
    payload = []
    for post in posts:
        messages = build_filter_prompt(post)
        payload.append({
            "id": post["id"],
            "messages": messages,
            "meta": {
                "estimated_tokens": estimate_tokens(
                    post.get("title", "") + post.get("body", ""),
                    config["openai"].get("model_filter", "gpt-4.1-mini")
                )
            }
        })
    return payload


def estimate_batch_cost(posts: List[dict], avg_tokens: int = 300, input_cost_per_1k: float = 0.40) -> float:
    """Rough estimate of GPT-4.1 Mini cost for the filtering batch."""
    total_tokens = len(posts) * avg_tokens
    return (total_tokens / 1000) * input_cost_per_1k
