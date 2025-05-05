# reddit/scraper.py

import praw
import datetime
from db.reader import is_already_processed
from config.config_loader import get_config

config = get_config()

reddit = praw.Reddit(
    client_id=config["reddit"]["client_id"],
    client_secret=config["reddit"]["client_secret"],
    user_agent=config["reddit"]["user_agent"]
)

def is_post_in_age_range(post, min_days, max_days) -> bool:
    """Check if post is within the configured age window."""
    post_date = datetime.datetime.fromtimestamp(post.created_utc)
    age_days = (datetime.datetime.utcnow() - post_date).days
    return min_days <= age_days <= max_days

def fetch_posts_from_subreddit(subreddit_name, limit=50) -> list:
    """Fetches new posts from a single subreddit within age range."""
    min_days = config["scraper"]["min_post_age_days"]
    max_days = config["scraper"]["max_post_age_days"]
    results = []

    subreddit = reddit.subreddit(subreddit_name)
    for post in subreddit.new(limit=limit):
        if not is_post_in_age_range(post, min_days, max_days):
            continue
        if is_already_processed(post.id):
            continue
        results.append({
            "id": post.id,
            "title": post.title,
            "body": post.selftext,
            "created_utc": post.created_utc,
            "subreddit": subreddit_name,
            "url": f"https://www.reddit.com{post.permalink}"
        })
    return results

def scrape_all_configured_subreddits() -> list:
    """Scrapes posts from primary and exploratory subreddits."""
    subreddits = config["subreddits"]["primary"]
    primary_pct = config["subreddits"]["primary_percentage"]
    exploratory_pct = config["subreddits"]["exploratory_percentage"]

    total_limit = config["scraper"]["max_items_per_day"]
    primary_limit = int((primary_pct / 100) * total_limit)
    per_subreddit = max(1, primary_limit // len(subreddits))

    all_posts = []
    for sub in subreddits:
        all_posts += fetch_posts_from_subreddit(sub, limit=per_subreddit)

    return all_posts
