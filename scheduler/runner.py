# scheduler/runner.py

from reddit.scraper import scrape_all_configured_subreddits
from db.writer import insert_post, update_post_insight
from gpt.filters import prepare_batch_payload as prepare_filter_batch
from gpt.insights import prepare_insight_batch
from gpt.batch_api import generate_batch_payload, submit_batch_job, poll_batch_status, download_batch_results
from db.cleaner import clean_old_entries
from db.reader import get_top_posts_for_today
from config.config_loader import get_config
import json
import uuid
import os

config = get_config()

def run_daily_pipeline():
    print("[1] Cleaning old entries...")
    clean_old_entries()

    print("[2] Scraping Reddit posts...")
    scraped_posts = scrape_all_configured_subreddits()
    for post in scraped_posts:
        insert_post(post)

    print(f"[3] Preparing {len(scraped_posts)} posts for filtering...")
    filter_batch = prepare_filter_batch(scraped_posts)
    filter_file = generate_batch_payload(filter_batch, config["openai"]["model_filter"])
    batch_id = submit_batch_job(filter_file)
    poll_batch_status(batch_id)

    result_path = f"data/batch_responses/filter_result_{uuid.uuid4().hex}.jsonl"
    download_batch_results(batch_id, result_path)

    print("[4] Reading and selecting high-potential posts...")
    high_potential_posts = []
    with open(result_path, "r", encoding="utf-8") as f:
        for line in f:
            result = json.loads(line)
            post_id = result["id"]
            scores = json.loads(result["response"]["choices"][0]["message"]["content"])
            if scores["relevance_score"] >= 7 and scores["pain_point_clarity"] >= 7:
                high_potential_posts.append((post_id, scores))
                update_post_insight(post_id, scores)

    print(f"[5] Selected {len(high_potential_posts)} posts for deep analysis.")
    if not high_potential_posts:
        print("No high-value posts found today.")
        return

    deep_posts = [p for p in scraped_posts if p["id"] in [pid]()_]()_
