# Cronlytic Reddit Scraper

A Python application that scrapes Reddit for potential marketing leads, analyzes them with GPT models, and identifies high-value opportunities for a cron job scheduling SaaS.

## 📋 Overview

This tool uses a combination of Reddit's API and OpenAI's GPT models to:

1. Scrape relevant subreddits for discussions about scheduling, automation, and related topics
2. Identify posts that express pain points solvable by a cron job scheduling SaaS
3. Score and analyze these posts to find high-quality marketing leads
4. Store results in a local SQLite database for review

The application maintains a balance between focused (90%) and exploratory (10%) subreddits, intelligently refreshing the exploratory list based on discoveries. This exploration process happens automatically as part of the main workflow.

## 🚀 Setup

### Prerequisites

- Python 3.8+
- Reddit API credentials ([create an app here](https://www.reddit.com/prefs/apps))
- OpenAI API key

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/cronlytic-reddit-scraper.git
   cd cronlytic-reddit-scraper
   ```

2. Create a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables by copying `.env.template` to `.env`:
   ```
   cp .env.template .env
   ```

5. Edit `.env` and add your API credentials:
   ```
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_client_secret
   REDDIT_USER_AGENT="script:cronlytic-reddit-scraper:v1.0 (by /u/yourusername)"
   OPENAI_API_KEY=your_openai_api_key
   ```

## 🔧 Configuration

Configure the application by editing `config/config.yaml`. Key settings include:

- **Target subreddits**: Primary subreddits and exploratory subreddit settings
- **Post age range**: Only analyze posts 5-90 days old
- **API rate limits**: Prevent hitting Reddit API limits
- **OpenAI models**: Which models to use for filtering and deep analysis
- **Monthly budget**: Cap total API spending
- **Scoring weights**: How to weight different factors when scoring posts

## 🏃‍♀️ Running

### One-time Run

To run the pipeline once:

```
python main.py
```

This will:
1. Scrape posts from configured primary subreddits
2. Automatically discover and scrape from exploratory subreddits
3. Analyze all posts with GPT models
4. Store results in the database

### Scheduled Operation

To run the pipeline daily at the configured time:

```
python scheduler/daily_scheduler.py
```

## 📊 Results

Results are stored in a SQLite database at `data/db.sqlite`. You can query it using:

```sql
-- Today's top leads
SELECT * FROM posts
WHERE processed_at >= DATE('now')
ORDER BY roi_weight DESC, relevance_score DESC
LIMIT 10;

-- Posts with specific tag
SELECT * FROM posts
WHERE tags LIKE '%serverless%'
ORDER BY processed_at DESC;
```

You can also use the included results viewer:

```
python check_results.py stats       # Show database statistics
python check_results.py top -n 5    # Show top 5 posts
python check_results.py tag serverless  # Show posts with the 'serverless' tag
```

## 📂 Project Structure

```
cronlytic-reddit-scraper/
├── config/                  # Configuration files
├── data/                    # Database and data storage
├── db/                      # Database interaction
├── gpt/                     # OpenAI GPT integration
│   └── prompts/             # Prompt templates
├── logs/                    # Application logs
├── reddit/                  # Reddit API interaction
├── scheduler/               # Scheduling components
├── utils/                   # Utility functions
├── .env                     # Environment variables (create from .env.template)
├── .env.template            # Template for .env file
├── check_results.py         # Tool for viewing analysis results
├── main.py                  # Main application entry point
└── requirements.txt         # Python dependencies
```

## 🔒 Cost Controls

The application includes several safeguards to control API costs:

- Monthly budget cap (configurable in `config.yaml`)
- Efficient batch processing using OpenAI's Batch API
- Pre-filtering with less expensive models before using more powerful models
- Cost tracking and logging

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgements

- [PRAW (Python Reddit API Wrapper)](https://praw.readthedocs.io/)
- [OpenAI API](https://platform.openai.com/docs/api-reference)
- [APScheduler](https://apscheduler.readthedocs.io/)

## Core Functionality (Implemented):
| Feature                                   | Status | Notes                                                 |
| ----------------------------------------- | ------ | ----------------------------------------------------- |
| **Reddit Scraping (Posts & Comments)**    | ✅ Done | Age-filtered, deduplicated, tracked via history table |
| **Primary & Exploratory Subreddit Logic** | ✅ Done | With refreshable `exploratory_subreddits.json`        |
| **GPT-4.1 Mini Filtering**                | ✅ Done | Via batch API, scoring + threshold-based selection    |
| **GPT-4.1 Insight Extraction**            | ✅ Done | With batch API, structured JSON, ROI + tags           |
| **SQLite Local DB Storage**               | ✅ Done | Full schema, type handling (`post`/`comment`)         |
| **Rate Limiting**                         | ✅ Done | Real limiter applied to avoid Reddit bans             |
| **Budget Control**                        | ✅ Done | Tracks monthly cost, blocks over-budget batches       |
| **Daily Runner Pipeline**                 | ✅ Done | Logs step-by-step, fail-safe batch handling           |
| **Batch API Integration**                 | ✅ Done | With file-based payloads + polling + result fetch     |
| **Cached Summaries → GPT Discovery**      | ✅ Done | Based on post text, fallback if prompt fails          |
| **Comment scraping toggle**               | ✅ Done | Controlled via config key (`include_comments`)        |

## Missing Features
| Feature                                   | Status                     | Suggestion                                   |
| ----------------------------------------- | -------------------------- | -------------------------------------------- |
| **Retry on GPT Batch Failures**           | 🟡 Missing                 | Could retry `submit_batch_job()` once        |
| **Parallel subreddit fetching**           | 🟡 Manual (sequential)     | Consider async/threaded fetch in future      |
| **Tagged CSV Export / CLI**               | 🟡 Missing                 | Useful for non-technical review/debug        |
| **Multi-language / non-English handling** | 🟡 Not supported           | Detect & skip or flag for English-only use   |
| **Unit tests / mocks**                    | 🟡 Not present             | Add test coverage for scoring and DB logic   |
| **Dashboard/UI**                          | ❌ Out of scope (by design) | CLI / SQLite interface is sufficient for now |
