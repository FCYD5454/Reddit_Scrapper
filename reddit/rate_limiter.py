# reddit/rate_limiter.py

import time
from datetime import datetime, timedelta
from config.config_loader import get_config
from utils.logger import setup_logger

log = setup_logger()
config = get_config()

class RedditRateLimiter:
    """Rate limiter for Reddit API calls."""

    def __init__(self, requests_per_minute=None):
        self.requests_per_minute = requests_per_minute or config["scraper"]["rate_limit_per_minute"]
        self.request_timestamps = []
        log.info(f"Rate limiter initialized: {self.requests_per_minute} requests/minute")

    def wait(self):
        """Waits if the request rate has exceeded the limit."""
        now = datetime.utcnow()

        # Remove timestamps older than 60 seconds
        self.request_timestamps = [ts for ts in self.request_timestamps if now - ts < timedelta(minutes=1)]

        if len(self.request_timestamps) >= self.requests_per_minute:
            oldest = min(self.request_timestamps)
            wait_time = (oldest + timedelta(minutes=1) - now).total_seconds()
            if wait_time > 0:
                log.debug(f"Rate limit hit. Sleeping for {wait_time:.2f} seconds...")
                time.sleep(wait_time)

        self.request_timestamps.append(datetime.utcnow())

# Instantiate global limiter
reddit_rate_limiter = RedditRateLimiter()
