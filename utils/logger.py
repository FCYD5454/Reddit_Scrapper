# utils/logger.py

import logging
import os
import sys
from datetime import datetime
from config.config_loader import get_config

def setup_logger():
    """Configure and return a logger instance."""
    # Reconfigure stdout/stderr to use UTF-8 under Windows shell (avoids cp950 emoji errors)
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding='utf-8')
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

    config = get_config()
    log_level = getattr(logging, config.get("log_level", "INFO"))

    # Ensure log directory exists
    os.makedirs("logs", exist_ok=True)

    # Create logger
    logger = logging.getLogger("cronlytic.com")
    logger.setLevel(log_level)

    # Clear existing handlers
    logger.handlers = []

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # Create file handler
    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(f"logs/cronlytic_{today}.log")
    file_handler.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
