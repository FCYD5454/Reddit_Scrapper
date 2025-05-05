# db/writer.py

import sqlite3
from config.config_loader import get_config
from datetime import datetime

config = get_config()
DB_PATH = config["database"]["path"]

def insert_post(post: dict, community_type: str = "primary"):
    """Insert a new Reddit post into the posts table."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    INSERT OR IGNORE INTO posts (
        id, url, title, body, subreddit, created_utc, last_active,
        processed_at, community_type
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        post["id"],
        post["url"],
        post["title"],
        post.get("body", ""),
        post["subreddit"],
        post["created_utc"],
        post["created_utc"],  # initialize last_active to created_utc
        datetime.utcnow().isoformat(),
        community_type
    ))

    c.execute("""
    INSERT OR IGNORE INTO history (id, processed_at)
    VALUES (?, ?)
    """, (
        post["id"],
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()

def update_post_insight(post_id: str, insight: dict):
    """Update an existing post with scoring/insight results."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
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
    conn.close()
