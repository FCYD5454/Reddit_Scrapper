"""
Gemini provider adapter — Google Generative AI REST API.

Google's generativelanguage.googleapis.com does NOT have a native async batch
endpoint. This adapter simulates batch processing by dispatching individual
generateContent requests concurrently via ThreadPoolExecutor, then persists
results to disk so poll_batch / fetch_batch_result work without shared state.

Authentication:
    GEMINI_API_KEY (env var) or config["api_key"]
    Passed as "x-goog-api-key" header (recommended).

Default model:
    GEMINI_MODEL env var → config["model_filter"] → "gemini-2.0-flash"

API reference: https://ai.google.dev/api/generate-content
"""

from typing import List, Dict, Any, Optional, Tuple
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

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_TIMEOUT = 60
MAX_WORKERS = 10
MAX_RETRIES = 3
RETRY_DELAY = 2.0
DEFAULT_RESULTS_DIR = "data/batch_responses"


class GeminiProvider(ProviderBase):
    """
    Gemini provider using the Google Generative AI REST API.

    Since the Google AI Studio API has no async batch endpoint, all items in
    ``submit_batch`` are dispatched concurrently with a ThreadPoolExecutor.
    Results are written to ``{results_dir}/{batch_id}.json`` so that
    ``poll_batch`` and ``fetch_batch_result`` can operate statelessly.
    """

    def __init__(self, config: Dict[str, Any] = None):
        cfg = config or {}
        self.api_key: Optional[str] = cfg.get("api_key") or os.getenv("GEMINI_API_KEY")
        self.base_url: str = (
            cfg.get("base_url")
            or os.getenv("GEMINI_BASE_URL", GEMINI_BASE_URL)
        ).rstrip("/")
        self.model: str = (
            cfg.get("model_filter")
            or cfg.get("model")
            or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        )
        self.results_dir: str = cfg.get("results_dir", DEFAULT_RESULTS_DIR)
        self._mock_mode: bool = not bool(self.api_key)
        if self._mock_mode:
            log.warning("GeminiProvider: no GEMINI_API_KEY found — running in mock mode")

        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _messages_to_gemini(
        self, messages: List[Dict[str, str]]
    ) -> Tuple[Optional[Dict], List[Dict]]:
        """Convert OpenAI-style messages to Gemini contents + optional systemInstruction.

        OpenAI roles  →  Gemini mapping
        ---------------------------------
        system        →  systemInstruction (separate top-level field)
        user          →  role: "user"
        assistant     →  role: "model"
        """
        system_parts: List[str] = []
        contents: List[Dict] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            else:
                gemini_role = "model" if role == "assistant" else "user"
                contents.append({"role": gemini_role, "parts": [{"text": content}]})

        system_instruction: Optional[Dict] = None
        if system_parts:
            system_instruction = {"parts": [{"text": "\n".join(system_parts)}]}

        # Gemini requires at least one content entry
        if not contents:
            contents = [{"role": "user", "parts": [{"text": ""}]}]

        return system_instruction, contents

    def _single_request(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one generateContent call. Returns a normalised result dict."""
        item_id: str = item.get("id") or str(uuid.uuid4())

        # Support both flat "messages" list and a separate "system" key
        all_messages: List[Dict] = []
        if "system" in item:
            all_messages.append({"role": "system", "content": item["system"]})
        all_messages.extend(item.get("messages", []))

        system_instruction, contents = self._messages_to_gemini(all_messages)
        model: str = item.get("model") or self.model
        url = f"{self.base_url}/models/{model}:generateContent"

        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 4096,
            },
        }
        if system_instruction:
            body["systemInstruction"] = system_instruction

        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.post(url, json=body, timeout=DEFAULT_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()

                candidates = data.get("candidates", [])
                if not candidates:
                    raise ValueError(
                        f"Gemini returned no candidates for item {item_id}. "
                        f"Prompt feedback: {data.get('promptFeedback')}"
                    )

                text: str = candidates[0]["content"]["parts"][0]["text"]
                usage_meta = data.get("usageMetadata", {})
                return {
                    "id": item_id,
                    "output": text,
                    "usage": {
                        "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                        "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                        "total_tokens": usage_meta.get("totalTokenCount", 0),
                    },
                }

            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else 0
                if status_code in (429, 503) and attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (2 ** attempt)
                    log.warning(
                        f"Gemini rate-limit on item {item_id} "
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
            f"Gemini request failed for item {item_id} after {MAX_RETRIES} retries: {last_exc}"
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
            batch_id = f"gemini_mock_{int(time.time() * 1000)}"
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

        batch_id = f"gemini_{uuid.uuid4().hex}"
        if not payload:
            self._save_results(batch_id, [])
            return batch_id

        workers = min(MAX_WORKERS, len(payload))
        log.info(
            f"Gemini: submitting {len(payload)} requests "
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
                    log.error(f"Gemini item {item_id} failed: {exc}")
                    results.append({
                        "id": item_id,
                        "output": "",
                        "error": str(exc),
                        "usage": {},
                    })

        self._save_results(batch_id, results)
        log.info(f"Gemini: batch {batch_id} done ({len(results)} results)")
        return batch_id

    def poll_batch(self, batch_id: str, timeout_seconds: int = 10800) -> Dict[str, Any]:
        """Processing is synchronous — if the results file exists the batch is complete."""
        if os.path.exists(self._results_path(batch_id)):
            return {"status": "completed", "meta": {"batch_id": batch_id}}
        return {"status": "not_found", "meta": {}}

    def cancel_batch(self, batch_id: str) -> bool:
        """No server-side async job to cancel — processing is already finished."""
        log.info(f"Gemini: cancel_batch {batch_id} is a no-op (synchronous execution)")
        return True

    def fetch_batch_result(self, batch_id: str) -> List[Dict[str, Any]]:
        """Return the persisted results for a completed batch."""
        path = self._results_path(batch_id)
        if not os.path.exists(path):
            log.warning(f"Gemini: results file not found for batch {batch_id}")
            return []
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
