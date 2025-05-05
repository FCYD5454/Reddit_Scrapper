# check_results.py

import sqlite3
import argparse
import os
import sys
from tabulate import tabulate
from datetime import datetime, timedelta
from config.config_loader import get_config

config = get_config()
DB_PATH = config["database"]["path"]

def check_database_exists():
    """Check if the database file exists."""
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        print("Run the scraper first to create and populate the database.")
        sys.exit(1)

def get_top_posts(days=1, limit=10, order_by="roi_weight"):
    """Get top posts from the last N days."""
    check_database_exists()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

    valid_order_columns = ["roi_weight", "relevance_score", "emotion_score", "pain_score", "processed_at"]
    if order_by not in valid_order_columns:
        order_by = "roi_weight"

    c.execute(f"""
    SELECT id, subreddit, title, url,
           relevance_score, emotion_score, pain_score,
           lead_type, tags, roi_weight, community_type, processed_at
    FROM posts
    WHERE processed_at > ?
    ORDER BY {order_by} DESC, relevance_score DESC
    LIMIT ?
    """, (cutoff_date, limit))

    rows = c.fetchall()
    conn.close()

    return rows

def get_posts_by_tag(tag, limit=10):
    """Get posts with a specific tag."""
    check_database_exists()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
    SELECT id, subreddit, title, url,
           relevance_score, emotion_score, pain_score,
           lead_type, tags, roi_weight, community_type, processed_at
    FROM posts
    WHERE tags LIKE ?
    ORDER BY processed_at DESC, roi_weight DESC
    LIMIT ?
    """, (f"%{tag}%", limit))

    rows = c.fetchall()
    conn.close()

    return rows

def print_posts(posts):
    """Print posts in a nice table format."""
    if not posts:
        print("No posts found matching your criteria.")
        return

    table_data = []
    for post in posts:
        # Format the date
        processed_date = datetime.fromisoformat(post['processed_at']).strftime('%Y-%m-%d')

        # Format the scores
        scores = f"R:{post['relevance_score']:.1f} E:{post['emotion_score']:.1f} P:{post['pain_score']:.1f}"

        # Add the row
        table_data.append([
            post['roi_weight'],
            post['subreddit'],
            post['title'][:50] + ('...' if len(post['title']) > 50 else ''),
            post['lead_type'] if post['lead_type'] else 'Unknown',
            post['tags'],
            scores,
            processed_date
        ])

    headers = ["ROI", "Subreddit", "Title", "Lead Type", "Tags", "Scores", "Date"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print(f"\nTotal: {len(posts)} posts")

def get_stats():
    """Get general statistics about the database."""
    check_database_exists()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Total posts
    c.execute("SELECT COUNT(*) FROM posts")
    total_posts = c.fetchone()[0]

    # Posts by community type
    c.execute("SELECT community_type, COUNT(*) FROM posts GROUP BY community_type")
    community_counts = c.fetchall()

    # Posts by subreddit
    c.execute("SELECT subreddit, COUNT(*) FROM posts GROUP BY subreddit ORDER BY COUNT(*) DESC LIMIT 10")
    subreddit_counts = c.fetchall()

    # Posts by lead type
    c.execute("SELECT lead_type, COUNT(*) FROM posts WHERE lead_type IS NOT NULL GROUP BY lead_type ORDER BY COUNT(*) DESC")
    lead_type_counts = c.fetchall()

    # Recent processing dates
    c.execute("SELECT DISTINCT substr(processed_at, 1, 10) as day FROM posts ORDER BY day DESC LIMIT 7")
    processing_dates = c.fetchall()

    # Average scores
    c.execute("SELECT AVG(relevance_score), AVG(emotion_score), AVG(pain_score), AVG(roi_weight) FROM posts")
    avg_scores = c.fetchone()

    conn.close()

    print("\n=== Database Statistics ===\n")
    print(f"Total posts: {total_posts}")

    print("\nPosts by community type:")
    for community_type, count in community_counts:
        print(f"  {community_type}: {count}")

    print("\nTop subreddits:")
    for subreddit, count in subreddit_counts:
        print(f"  r/{subreddit}: {count}")

    print("\nLead types:")
    for lead_type, count in lead_type_counts:
        print(f"  {lead_type}: {count}")

    print("\nRecent processing dates:")
    for date in processing_dates:
        print(f"  {date[0]}")

    print("\nAverage scores:")
    print(f"  Relevance: {avg_scores[0]:.2f}")
    print(f"  Emotional: {avg_scores[1]:.2f}")
    print(f"  Pain Point: {avg_scores[2]:.2f}")
    print(f"  ROI Weight: {avg_scores[3]:.2f}")
    print("\n")

def main():
    parser = argparse.ArgumentParser(description="Check Reddit scraper results.")

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Top posts command
    top_parser = subparsers.add_parser('top', help='Show top posts')
    top_parser.add_argument('-d', '--days', type=int, default=7, help='Posts from the last N days')
    top_parser.add_argument('-n', '--limit', type=int, default=10, help='Number of posts to show')
    top_parser.add_argument('-o', '--order', choices=['roi_weight', 'relevance_score', 'emotion_score', 'pain_score', 'processed_at'],
                          default='roi_weight', help='Order posts by this field')

    # Tag command
    tag_parser = subparsers.add_parser('tag', help='Show posts with a specific tag')
    tag_parser.add_argument('tag', help='Tag to search for')
    tag_parser.add_argument('-n', '--limit', type=int, default=10, help='Number of posts to show')

    # Stats command
    subparsers.add_parser('stats', help='Show database statistics')

    args = parser.parse_args()

    if args.command == 'top':
        posts = get_top_posts(days=args.days, limit=args.limit, order_by=args.order)
        print(f"\n=== Top {args.limit} posts from the last {args.days} days (ordered by {args.order}) ===\n")
        print_posts(posts)

    elif args.command == 'tag':
        posts = get_posts_by_tag(args.tag, limit=args.limit)
        print(f"\n=== Posts with tag '{args.tag}' ===\n")
        print_posts(posts)

    elif args.command == 'stats':
        get_stats()

    else:
        parser.print_help()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)