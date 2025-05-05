# gpt/insights.py

import os
from typing import List, Dict, Any
from utils.helpers import estimate_tokens
from utils.logger import setup_logger
from config.config_loader import get_config

log = setup_logger()
config = get_config()
PROMPT_PATH = "gpt/prompts/insight_prompt.txt"


def load_insight_prompt_template() -> str:
    """Load the insight prompt template from file."""
    try:
        with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        log.error(f"Error loading insight prompt template: {str(e)}")
        return (
            "Extract:\n"
            "1. The core pain point\n"
            "2. Lead type\n"
            "3. 1–3 relevant marketing tags\n"
            "4. ROI weight (1–5)\n"
            "5. Justification\n\n"
            "Respond with JSON."
        )


INSIGHT_PROMPT_TEMPLATE = load_insight_prompt_template()


def build_insight_prompt(post: dict) -> List[Dict[str, str]]:
    """Constructs the GPT-4.1 prompt for extracting deeper insights using template."""
    return [
        {
            "role": "system",
            "content": "You are a SaaS strategist extracting pain points and marketing tags from Reddit posts."
        },
        {
            "role": "user",
            "content": f"Post title: {post['title']}\nPost body: {post['body']}\n\n{INSIGHT_PROMPT_TEMPLATE}"
        }
    ]


def prepare_insight_batch(posts: List[dict]) -> List[Dict[str, Any]]:
    """Prepares GPT-4.1 insight batch payload."""
    model = config["openai"].get("model_deep", "gpt-4.1")
    payload = []
    for post in posts:
        messages = build_insight_prompt(post)
        payload.append({
            "id": post["id"],
            "messages": messages,
            "meta": {
                "estimated_tokens": estimate_tokens(
                    post.get("title", "") + post.get("body", ""), model
                )
            }
        })
    return payload


def estimate_insight_cost(posts: List[dict], avg_tokens: int = 700, input_cost_per_1k: float = 2.0, output_cost_per_1k: float = 8.0) -> float:
    """Estimate GPT-4.1 cost for deep insight analysis."""
    total_input = len(posts) * avg_tokens
    total_output = len(posts) * 300
    return (total_input / 1000 * input_cost_per_1k) + (total_output / 1000 * output_cost_per_1k)
