# scheduler/runner.py
import json
import uuid
import os
import time
from datetime import datetime
from reddit.scraper import scrape_all_configured_subreddits
from db.writer import insert_post, update_post_insight
from db.reader import get_top_posts_for_today
from db.schema import create_tables
from gpt.filters import prepare_batch_payload as prepare_filter_batch, estimate_batch_cost as estimate_filter_cost
from gpt.insights import prepare_insight_batch, estimate_insight_cost
from gpt.batch_api import generate_batch_payload, submit_batch_job, poll_batch_status, download_batch_results, add_estimated_batch_cost
from db.cleaner import clean_old_entries
from scheduler.cost_tracker import initialize_cost_tracking, can_process_batch
from config.config_loader import get_config
from utils.logger import setup_logger
from utils.helpers import ensure_directory_exists

log = setup_logger()
config = get_config()


def split_batch_by_token_limit(payload, model: str, token_limit: int = 1_000_000):
    batches = []
    current_batch = []
    current_tokens = 0

    for item in payload:
        tokens = item.get("meta", {}).get("estimated_tokens", 300)
        if current_tokens + tokens > token_limit:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(item)
        current_tokens += tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def run_daily_pipeline():
    log.info("\U0001F680 Starting Reddit scraping and analysis pipeline")

    ensure_directory_exists("data")
    ensure_directory_exists("data/batch_responses")
    create_tables()
    initialize_cost_tracking()

    log.info("Step 1: Cleaning old database entries...")
    clean_old_entries()

    log.info("Step 2: Scraping Reddit posts...")
    scraped_posts = scrape_all_configured_subreddits()
    if not scraped_posts:
        log.warning("No posts found to analyze. Exiting pipeline.")
        return

    log.info(f"Found {len(scraped_posts)} posts to analyze")

    log.info("Step 3: Preparing posts for filtering...")
    filter_batch = prepare_filter_batch(scraped_posts)
    filter_cost = estimate_filter_cost(scraped_posts)
    log.info(f"Estimated cost for filtering: ${filter_cost:.2f}")

    if not can_process_batch(filter_cost):
        log.error("Insufficient budget for filtering. Exiting pipeline.")
        return

    model_filter = config["openai"]["model_filter"]
    filter_batches = split_batch_by_token_limit(filter_batch, model_filter)
    all_result_paths = []

    for i, batch in enumerate(filter_batches):
        log.info(f"Submitting sub-batch {i + 1}/{len(filter_batches)} with {len(batch)} entries...")
        filter_file = generate_batch_payload(batch, model_filter)
        add_estimated_batch_cost(batch, model_filter)

        try:
            batch_id = submit_batch_job(filter_file)
            log.info(f"Batch job submitted with ID: {batch_id}")
            batch_result = poll_batch_status(batch_id)
            if batch_result.status != "completed":
                log.error(f"Batch job failed with status: {batch_result.status}")
                continue

            result_path = f"data/batch_responses/filter_result_{uuid.uuid4().hex}.jsonl"
            download_batch_results(batch_id, result_path)
            all_result_paths.append(result_path)
        except Exception as e:
            log.error(f"Error in filtering batch: {str(e)}")
            continue

    log.info("Step 4: Selecting high-potential posts...")
    high_potential_posts = []
    high_potential_ids = set()

    try:
        for result_path in all_result_paths:
            with open(result_path, "r", encoding="utf-8") as f:
                for line in f:
                    result = json.loads(line)
                    post_id = result["custom_id"]
                    content = result["response"]["choices"][0]["message"]["content"]

                    try:
                        scores = json.loads(content)
                        weights = config["scoring"]
                        weighted_score = (
                            scores["relevance_score"] * weights["relevance_weight"] +
                            scores["emotional_intensity"] * weights["emotion_weight"] +
                            scores["pain_point_clarity"] * weights["pain_point_weight"]
                        )
                        if weighted_score >= 7.0:
                            high_potential_ids.add(post_id)
                            high_potential_posts.append((post_id, scores))
                            update_post_insight(post_id, scores)
                    except Exception as e:
                        log.error(f"Error parsing result for post {post_id}: {str(e)}")
    except Exception as e:
        log.error(f"Error reading filter results: {str(e)}")
        return

    output_limit = config["scoring"]["output_top_n"]
    high_potential_count = len(high_potential_posts)
    log.info(f"Selected {high_potential_count} posts for deep analysis.")
    if high_potential_count == 0:
        log.info("No high-value posts found. Exiting pipeline.")
        return

    deep_posts = [p for p in scraped_posts if p["id"] in high_potential_ids]
    insight_batch = prepare_insight_batch(deep_posts)
    insight_cost = estimate_insight_cost(insight_batch)
    log.info(f"Estimated cost for insight analysis: ${insight_cost:.2f}")

    if not can_process_batch(insight_cost):
        log.error("Insufficient budget for insight analysis. Exiting pipeline.")
        return

    log.info(f"Submitting batch of {len(insight_batch)} posts for deep analysis...")
    insight_file = generate_batch_payload(insight_batch, config["openai"]["model_deep"])
    add_estimated_batch_cost(insight_batch, config["openai"]["model_deep"])

    try:
        insight_batch_id = submit_batch_job(insight_file)
        log.info(f"Insight batch job submitted with ID: {insight_batch_id}")
        insight_result = poll_batch_status(insight_batch_id)
        if insight_result.status != "completed":
            log.error(f"Insight batch job failed with status: {insight_result.status}")
            return

        insight_path = f"data/batch_responses/insight_result_{uuid.uuid4().hex}.jsonl"
        download_batch_results(insight_batch_id, insight_path)
    except Exception as e:
        log.error(f"Error in insight batch: {str(e)}")
        return

    log.info("Step 6: Updating posts with deep insights...")
    try:
        with open(insight_path, "r", encoding="utf-8") as f:
            for line in f:
                result = json.loads(line)
                post_id = result["custom_id"]
                content = result["response"]["choices"][0]["message"]["content"]

                try:
                    insight = json.loads(content)
                    update_post_insight(post_id, insight)
                except Exception as e:
                    log.error(f"Error parsing insight for post {post_id}: {str(e)}")
    except Exception as e:
        log.error(f"Error reading insight results: {str(e)}")

    top_posts = get_top_posts_for_today(limit=output_limit)
    log.info(f"✅ Pipeline finished. Found {len(top_posts)} qualified leads.")

    for i, post in enumerate(top_posts[:5], 1):
        log.info(f"{i}. [{post['subreddit']}] {post['title']} - {post['url']}")


if __name__ == "__main__":
    run_daily_pipeline()
