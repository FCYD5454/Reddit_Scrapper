# gpt/filters.py

import openai
from typing import List, Dict
from utils.helpers import estimate_tokens

def build_filter_prompt(post: dict) -> List[Dict]:
    """Constructs the GPT-4.1 Mini prompt for a Reddit post."""
    return [
        {"role": "system", "content": "You are a marketing assistant scoring Reddit posts for product relevance."},
        {"role": "user", "content": f"""Post title: {post['title']}
Post body: {post['body']}
Score the post for relevance to a product that schedules HTTP jobs like a hosted cron service.
Respond in JSON as specified in the prompt."""}
    ]

def prepare_batch_payload(posts: List[dict]) -> List[Dict]:
    """Returns list of payloads for batch submission."""
    payload = []
    for post in posts:
        messages = build_filter_prompt(post)
        payload.append({
            "id": post["id"],
            "messages": messages
        })
    return payload

def estimate_batch_cost(posts: List[dict], avg_tokens: int = 300, input_cost_per_1k: float = 0.40) -> float:
    """Rough estimate of GPT-4.1 Mini cost for the filtering batch."""
    total_tokens = len(posts) * avg_tokens
    return (total_tokens / 1000) * input_cost_per_1k
