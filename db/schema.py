# db/schema.py

import sqlite3
from config.config_loader import get_config

config = get_config()
DB_PATH = config["database"]["path"]

def create_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY,
        url TEXT,
        title TEXT,
        body TEXT,
        subreddit TEXT,
        created_utc REAL,
        last_active REAL,
        processed_at TEXT,
        relevance_score REAL,
        emotion_score REAL,
        pain_score REAL,
        lead_type TEXT,
        tags TEXT,
        roi_weight INTEGER,
        community_type TEXT  -- 'primary' or 'exploratory'
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id TEXT PRIMARY KEY,
        processed_at TEXT
    );
    """)

    conn.commit()
    conn.close()
