# scheduler/cost_tracker.py

import os
import json
from datetime import datetime
from config.config_loader import get_config

config = get_config()
BUDGET_FILE = "data/openai_cost.json"

def load_cost_data():
    if not os.path.exists(BUDGET_FILE):
        return {"month": current_month(), "total_cost": 0.0}
    with open(BUDGET_FILE, "r") as f:
        return json.load(f)

def save_cost_data(data):
    with open(BUDGET_FILE, "w") as f:
        json.dump(data, f, indent=2)

def current_month():
    return datetime.utcnow().strftime("%Y-%m")

def add_cost(amount_usd: float):
    data = load_cost_data()
    if data["month"] != current_month():
        data = {"month": current_month(), "total_cost": 0.0}
    data["total_cost"] += amount_usd
    save_cost_data(data)

def get_remaining_budget():
    data = load_cost_data()
    return max(0, config["openai"]["monthly_budget_usd"] - data["total_cost"])

def is_over_budget() -> bool:
    return get_remaining_budget() <= 0
