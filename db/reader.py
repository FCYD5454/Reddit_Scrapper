# db/reader.py

import sqlite3
from datetime import datetime
from config.config_loader import get_config
from pathlib import Path

config = get_config()
DB_PATH = config["database"]["path"]

# Initialize shared read-only connection with WAL mode
_conn = None

def _get_connection():
    global _conn
    if _conn is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL;")
    return _conn

def is_already_processed(post_id: str) -> bool:
    """Check if a post or comment has already been processed."""
    conn = _get_connection()
    try:
        result = conn.execute("SELECT 1 FROM history WHERE id = ?", (post_id,)).fetchone()
        return result is not None
    except sqlite3.Error as e:
        print(f"SQLite error during is_already_processed: {e}")
        return False

def get_top_posts_for_today(limit=10) -> list:
    today = datetime.utcnow().date().isoformat()
    conn = _get_connection()
    rows = conn.execute("""
        SELECT * FROM posts
        WHERE processed_at >= ?
        ORDER BY roi_weight DESC, relevance_score DESC
        LIMIT ?
    """, (today, limit)).fetchall()
    return [dict(row) for row in rows]

def get_all_posts_by_tag(tag: str) -> list:
    conn = _get_connection()
    rows = conn.execute("""
        SELECT * FROM posts
        WHERE tags LIKE ?
        ORDER BY processed_at DESC
    """, (f"%{tag}%",)).fetchall()
    return [dict(row) for row in rows]
