# reddit/rate_limiter.py
import time
from datetime import datetime, timedelta, timezone
from collections import deque
from config.config_loader import get_config
from utils.logger import setup_logger

log = setup_logger()
config = get_config()

class RedditRateLimiter:
    """Modern and efficient rate limiter using UTC-aware timestamps."""

    def __init__(self, requests_per_minute=None):
        self.limit = requests_per_minute or config["scraper"]["rate_limit_per_minute"]
        self.timestamps = deque(maxlen=self.limit)  # Prevents overgrowth
        log.info(f"Rate limiter initialized: {self.limit} requests/minute")

    def wait(self):
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=1)

        # Remove expired timestamps from the front
        while self.timestamps and self.timestamps[0] < window_start:
            self.timestamps.popleft()

        if len(self.timestamps) >= self.limit:
            wait_until = self.timestamps[0] + timedelta(minutes=1)
            sleep_time = (wait_until - now).total_seconds()
            log.debug(f"Rate limit hit. Sleeping for {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
            # Update time after waking up to avoid stale timestamp
            now = datetime.now(timezone.utc)

        self.timestamps.append(now)
