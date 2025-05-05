# reddit/discovery.py

import openai
import json
from config.config_loader import get_config

config = get_config()

def build_discovery_prompt(top_post_summaries: list[str]) -> list:
    """Builds the GPT prompt for discovering adjacent subreddits."""
    joined = "\n".join(f"- {summary}" for summary in top_post_summaries)
    return [
        {"role": "system", "content": "You are an expert in developer marketing and community discovery."},
        {"role": "user", "content": f"""Based on the following Reddit post summaries, suggest a ranked list of 12 relevant subreddits that are likely to contain pain points Cronlytic could solve.

Summaries:
{joined}

Respond in JSON format:
[
  {{
    "subreddit": "example",
    "reason": "...",
    "pain_signal_pct": 70,
    "solution_requests_pct": 40,
    "engagement_level": "medium"
  }},
  ...
]
"""}]

def discover_adjacent_subreddits(summaries: list[str], model="gpt-4.1") -> list:
    """Uses GPT-4.1 to suggest exploratory subreddits."""
    prompt = build_discovery_prompt(summaries)
    response = openai.ChatCompletion.create(
        model=model,
        messages=prompt,
        temperature=0.3
    )
    try:
        suggestions = json.loads(response['choices'][0]['message']['content'])
        return suggestions[:config["subreddits"]["exploratory_limit"]]
    except Exception as e:
        print(f"Error parsing GPT response: {e}")
        return []
