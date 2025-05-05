# scheduler/daily_scheduler.py

from apscheduler.schedulers.blocking import BlockingScheduler
from scheduler.runner import run_daily_pipeline
import logging

def start_scheduler():
    scheduler = BlockingScheduler()

    # Run daily at 09:00 UTC (adjust as needed)
    scheduler.add_job(run_daily_pipeline, 'cron', hour=9, minute=0)
    
    logging.basicConfig()
    logging.getLogger('apscheduler').setLevel(logging.INFO)

    print("🕒 Daily scheduler started. Waiting for next trigger...")
    scheduler.start()

if __name__ == "__main__":
    start_scheduler()
