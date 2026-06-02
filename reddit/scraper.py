# reddit/scraper.py

import datetime
import os
import socket
import time
import random
from playwright.sync_api import sync_playwright

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

# List of real-world user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
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
# Playwright Scraping Pipeline for old.reddit.com (Bypasses Cloudflare)
# ---------------------------------------------------------------------------

def fetch_posts_from_subreddit(subreddit_name: str, limit: int = 100) -> list:
    """Scrape subreddit posts using Playwright headless browser on old.reddit.com."""
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

    log.info(f"Fetching posts from r/{subreddit_name} via Playwright (old.reddit.com)...")
    start_time = time.time()

    raw_posts = []

    with sync_playwright() as p:
        # Launch Chromium headless with anti-automation stealth flags
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        # Target Hot, Top, and New feeds on old.reddit.com
        feeds = [
            ("hot", f"https://old.reddit.com/r/{subreddit_name}/"),
            ("top", f"https://old.reddit.com/r/{subreddit_name}/top/?t=month"),
            ("new", f"https://old.reddit.com/r/{subreddit_name}/new/")
        ]

        for feed_name, url in feeds:
            try:
                log.info(f"→ Navigating to {feed_name} feed: {url}")
                page.goto(url, timeout=30000)
                
                # Check for "Over 18" NSFW click-through screen
                nsfw_btn = page.query_selector("button[name='over18'][value='yes']")
                if nsfw_btn:
                    log.info("NSFW warning detected. Clicking Yes to proceed...")
                    nsfw_btn.click()
                    page.wait_for_timeout(1000)

                # Wait for main posts table to load
                page.wait_for_selector("#siteTable", timeout=15000)
                page.wait_for_timeout(random.randint(1000, 2000))

                # Find all post container elements (div.thing)
                things = page.query_selector_all("#siteTable div.thing")
                log.info(f"Found {len(things)} posts in {feed_name} feed.")

                count = 0
                for thing in things:
                    if count >= limit:
                        break

                    fullname = thing.get_attribute("data-fullname")
                    if not fullname or not fullname.startswith("t3_"):
                        continue
                    post_id = fullname[3:]

                    if post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)

                    title_elem = thing.query_selector("a.title")
                    title = title_elem.inner_text() if title_elem else ""

                    permalink = thing.get_attribute("data-permalink") or ""

                    # Extract created_utc from <time> datetime attribute
                    time_elem = thing.query_selector("time.live-timestamp")
                    created_utc = time.time()
                    if time_elem:
                        dt_attr = time_elem.get_attribute("datetime")
                        if dt_attr:
                            try:
                                dt = datetime.datetime.fromisoformat(dt_attr.replace("Z", "+00:00"))
                                created_utc = dt.timestamp()
                            except Exception:
                                pass

                    # Extract selftext by clicking expando button if it's a text post
                    selftext = ""
                    expando_btn = thing.query_selector("div.expando-button.selftext.collapsed")
                    if expando_btn:
                        try:
                            expando_btn.click()
                            page.wait_for_timeout(400)  # Wait briefly for expando DOM to render
                            md_elem = thing.query_selector("div.expando div.md")
                            if md_elem:
                                selftext = md_elem.inner_text()
                        except Exception as e:
                            log.debug(f"Failed to click expando for post {post_id}: {e}")

                    raw_posts.append({
                        "id": post_id,
                        "title": title,
                        "selftext": selftext,
                        "created_utc": created_utc,
                        "permalink": permalink,
                    })
                    count += 1

            except Exception as e:
                log.error(f"Failed to scrape feed {feed_name} for r/{subreddit_name}: {e}")

        # Post-process all fetched raw posts
        for p_data in raw_posts:
            post = MockPost(p_data)
            created_at = datetime.datetime.fromtimestamp(post.created_utc)
            log.debug(f"Post {post.id} at {created_at.isoformat()} — {post.title[:60]}")

            if not is_post_in_age_range(post, min_days, max_days):
                post_skip_age += 1
                continue
            if is_already_processed(post.id):
                post_skip_dupl += 1
                continue

            comments_list = []
            if include_comments and p_data.get("permalink"):
                try:
                    comments_url = f"https://old.reddit.com{p_data['permalink']}"
                    log.info(f"→ Navigating to comments page: {comments_url}")
                    page.goto(comments_url, timeout=25000)
                    page.wait_for_timeout(random.randint(1000, 2000))

                    # Parse all comment containers (div.comment)
                    comment_divs = page.query_selector_all("div.comment")
                    log.info(f"Found {len(comment_divs)} comment elements on page.")

                    for c_div in comment_divs:
                        c_fullname = c_div.get_attribute("data-fullname")
                        if not c_fullname or not c_fullname.startswith("t1_"):
                            continue
                        c_id = c_fullname[3:]

                        md_elem = c_div.query_selector("div.md")
                        c_body = md_elem.inner_text() if md_elem else ""

                        time_elem = c_div.query_selector("time.live-timestamp")
                        c_utc = time.time()
                        if time_elem:
                            dt_attr = time_elem.get_attribute("datetime")
                            if dt_attr:
                                try:
                                    dt = datetime.datetime.fromisoformat(dt_attr.replace("Z", "+00:00"))
                                    c_utc = dt.timestamp()
                                except Exception:
                                    pass

                        # Extract comment permalink
                        c_perma = ""
                        perma_elem = c_div.query_selector("a.bylink")
                        if perma_elem:
                            c_perma = perma_elem.get_attribute("href") or ""

                        comments_list.append(MockComment({
                            "id": c_id,
                            "created_utc": c_utc,
                            "body": c_body,
                            "permalink": c_perma,
                        }))

                except Exception as e:
                    log.warning(f"Failed to scrape comments for post {post.id}: {e}")

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

        browser.close()

    sum_fetched = len(raw_posts) + comment_fetched
    sum_skip_seen = post_skip_seen + comment_skip_seen
    sum_skip_age = post_skip_age + comment_skip_age
    sum_skip_dupl = post_skip_dupl + comment_skip_dupl

    log.info(f"r/{subreddit_name:<25} | {'Fetched':<12} | {'Skip (seen)':<12} | {'Skip (age)':<12} | {'Skip (dup)':<12} | {'Remaining':<12}")
    log.info(f"{'Posts':<25} | {len(raw_posts):<12} | {post_skip_seen:<12} | {post_skip_age:<12} | {post_skip_dupl:<12} | {post_remaining:<12}")
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
