from typing import List, Dict, Any
import os
import time
import requests

from .provider_base import ProviderBase

DEFAULT_TIMEOUT = 30
RETRY_DELAY = 1.0
MAX_RETRIES = 5

class DeepSeekProvider(ProviderBase):
    """
    Minimal DeepSeek provider adapter skeleton.
    Reads DEEPSEEK_API_KEY and DEEPSEEK_ENDPOINT from environment or config.
    Adjust endpoints and JSON fields to match DeepSeek API.
    """

    def __init__(self, config: Dict[str, Any] = None):
        cfg = config or {}
        self.api_key = cfg.get("api_key") or os.getenv("DEEPSEEK_API_KEY")
        self.endpoint = cfg.get("endpoint") or os.getenv("DEEPSEEK_ENDPOINT", "https://api.deepseek.example")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
            self._mock_mode = False
        else:
            self._mock_mode = True

    def submit_batch(self, payload: List[Dict[str, Any]]) -> str:
        if self._mock_mode:
            return f"deepseek_mock_{int(time.time()*1000)}"
        url = f"{self.endpoint}/v1/batches"
        body = {"inputs": payload}
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.post(url, json=body, timeout=DEFAULT_TIMEOUT)
                resp.raise_for_status()
                d = resp.json()
                return d.get("batch_id") or d.get("id")
            except requests.RequestException:
                time.sleep(RETRY_DELAY * (attempt + 1))
        raise RuntimeError("Failed to submit batch to DeepSeek after retries")

    def poll_batch(self, batch_id: str, timeout_seconds: int = 10800) -> Dict[str, Any]:
        if self._mock_mode:
            return {"status": "completed", "meta": {}}
        url = f"{self.endpoint}/v1/batches/{batch_id}"
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                resp = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                resp.raise_for_status()
                d = resp.json()
                status = d.get("status")
                if status in ("completed", "failed"):
                    return {"status": status, "meta": d}
            except requests.RequestException:
                pass
            time.sleep(2)
        return {"status": "timeout", "meta": {}}

    def cancel_batch(self, batch_id: str) -> bool:
        if self._mock_mode:
            return True
        url = f"{self.endpoint}/v1/batches/{batch_id}/cancel"
        try:
            resp = self.session.post(url, timeout=DEFAULT_TIMEOUT)
            return resp.status_code in (200, 202)
        except requests.RequestException:
            return False

    def fetch_batch_result(self, batch_id: str) -> List[Dict[str, Any]]:
        if self._mock_mode:
            return []
        url = f"{self.endpoint}/v1/batches/{batch_id}/results"
        try:
            resp = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
            d = resp.json()
            items = d.get("items") or d.get("results") or []
            normalized = []
            for it in items:
                normalized.append({
                    "id": it.get("id") or it.get("item_id"),
                    "output": it.get("output") or it.get("text") or str(it),
                    "usage": it.get("usage") or {"tokens": it.get("tokens", 0)}
                })
            return normalized
        except requests.RequestException:
            return []