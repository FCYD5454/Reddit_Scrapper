# Reddit Scrapper:

## Folder Structure

```bash
cronlytic_scraper/
├── config/
│   └── config.yaml                   # Main config file (subreddits, budget, weights, etc.)
│
├── data/
│   └── db.sqlite                     # SQLite DB file (auto-created)
│   └── batch_requests.jsonl         # OpenAI Batch API payloads
│   └── batch_responses/             # Responses saved after OpenAI returns
│
├── gpt/
│   ├── batch_api.py                 # Functions for sending/receiving batch jobs
│   ├── filters.py                   # GPT-4.1 Mini filtering logic
│   ├── insights.py                  # GPT-4.1 detailed extraction
│   └── prompts/                     # Prompt templates
│       ├── filter_prompt.txt
│       ├── insight_prompt.txt
│       └── community_discovery.txt
│
├── reddit/
│   ├── scraper.py                   # Fetches Reddit posts/comments via PRAW/Pushshift
│   ├── discovery.py                 # Generates exploratory subreddits using GPT-4
│   └── rate_limiter.py             # Ensures Reddit API rate limit compliance
│
├── db/
│   ├── schema.py                    # SQLite table creation
│   ├── writer.py                    # Insert/update to DB
│   ├── cleaner.py                   # Remove aged posts
│   └── reader.py                    # Query top posts, sort by day
│
├── scheduler/
│   ├── runner.py                    # Main job loop
│   ├── daily_scheduler.py           # APScheduler or cron job logic
│   └── cost_tracker.py              # Tracks OpenAI token usage & budget cap
│
├── utils/
│   ├── logger.py                    # Unified logging
│   └── helpers.py                   # Misc helpers (e.g., token estimate, UUIDs)
│
├── .env                             # API keys, secrets (loaded via dotenv)
├── requirements.txt                 # Python dependencies
├── README.md
└── main.py                          # Entrypoint (e.g., run daily pipeline)
```
