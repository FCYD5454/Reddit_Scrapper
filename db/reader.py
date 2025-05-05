# db/reader.py

import sqlite3
from datetime import datetime
from config.config_loader import get_config

config = get_config()
DB_PATH = config["database"]["path"]

def is_already_processed(post_id: str) -> bool:
    """Check if a post or comment has already been processed."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM history WHERE id = ?", (post_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_top_posts_for_today(limit=10) -> list:
    """Fetch top posts processed today, sorted by ROI and score."""
    today = datetime.utcnow().date().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
    SELECT * FROM posts
    WHERE processed_at >= ?
    ORDER BY roi_weight DESC, relevance_score DESC
    LIMIT ?
    """, (today, limit))

    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_posts_by_tag(tag: str) -> list:
    """Returns all posts or comments containing a specific tag."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
    SELECT * FROM posts
    WHERE tags LIKE ?
    ORDER BY processed_at DESC
    """, (f"%{tag}%",))

    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]
