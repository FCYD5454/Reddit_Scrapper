# gpt/batch_api.py

import json
import uuid
import time
import os
import openai
from config.config_loader import get_config
from scheduler.cost_tracker import add_cost
from utils.logger import setup_logger

log = setup_logger()
config = get_config()

BATCH_FILE_PATH = "data/batch_requests.jsonl"
RESPONSE_DIR = "data/batch_responses"

def generate_batch_payload(requests: list[dict], model: str) -> str:
    """Create a JSONL file from prompts for OpenAI batch processing."""
    os.makedirs(RESPONSE_DIR, exist_ok=True)
    job_id = str(uuid.uuid4())
    path = f"{RESPONSE_DIR}/batch_{job_id}.jsonl"

    with open(path, "w", encoding="utf-8") as f:
        for prompt in requests:
            f.write(json.dumps({
                "custom_id": prompt.get("id", str(uuid.uuid4())),
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": prompt["messages"],
                    "temperature": 0,
                }
            }) + "\n")

    log.info(f"Batch payload generated at: {path} with {len(requests)} entries")
    return path

def submit_batch_job(file_path: str, endpoint: str = "/v1/chat/completions") -> str:
    """Submits a batch job to OpenAI."""
    with open(file_path, "rb") as f:
        batch = openai.Batches.create(
            input_file=f,
            endpoint=endpoint,
            completion_window="24h",
        )
    log.info(f"Submitted batch job: {batch.id}")
    return batch.id

def poll_batch_status(batch_id: str):
    """Polls status until job is complete or failed."""
    while True:
        batch = openai.Batches.retrieve(batch_id)
        log.info(f"Batch {batch_id} status: {batch.status}")
        if batch.status in {"completed", "failed", "expired"}:
            return batch
        time.sleep(15)

def download_batch_results(batch_id: str, save_path: str):
    """Downloads and stores the results of a completed batch job."""
    batch = openai.Batches.retrieve(batch_id)
    if batch.status != "completed":
        raise RuntimeError(f"Batch {batch_id} not completed.")

    output_url = batch.output_file["url"]
    import requests
    response = requests.get(output_url)
    with open(save_path, "wb") as f:
        f.write(response.content)
    log.info(f"Saved results to {save_path}")

def add_estimated_batch_cost(requests: list[dict], model: str):
    """Estimate and record the cost of the batch job."""
    if model == "gpt-4.1-mini":
        cost_per_1k = 0.40
    elif model == "gpt-4.1":
        cost_per_1k = 10.0  # Combined input + output est.
    else:
        cost_per_1k = 1.0

    total_tokens = 0
    for req in requests:
        meta = req.get("meta", {})
        total_tokens += meta.get("estimated_tokens", 300) + 300  # Add output est.

    estimated_cost = (total_tokens / 1000) * cost_per_1k
    log.info(f"Estimated cost for batch: ${estimated_cost:.2f}")
    add_cost(estimated_cost)
