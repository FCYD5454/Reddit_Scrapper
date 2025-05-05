# gpt/batch_api.py

import json
import uuid
import time
import os
import openai

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
    
    return path

def submit_batch_job(file_path: str, endpoint: str = "/v1/chat/completions") -> str:
    """Submits a batch job to OpenAI."""
    with open(file_path, "rb") as f:
        batch = openai.Batches.create(
            input_file=f,
            endpoint=endpoint,
            completion_window="24h",
        )
    print(f"Submitted batch job: {batch.id}")
    return batch.id

def poll_batch_status(batch_id: str):
    """Polls status until job is complete or failed."""
    while True:
        batch = openai.Batches.retrieve(batch_id)
        print(f"Batch {batch_id} status: {batch.status}")
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
    print(f"Saved results to {save_path}")
