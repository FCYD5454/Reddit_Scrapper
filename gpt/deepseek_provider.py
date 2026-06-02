"""
DeepSeek provider adapter — OpenAI-compatible Chat Completions API.

DeepSeek's API is OpenAI-compatible but does not expose a native async batch
endpoint. This adapter dispatches individual /chat/completions requests
concurrently via ThreadPoolExecutor and persists results to disk so that
poll_batch / fetch_batch_result can operate statelessly.

Authentication:
    DEEPSEEK_API_KEY (env var) or config["api_key"]
    Passed as "Authorization: Bearer {key}" header.

Default model:
    DEEPSEEK_MODEL env var → config["model_filter"] → "deepseek-chat"

API reference: https://api-docs.deepseek.com
"""

from typing import List, Dict, Any, Optional
import os
import json
import time
import uuid
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from .provider_base import ProviderBase

try:
    from utils.logger import setup_logger
    log = setup_logger()
except Exception:
    import logging
    log = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 60
MAX_WORKERS = 5
MAX_RETRIES = 3
RETRY_DELAY = 2.0
DEFAULT_RESULTS_DIR = "data/batch_responses"


class DeepSeekProvider(ProviderBase):
    """
    DeepSeek provider using the OpenAI-compatible Chat Completions API.

    Since DeepSeek does not expose an async batch endpoint, all items in
    ``submit_batch`` are dispatched concurrently with a ThreadPoolExecutor.
    Results are written to ``{results_dir}/{batch_id}.json`` so that
    ``poll_batch`` and ``fetch_batch_result`` can operate statelessly.
    """

    def __init__(self, config: Dict[str, Any] = None):
        cfg = config or {}
        self.api_key: Optional[str] = cfg.get("api_key") or os.getenv("DEEPSEEK_API_KEY")
        self.base_url: str = (
            cfg.get("base_url")
            or cfg.get("endpoint")
            or os.getenv("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL)
        ).rstrip("/")
        self.model: str = (
            cfg.get("model_filter")
            or cfg.get("model")
            or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
        )
        self.results_dir: str = cfg.get("results_dir", DEFAULT_RESULTS_DIR)
        self._mock_mode: bool = not bool(self.api_key)
        if self._mock_mode:
            log.warning("DeepSeekProvider: no DEEPSEEK_API_KEY found — running in mock mode")

        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_messages(self, item: Dict[str, Any]) -> List[Dict[str, str]]:
        """Reconstruct the full messages list, hoisting a top-level 'system' key if present."""
        messages: List[Dict] = []
        if "system" in item:
            messages.append({"role": "system", "content": item["system"]})
        messages.extend(item.get("messages", []))
        return messages

    def _single_request(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one /chat/completions call. Returns a normalised result dict."""
        item_id: str = item.get("id") or str(uuid.uuid4())
        messages = self._build_messages(item)
        model: str = item.get("model") or self.model
        url = f"{self.base_url}/chat/completions"

        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": 4096,
        }

        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.post(url, json=body, timeout=DEFAULT_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()

                choices = data.get("choices", [])
                if not choices:
                    raise ValueError(
                        f"DeepSeek returned no choices for item {item_id}"
                    )

                text: str = choices[0]["message"]["content"]
                usage = data.get("usage", {})
                return {
                    "id": item_id,
                    "output": text,
                    "usage": {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                }

            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else 0
                if status_code in (429, 503) and attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (2 ** attempt)
                    log.warning(
                        f"DeepSeek rate-limit on item {item_id} "
                        f"(HTTP {status_code}), retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    last_exc = exc
                else:
                    raise
            except Exception as exc:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    last_exc = exc
                else:
                    raise

        raise RuntimeError(
            f"DeepSeek request failed for item {item_id} after {MAX_RETRIES} retries: {last_exc}"
        )

    def _results_path(self, batch_id: str) -> str:
        return os.path.join(self.results_dir, f"{batch_id}.json")

    def _save_results(self, batch_id: str, results: List[Dict]) -> None:
        os.makedirs(self.results_dir, exist_ok=True)
        with open(self._results_path(batch_id), "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=None)

    # ------------------------------------------------------------------
    # ProviderBase interface
    # ------------------------------------------------------------------

    def submit_batch(self, payload: List[Dict[str, Any]]) -> str:
        """Dispatch all items concurrently and persist results. Returns synthetic batch_id."""
        if self._mock_mode:
            batch_id = f"deepseek_mock_{int(time.time() * 1000)}"
            mock_results = [
                {
                    "id": item.get("id", f"item_{i}"),
                    "output": (
                        "[mock] "
                        + (item.get("messages") or [{}])[-1].get("content", "")[:80]
                    ),
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                }
                for i, item in enumerate(payload)
            ]
            self._save_results(batch_id, mock_results)
            return batch_id

        batch_id = f"deepseek_{uuid.uuid4().hex}"
        if not payload:
            self._save_results(batch_id, [])
            return batch_id

        workers = min(MAX_WORKERS, len(payload))
        log.info(
            f"DeepSeek: submitting {len(payload)} requests "
            f"(batch={batch_id}, workers={workers})"
        )

        results: List[Dict] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_item = {
                pool.submit(self._single_request, item): item for item in payload
            }
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    item_id = item.get("id", "unknown")
                    log.error(f"DeepSeek item {item_id} failed: {exc}")
                    results.append({
                        "id": item_id,
                        "output": "",
                        "error": str(exc),
                        "usage": {},
                    })

        self._save_results(batch_id, results)
        log.info(f"DeepSeek: batch {batch_id} done ({len(results)} results)")
        return batch_id

    def poll_batch(self, batch_id: str, timeout_seconds: int = 10800) -> Dict[str, Any]:
        """Processing is synchronous — if the results file exists the batch is complete."""
        if os.path.exists(self._results_path(batch_id)):
            return {"status": "completed", "meta": {"batch_id": batch_id}}
        return {"status": "not_found", "meta": {}}

    def cancel_batch(self, batch_id: str) -> bool:
        """No server-side async job to cancel — processing is already finished."""
        log.info(f"DeepSeek: cancel_batch {batch_id} is a no-op (synchronous execution)")
        return True

    def fetch_batch_result(self, batch_id: str) -> List[Dict[str, Any]]:
        """Return the persisted results for a completed batch."""
        path = self._results_path(batch_id)
        if not os.path.exists(path):
            log.warning(f"DeepSeek: results file not found for batch {batch_id}")
            return []
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
