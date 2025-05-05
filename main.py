# main.py

from scheduler.runner import run_daily_pipeline
from utils.logger import setup_logger

if __name__ == "__main__":
    log = setup_logger()
    log.info("🚀 Starting Cronlytic Reddit scraping pipeline...")
    run_daily_pipeline()
    log.info("✅ Finished.")
