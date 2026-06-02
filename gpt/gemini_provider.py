from typing import List, Dict, Any
import os
import time
import requests

from .provider_base import ProviderBase

DEFAULT_TIMEOUT = 30
RETRY_DELAY = 1.0
MAX_RETRIES = 5

class GeminiProvider(ProviderBase):
    """
    Minimal Gemini provider adapter skeleton.
    Reads GEMINI_API_KEY and GEMINI_ENDPOINT from environment or config.
    Methods implemented: submit_batch, poll_batch, cancel_batch, fetch_batch_result.
    This is a template — adapt endpoints/JSON fields to the real Gemini API.
    """

    def __init__(self, config: Dict[str, Any] = None):
        cfg = config or {}
        self.api_key = cfg.get("api_key") or os.getenv("GEMINI_API_KEY")
        self.endpoint = cfg.get("endpoint") or os.getenv("GEMINI_ENDPOINT", "https://api.gemini.example")
        if not self.api_key:
            # allow mock/testing flows but warn caller
            # You may choose to raise instead.
            self._mock_mode = True
        else:
            self._mock_mode = False
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})

    def submit_batch(self, payload: List[Dict[str, Any]]) -> str:
        if self._mock_mode:
            # synthetic id for local/dev testing
            return f"gemini_mock_{int(time.time()*1000)}"
        url = f"{self.endpoint}/v1/batches"
        body = {"items": payload}
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.post(url, json=body, timeout=DEFAULT_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                # Replace with actual response field
                return data.get("batch_id") or data.get("id") or data.get("batchId")
            except requests.RequestException:
                time.sleep(RETRY_DELAY * (attempt + 1))
        raise RuntimeError("Failed to submit batch to Gemini after retries")

    def poll_batch(self, batch_id: str, timeout_seconds: int = 10800) -> Dict[str, Any]:
        if self._mock_mode:
            return {"status": "completed", "meta": {"items": 0}}
        url = f"{self.endpoint}/v1/batches/{batch_id}/status"
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                resp = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                # Normalise expected keys: status can be 'pending'|'running'|'completed'|'failed'
                status = data.get("status")
                if status in ("completed", "failed"):
                    return {"status": status, "meta": data}
            except requests.RequestException:
                # continue to retry until timeout
                pass
            time.sleep(2)
        return {"status": "timeout", "meta": {}}

    def cancel_batch(self, batch_id: str) -> bool:
        if self._mock_mode:
            return True
        url = f"{self.endpoint}/v1/batches/{batch_id}"
        try:
            resp = self.session.delete(url, timeout=DEFAULT_TIMEOUT)
            return resp.status_code in (200, 202, 204)
        except requests.RequestException:
            return False

    def fetch_batch_result(self, batch_id: str) -> List[Dict[str, Any]]:
        """
        Fetch item-level results and normalize to:
        [{'id': ..., 'output': ..., 'usage': {...}}, ...]
        """
        if self._mock_mode:
            # Return synthetic normalized items for tests
            return [{"id": f"item_{i}", "output": item.get("input", "") + " (mocked)", "usage": {"tokens": 0}} 
                    for i, item in enumerate([])]
        url = f"{self.endpoint}/v1/batches/{batch_id}/results"
        try:
            resp = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            # Transform provider-specific format to normalized list
            items = data.get("items") or data.get("results") or []
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