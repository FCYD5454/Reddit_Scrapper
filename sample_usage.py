# sample_usage.py

"""
Demonstrate the flow of loading and using prompt templates with sample data.
"""

import os
import json

# Mock data - sample Reddit post
SAMPLE_POST = {
    "id": "sample123",
    "title": "Need a way to run scheduled API calls without a server",
    "body": "I'm building a small SaaS and need to send notifications to users on a schedule. I don't want to maintain a server just to run cron jobs. What's a good cloud solution for this problem?",
    "subreddit": "webdev",
    "created_utc": 1650000000.0,
    "url": "https://www.reddit.com/r/webdev/comments/sample123/need_a_way_to_run_scheduled_api_calls_without_a/"
}

def read_prompt_template(file_path):
    """Read a prompt template from file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error loading prompt template: {str(e)}")
        return "Default fallback prompt"

def build_filter_prompt(post, template):
    """Build a filter prompt using the template and post data."""
    return [
        {"role": "system", "content": "You are a marketing assistant scoring Reddit posts for product relevance."},
        {"role": "user", "content": f"""Post title: {post['title']}
Post body: {post['body']}

{template}"""}
    ]

def build_insight_prompt(post, template):
    """Build an insight prompt using the template and post data."""
    return [
        {"role": "system", "content": "You are a SaaS strategist extracting pain points and marketing tags from Reddit posts."},
        {"role": "user", "content": f"""Post title: {post['title']}
Post body: {post['body']}

{template}"""}
    ]

def build_discovery_prompt(summaries, template):
    """Build a discovery prompt using the template and summaries."""
    joined = "\n".join(f"- {summary}" for summary in summaries)
    prompt_content = template.replace("{SUMMARIES}", joined)

    return [
        {"role": "system", "content": "You are an expert in developer marketing and community discovery."},
        {"role": "user", "content": prompt_content}
    ]

def main():
    """Demonstrate loading and using prompts."""
    # Load all prompt templates
    filter_template = read_prompt_template("gpt/prompts/filter_prompt.txt")
    insight_template = read_prompt_template("gpt/prompts/insight_prompt.txt")
    discovery_template = read_prompt_template("gpt/prompts/community_discovery.txt")

    print("\n=== FILTER PROMPT TEMPLATE ===")
    print(filter_template[:100] + "...")

    print("\n=== INSIGHT PROMPT TEMPLATE ===")
    print(insight_template[:100] + "...")

    print("\n=== DISCOVERY PROMPT TEMPLATE ===")
    print(discovery_template[:100] + "...")

    # Demonstrate building prompts with real data
    print("\n=== SAMPLE USAGE ===")

    # 1. Filter prompt
    filter_prompt = build_filter_prompt(SAMPLE_POST, filter_template)
    print("\nFilter prompt:")
    print(json.dumps(filter_prompt, indent=2)[:200] + "...\n")

    # 2. Insight prompt
    insight_prompt = build_insight_prompt(SAMPLE_POST, insight_template)
    print("\nInsight prompt:")
    print(json.dumps(insight_prompt, indent=2)[:200] + "...\n")

    # 3. Discovery prompt
    sample_summaries = [
        "Need a way to run scheduled API calls without a server",
        "Looking for a solution to run cron jobs in the cloud",
        "How to schedule tasks without maintaining infrastructure?"
    ]
    discovery_prompt = build_discovery_prompt(sample_summaries, discovery_template)
    print("\nDiscovery prompt:")
    print(json.dumps(discovery_prompt, indent=2)[:200] + "...\n")

    print("\nAll prompts built successfully from templates!")

if __name__ == "__main__":
    main()