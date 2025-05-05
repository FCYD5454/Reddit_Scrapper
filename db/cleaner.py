# db/cleaner.py

import sqlite3
from datetime import datetime, timedelta
from config.config_loader import get_config

config = get_config()
DB_PATH = config["database"]["path"]
RETENTION_DAYS = config["database"]["retention_days"]

def clean_old_entries():
    """Remove posts and history entries older than retention_days."""
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    cutoff_str = cutoff.isoformat()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("DELETE FROM posts WHERE processed_at < ?", (cutoff_str,))
    c.execute("DELETE FROM history WHERE processed_at < ?", (cutoff_str,))

    conn.commit()
    conn.close()
    print(f"Old entries removed before {cutoff_str}")
