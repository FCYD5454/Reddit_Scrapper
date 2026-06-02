# reddit/scraper.py

import datetime
import os
import socket
import time
import random
import requests

from db.reader import is_already_processed
from db.writer import insert_post
from reddit.discovery import discover_adjacent_subreddits
from config.config_loader import get_config
from utils.logger import setup_logger
from utils.helpers import load_json, save_json, truncate
from reddit.rate_limiter import RedditRateLimiter

socket.setdefaulttimeout(10)  # Set global 10s timeout for HTTP

log = setup_logger()
config = get_config()

limiter = RedditRateLimiter(config["scraper"].get("rate_limit_per_minute", 30))
EXPLORATORY_FILE = "data/exploratory_subreddits.json"

# Robust list of desktop user agents to prevent Reddit blocks (429)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]


# ---------------------------------------------------------------------------
# Mock classes to match PRAW objects perfectly so AI/DB flows remain untouched
# ---------------------------------------------------------------------------

class MockComment:
    """Mock a PRAW Comment object."""
    def __init__(self, data: dict):
        self.id = data.get("id")
        self.created_utc = data.get("created_utc")
        self.body = data.get("body", "")
        self.permalink = data.get("permalink", "")


class MockComments:
    """Mock a PRAW Comments collection."""
    def __init__(self, comment_list: list):
        self._comments = comment_list

    def replace_more(self, limit=0):
        # Public JSON API already returns all comments, so this is a no-op
        pass

    def list(self) -> list:
        return self._comments


class MockPost:
    """Mock a PRAW Submission (Post) object."""
    def __init__(self, data: dict, comments_list: list = None):
        self.id = data.get("id")
        self.title = data.get("title", "")
        self.selftext = data.get("selftext", "") or data.get("body", "")
        self.created_utc = data.get("created_utc")
        self.permalink = data.get("permalink", "")
        self.comments = MockComments(comments_list or [])


# ---------------------------------------------------------------------------
# Public JSON Scraper Functions (No API Key Required)
# ---------------------------------------------------------------------------

def get_reddit_json(url: str, params: dict = None) -> list:
    """Fetch public JSON data from Reddit with automated exponential backoff on 429."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.reddit.com/",
    }

    backoff = 2.0
    for attempt in range(4):
        try:
            # Respect rate limiter before making request
            limiter.wait()
            resp = requests.get(url, headers=headers, params=params, timeout=15)

            if resp.status_code == 429:
                log.warning(
                    f"Reddit returned 429 (Too Many Requests). "
                    f"Backing off for {backoff:.1f}s (attempt {attempt+1}/4)..."
                )
                time.sleep(backoff)
                backoff *= 2
                continue

            resp.raise_for_status()
            return resp.json()

        except Exception as e:
            if attempt < 3:
                log.warning(f"Error fetching {url}: {e}. Retrying in {backoff:.1f}s...")
                time.sleep(backoff)
                backoff *= 2
            else:
                log.error(f"Failed to fetch {url} after {attempt + 1} attempts: {e}")
                raise
    return []


def parse_comments_tree_recursive(node: dict, list_out: list):
    """Recursively parse nested Reddit comment children into a flat list."""
    if not node or not isinstance(node, dict):
        return

    kind = node.get("kind")
    data = node.get("data", {})

    if kind == "t1":  # t1 represents comment objects
        body = data.get("body")
        comment_id = data.get("id")
        if comment_id and body:
            list_out.append(MockComment({
                "id": comment_id,
                "created_utc": data.get("created_utc"),
                "body": body,
                "permalink": data.get("permalink", ""),
            }))

    # Recursively fetch nested replies
    replies = data.get("replies")
    if replies and isinstance(replies, dict):
        replies_data = replies.get("data", {})
        for child in replies_data.get("children", []):
            parse_comments_tree_recursive(child, list_out)


def fetch_comments_for_post(subreddit_name: str, post_id: str) -> list:
    """Fetch and parse all public comments for a specific post."""
    url = f"https://www.reddit.com/r/{subreddit_name}/comments/{post_id}.json"
    try:
        data = get_reddit_json(url)
        if not data or not isinstance(data, list) or len(data) < 2:
            return []

        comment_root = data[1]
        comment_list = []
        if isinstance(comment_root, dict):
            children = comment_root.get("data", {}).get("children", [])
            for child in children:
                parse_comments_tree_recursive(child, comment_list)
        return comment_list
    except Exception as e:
        log.warning(f"Failed to fetch comments for post {post_id}: {e}")
        return []


def fetch_posts_from_subreddit(subreddit_name: str, limit: int = 100) -> list:
    """Scrape subreddit posts using public JSON feeds instead of PRAW."""
    min_days = config["scraper"]["min_post_age_days"]
    max_days = config["scraper"]["max_post_age_days"]
    include_comments = config["scraper"].get("include_comments", False)
    results = []
    seen_ids = set()

    post_skip_seen = 0
    post_skip_age = 0
    post_skip_dupl = 0
    post_remaining = 0
    comment_fetched = 0
    comment_skip_seen = 0
    comment_skip_age = 0
    comment_skip_dupl = 0
    comment_remaining = 0

    log.info(f"Fetching posts from r/{subreddit_name} using public JSON API...")
    combined_raw_posts = []

    # Scrape Top, Hot, and New feeds
    for feed in ("top", "hot", "new"):
        url = f"https://www.reddit.com/r/{subreddit_name}/{feed}.json"
        params = {"limit": limit}
        if feed == "top":
            params["t"] = "month"

        try:
            data = get_reddit_json(url, params=params)
            if data and isinstance(data, dict):
                children = data.get("data", {}).get("children", [])
                combined_raw_posts.extend(children)
        except Exception as e:
            log.error(f"Error fetching {feed} feed from r/{subreddit_name}: {e}")

    log.info(f"Total fetched raw posts to process from r/{subreddit_name}: {len(combined_raw_posts)}")
    start_time = time.time()

    for i, child in enumerate(combined_raw_posts):
        p_data = child.get("data", {})
        post_id = p_data.get("id")
        if not p_data or not post_id:
            continue

        if i % 10 == 0:
            log.info(f"Processing post #{i+1}/{len(combined_raw_posts)}")

        if post_id in seen_ids:
            post_skip_seen += 1
            continue
        seen_ids.add(post_id)

        # Build mock post object
        post = MockPost(p_data)
        created_at = datetime.datetime.fromtimestamp(post.created_utc)
        log.debug(f"Post {post.id} at {created_at.isoformat()} — {post.title[:60]}")

        if not is_post_in_age_range(post, min_days, max_days):
            post_skip_age += 1
            continue
        if is_already_processed(post.id):
            post_skip_dupl += 1
            continue

        # If comments are enabled, scrape the post's comment tree
        comments_list = []
        if include_comments:
            # 2 second delay to prevent rapid scraping blocks
            time.sleep(2.0)
            comments_list = fetch_comments_for_post(subreddit_name, post_id)
            comment_fetched += len(comments_list)
            post.comments = MockComments(comments_list)

        results.append({
            "id": post.id,
            "title": post.title,
            "body": post.selftext,
            "created_utc": post.created_utc,
            "subreddit": subreddit_name,
            "url": f"https://www.reddit.com{post.permalink}",
            "type": "post"
        })
        post_remaining += 1

        if include_comments and comments_list:
            for comment in comments_list:
                if comment.id in seen_ids:
                    comment_skip_seen += 1
                    continue
                seen_ids.add(comment.id)

                if not is_post_in_age_range(comment, min_days, max_days):
                    comment_skip_age += 1
                    continue
                if is_already_processed(comment.id):
                    comment_skip_dupl += 1
                    continue

                results.append({
                    "id": comment.id,
                    "title": post.title,
                    "body": comment.body,
                    "post_body": post.selftext,
                    "created_utc": comment.created_utc,
                    "subreddit": subreddit_name,
                    "url": f"https://www.reddit.com{comment.permalink}",
                    "type": "comment",
                    "parent_post_id": post.id,
                })
                comment_remaining += 1

    sum_fetched = len(combined_raw_posts) + comment_fetched
    sum_skip_seen = post_skip_seen + comment_skip_seen
    sum_skip_age = post_skip_age + comment_skip_age
    sum_skip_dupl = post_skip_dupl + comment_skip_dupl

    log.info(f"{'r/' + subreddit_name:<25} | {'Fetched':<12} | {'Skip (seen)':<12} | {'Skip (age)':<12} | {'Skip (dup)':<12} | {'Remaining':<12}")
    log.info(f"{'Posts':<25} | {len(combined_raw_posts):<12} | {post_skip_seen:<12} | {post_skip_age:<12} | {post_skip_dupl:<12} | {post_remaining:<12}")
    log.info(f"{'Comments':<25} | {comment_fetched:<12} | {comment_skip_seen:<12} | {comment_skip_age:<12} | {comment_skip_dupl:<12} | {comment_remaining:<12}")
    log.info(f"{'Sum':<25} | {sum_fetched:<12} | {sum_skip_seen:<12} | {sum_skip_age:<12} | {sum_skip_dupl:<12} | {len(results):<12}")

    log.info(f"Finished processing posts from r/{subreddit_name} in {time.time() - start_time:.2f} seconds")
    return results


def is_post_in_age_range(post, min_days, max_days) -> bool:
    post_date = datetime.datetime.fromtimestamp(post.created_utc)
    age_days = (datetime.datetime.utcnow() - post_date).days
    return min_days <= age_days <= max_days


def get_exploratory_subreddits():
    if not os.path.exists(EXPLORATORY_FILE):
        return []

    data = load_json(EXPLORATORY_FILE)
    last_updated = data.get("last_updated", "")
    refresh_days = config["subreddits"]["exploratory_refresh_days"]

    if not last_updated or (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(last_updated)).days >= refresh_days:
        log.info("Exploratory subreddit list needs refresh")
        return []

    return data.get("subreddits", [])


def update_exploratory_subreddits(new_subreddits):
    data = {
        "last_updated": datetime.datetime.utcnow().isoformat(),
        "subreddits": new_subreddits
    }
    os.makedirs("data", exist_ok=True)
    save_json(data, EXPLORATORY_FILE)
    log.info(f"Updated exploratory subreddits: {', '.join(new_subreddits)}")


def scrape_subreddits() -> list:
    """Scrapes the configured subreddits as well as exploratory ones."""
    primary_subreddits = config["subreddits"]["primary"]
    primary_pct = config["subreddits"]["primary_percentage"]
    exploratory_pct = config["subreddits"]["exploratory_percentage"]
    exploratory_limit = config["subreddits"]["exploratory_limit"]

    total_limit = config["scraper"]["max_items_per_day"]
    primary_limit = int((primary_pct / 100) * total_limit)
    exploratory_limit_posts = int((exploratory_pct / 100) * total_limit)

    log.info(f"Scraping {len(primary_subreddits)} primary subreddits...")
    per_primary_subreddit = max(1, primary_limit // len(primary_subreddits))
    primary_posts = []

    for sub in primary_subreddits:
        posts = fetch_posts_from_subreddit(sub, limit=per_primary_subreddit)
        for post in posts:
            insert_post(post, community_type="primary")
        primary_posts.extend(posts)

    exploratory_subreddits = get_exploratory_subreddits()

    if not exploratory_subreddits:
        if primary_posts:
            log.info("Discovering new exploratory subreddits...")
            summaries = [truncate(f"{p['title']} {p['body']}", 300) for p in primary_posts[:10]]
            suggestions = discover_adjacent_subreddits(summaries)
            exploratory_subreddits = [s["subreddit"] for s in suggestions][:exploratory_limit]
            update_exploratory_subreddits(exploratory_subreddits)
        else:
            log.warning("No primary posts found to discover exploratory subreddits")

    if exploratory_subreddits:
        log.info(f"Scraping {len(exploratory_subreddits)} exploratory subreddits...")
        per_exploratory = max(1, exploratory_limit_posts // len(exploratory_subreddits))

        for sub in exploratory_subreddits:
            posts = fetch_posts_from_subreddit(sub, limit=per_exploratory)
            for post in posts:
                insert_post(post, community_type="exploratory")
            primary_posts.extend(posts)

    log.info(f"Total items scraped: {len(primary_posts)}")
    return primary_posts
