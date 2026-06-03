"""輔助的 DB writer helper — 不會覆寫原有 writer.py，供新的 batch metadata 使用。"""
from datetime import datetime
import sqlite3
from typing import List
try:
    # 嘗試重用現有的 reader 連線建立函式（如果 repo 已有）
    from db.reader import _get_connection
except Exception:
    def _get_connection():
        # fallback: 使用 data/db.sqlite（若你的 repo db path 不同請調整）
        return sqlite3.connect('data/db.sqlite', detect_types=sqlite3.PARSE_DECLTYPES)

import json
try:
    from utils.logger import setup_logger
    log = setup_logger()
except Exception:
    import logging
    log = logging.getLogger(__name__)

def insert_batch_metadata(batch_id: str, provider: str, estimated_cost: float = None):
    conn = _get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO batch_metadata (batch_id, provider, enqueued_at, status, estimated_cost, raw_response)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (batch_id, provider, datetime.utcnow().isoformat(), "enqueued", estimated_cost, None))
        conn.commit()
    except Exception as e:
        log.error(f"insert_batch_metadata error: {e}")

def batch_insert_posts(posts: List[dict], community_type: str = "primary"):
    if not posts:
        return
    conn = _get_connection()
    try:
        conn.execute("BEGIN")
        rows = []
        for p in posts:
            rows.append((
                p.get("id"), p.get("url"), p.get("title"), p.get("body", ""), p.get("subreddit"),
                p.get("created_utc"), datetime.utcnow().isoformat(), community_type, p.get("type", "post"), p.get("post_body", ""), p.get("parent_post_id")
            ))
        conn.executemany("""
            INSERT OR IGNORE INTO posts (id, url, title, body, subreddit, created_utc, processed_at, community_type, type, post_body, parent_post_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.error(f"batch_insert_posts failed: {e}")

