# gpt/insights.py

import openai
from typing import List, Dict
from utils.helpers import estimate_tokens

def build_insight_prompt(post: dict) -> List[Dict]:
    """Constructs the GPT-4.1 prompt for extracting deeper insights."""
    return [
        {"role": "system", "content": "You are a SaaS strategist extracting pain points and marketing tags from Reddit posts."},
        {"role": "user", "content": f"""Post title: {post['title']}
Post body: {post['body']}

Extract:
1. The core pain point
2. Lead type
3. 1–3 relevant marketing tags
4. ROI weight (1–5)
5. Justification

Respond in JSON as shown in the prompt."""}
    ]

def prepare_insight_batch(posts: List[dict]) -> List[Dict]:
    """Prepares GPT-4.1 insight batch payload."""
    payload = []
    for post in posts:
        messages = build_insight_prompt(post)
        payload.append({
            "id": post["id"],
            "messages": messages
        })
    return payload

def estimate_insight_cost(posts: List[dict], avg_tokens: int = 700, input_cost_per_1k: float = 2.0, output_cost_per_1k: float = 8.0) -> float:
    """Estimate GPT-4.1 cost for deep insight analysis."""
    total_input = len(posts) * avg_tokens
    total_output = len(posts) * 300  # assume 300 output tokens per post
    return (total_input / 1000 * input_cost_per_1k) + (total_output / 1000 * output_cost_per_1k)
