# reddit/rate_limiter.py

import time
from threading import Lock

class RedditRateLimiter:
    def __init__(self, max_requests_per_minute=60):
        self.max_requests = max_requests_per_minute
        self.interval = 60.0 / self.max_requests
        self.lock = Lock()
        self.last_request_time = 0

    def wait(self):
        """Wait to respect rate limit before sending the next request."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.interval:
                sleep_time = self.interval - elapsed
                time.sleep(sleep_time)
            self.last_request_time = time.time()
