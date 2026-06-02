from typing import List, Dict, Any

class ProviderBase:
    \"\"\"Provider adapter interface — 所有 provider (OpenAI/Gemini/DeepSeek) 必須實作這些方法。\"\"\"

    def submit_batch(self, payload: List[Dict[str, Any]]) -> str:
        \"\"\"Submit a batch payload. Return provider-specific batch_id (string).\"\"\"
        raise NotImplementedError

    def poll_batch(self, batch_id: str, timeout_seconds: int = 10800) -> Dict[str, Any]:
        \"\"\"Poll until batch completes or times out. Return dict with status and metadata.\"\"\"
        raise NotImplementedError

    def cancel_batch(self, batch_id: str) -> bool:
        \"\"\"Cancel a running batch. Return True on success.\"\"\"
        raise NotImplementedError

    def fetch_batch_result(self, batch_id: str) -> List[Dict[str, Any]]:
        \"\"\"Fetch normalized item-level results for a completed batch.
        Must return a list of dicts with at least: {'id': ..., 'output': ..., 'usage': {...}}.\"\"\"
        raise NotImplementedError

