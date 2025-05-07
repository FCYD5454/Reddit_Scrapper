# db/writer.py
import sqlite3
from config.config_loader import get_config
from datetime import datetime
from pathlib import Path

config = get_config()
DB_PATH = config["database"]["path"]

_conn = None

def _get_connection():
    global _conn
    if _conn is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL;")
    return _conn

def insert_post(post: dict, community_type: str = "primary"):
    """Insert a new Reddit post or comment into the posts table."""
    conn = _get_connection()
    try:
        conn.execute("""
        INSERT OR IGNORE INTO posts (
            id, url, title, body, subreddit, created_utc, last_active,
            processed_at, community_type, type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post["id"],
            post["url"],
            post["title"],
            post.get("body", ""),
            post["subreddit"],
            post["created_utc"],
            post["created_utc"],
            datetime.utcnow().isoformat(),
            community_type,
            post.get("type", "post")
        ))

        conn.execute("""
        INSERT OR IGNORE INTO history (id, processed_at)
        VALUES (?, ?)
        """, (
            post["id"],
            datetime.utcnow().isoformat()
        ))

        conn.commit()
    except sqlite3.Error as e:
        print(f"[SQLite Insert Error] {e}")

def update_post_insight(post_id: str, insight: dict):
    """Update an existing post with scoring/insight results."""
    conn = _get_connection()
    try:
        conn.execute("""
        UPDATE posts SET
            relevance_score = ?,
            emotion_score = ?,
            pain_score = ?,
            lead_type = ?,
            tags = ?,
            roi_weight = ?
        WHERE id = ?
        """, (
            insight.get("relevance_score"),
            insight.get("emotional_intensity"),
            insight.get("pain_point_clarity"),
            insight.get("lead_type"),
            ", ".join(insight.get("tags", [])),
            insight.get("roi_weight"),
            post_id
        ))
        conn.commit()
    except sqlite3.Error as e:
        print(f"[SQLite Update Error] {e}")

def mark_insight_processed(post_id: str):
    """Mark a post as having been processed for deep insight."""
    conn = _get_connection()
    try:
        conn.execute("""
        UPDATE posts SET insight_processed = 1
        WHERE id = ?
        """, (post_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"[SQLite mark_insight_processed Error] {e}")
