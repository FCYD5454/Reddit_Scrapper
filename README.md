````markdown
# Reddit Scrapper for Cronlytic Marketing

This project scrapes Reddit posts and comments to find high-quality, relevant leads and pain points for promoting **Cronlytic** — a SaaS for scheduling and monitoring HTTP jobs (hosted cron service).

---

## 🔧 Features

- Scrapes Reddit posts aged 5–90 days (mature + still active)
- 90% from configured subreddits, 10% exploratory via GPT-4
- Filters posts using **GPT-4.1 Mini**
- Extracts insights using **GPT-4.1**
- Uses **OpenAI Batch API** to reduce token cost
- Keeps daily top 10 ranked leads in SQLite DB
- Retains posts for 90 days, then auto-deletes
- Adheres to Reddit rate limits
- Enforces OpenAI budget limit ($100/month)
- Fully configurable via `config/config.yaml`

---

## 🚀 Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
````

### 2. Configure credentials

Create a `.env` file:

```env
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=your_bot_name

OPENAI_API_KEY=your_openai_key
```

### 3. Set tracking subreddits and weights in `config/config.yaml`

### 4. Run the daily pipeline

```bash
python scheduler/runner.py
```

Or start the scheduler:

```bash
python scheduler/daily_scheduler.py
```

---

## 📂 Output

Results are stored in:

* `data/db.sqlite` — all scored posts with tags and ROI
* `data/batch_responses/` — raw batch results (debug)

You can later build a UI or export CSV from the DB.

---

## 🛡 Safety

* Respects Reddit rate limits (60 req/min)
* Keeps cost under OpenAI's monthly cap
* Avoids reposting the same item twice

```

---

Let me know when you're ready for the **last file**:  
➡ `main.py` — a convenience entrypoint to trigger everything.
```
