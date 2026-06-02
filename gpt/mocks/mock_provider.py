from typing import List, Dict, Any
import time
from .provider_base import ProviderBase

class MockProvider(ProviderBase):
    """A simple mock provider for local testing. Returns synthetic ids and echoes input."""
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._batches = {}

    def submit_batch(self, payload: List[Dict[str, Any]]) -> str:
        batch_id = f"mockbatch_{int(time.time()*1000)}"
        # store payload and create synthetic pending status
        self._batches[batch_id] = {"status": "pending", "items": payload}
        # simulate asynchronous processing in background (not actually threaded here)
        # consumer tests can call poll_batch then fetch_batch_result
        return batch_id

    def poll_batch(self, batch_id: str, timeout_seconds: int = 30):
        # For mock, we simulate immediate completion
        if batch_id not in self._batches:
            return {"status": "not_found", "meta": {}}
        self._batches[batch_id]["status"] = "completed"
        return {"status": "completed", "meta": {"items": len(self._batches[batch_id]["items"]) }}

    def cancel_batch(self, batch_id: str) -> bool:
        if batch_id in self._batches:
            self._batches[batch_id]["status"] = "cancelled"
            return True
        return False

    def fetch_batch_result(self, batch_id: str) -> List[Dict[str, Any]]:
        b = self._batches.get(batch_id)
        if not b:
            return []
        results = []
        for i, item in enumerate(b.get("items", [])):
            results.append({
                "id": item.get("id") or f"item_{i}",
                "output": item.get("input", "") + " - mocked response",
                "usage": {"tokens": 1}
            })
        return results

