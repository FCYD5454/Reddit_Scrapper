"""Provider routing layer for batch API operations.

Delegates batch operations to the correct backend based on config["ai"]["provider"]:
  openai     → gpt/batch_api.py      (OpenAI native batch API)
  anthropic  → gpt/anthropic_batch.py (Anthropic Message Batches)
  gemini     → gpt/gemini_provider.py  (concurrent generateContent via ProviderBase)
  deepseek   → gpt/deepseek_provider.py (concurrent /chat/completions via ProviderBase)
"""

import json
import os
import re
from config.config_loader import get_config

_config = get_config()

# Providers that use the ProviderBase adapter pattern instead of JSONL files
_ADAPTER_PROVIDERS = {"gemini", "deepseek"}


class MockRequestCounts:
    """Mock the OpenAI Batch request_counts object."""
    def __init__(self, completed: int = 1, total: int = 1):
        self.completed = completed
        self.total = total


class MockBatch:
    """Mock the OpenAI Batch object for stateless/simulated adapters."""
    def __init__(self, batch_id: str, status: str, total_count: int = 1):
        self.id = batch_id
        self.status = status
        self.request_counts = MockRequestCounts(completed=total_count, total=total_count)
        self.output_file_id = f"file_mock_{batch_id}"


def _provider():
    return _config["ai"]["provider"]


def _is_adapter_provider():
    return _provider() in _ADAPTER_PROVIDERS


def _get_adapter_instance():
    """Return a fresh ProviderBase instance for the current adapter provider."""
    from gpt.batch_provider_adapter import get_provider_instance
    return get_provider_instance()


# ---------------------------------------------------------------------------
# Adapter helpers
# ---------------------------------------------------------------------------

def _adapter_submit_batch_job(file_path: str) -> str:
    """Read an Anthropic-format JSONL file and submit via ProviderBase.submit_batch."""
    payload = []
    with open(file_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            req = json.loads(line)
            params = req.get("params", {})

            # Reconstruct full messages list (Anthropic format separates system)
            messages = []
            if "system" in params:
                messages.append({"role": "system", "content": params["system"]})
            messages.extend(params.get("messages", []))

            payload.append({
                "id": req["custom_id"],
                "messages": messages,
                "meta": {},
            })

    instance = _get_adapter_instance()
    return instance.submit_batch(payload)


def _adapter_download_results(batch_id: str, save_path: str) -> None:
    """Fetch results from ProviderBase and write as normalised JSONL."""
    instance = _get_adapter_instance()
    results = instance.fetch_batch_result(batch_id)
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    count = 0
    with open(save_path, "w", encoding="utf-8") as fh:
        for item in results:
            has_output = bool(item.get("output"))
            entry = {
                "custom_id": item["id"],
                "content": item.get("output", ""),
                "result_type": "succeeded" if has_output else "error",
            }
            if "error" in item:
                entry["error_message"] = item["error"]
            fh.write(json.dumps(entry) + "\n")
            count += 1

    try:
        from utils.logger import setup_logger
        log = setup_logger()
    except Exception:
        import logging
        log = logging.getLogger(__name__)
    log.info(f"Saved {count} {_provider()} results to {save_path}")


# ---------------------------------------------------------------------------
# Public routing functions
# ---------------------------------------------------------------------------

def generate_batch_payload(requests, model):
    """Create a JSONL payload file (or equivalent) for the active provider."""
    if _provider() == "anthropic" or _is_adapter_provider():
        # Adapter providers reuse Anthropic's JSONL format since it supports
        # system/user message separation correctly.
        from gpt.anthropic_batch import generate_batch_payload as fn
    else:
        from gpt.batch_api import generate_batch_payload as fn
    return fn(requests, model)


def submit_batch_job(file_path, estimated_tokens=0):
    if _provider() == "anthropic":
        from gpt.anthropic_batch import submit_batch_job as fn
        return fn(file_path, estimated_tokens=estimated_tokens)
    if _is_adapter_provider():
        return _adapter_submit_batch_job(file_path)
    from gpt.batch_api import submit_batch_job as fn
    return fn(file_path, estimated_tokens=estimated_tokens)


def poll_batch_status(batch_id, timeout_seconds=10800):
    if _provider() == "anthropic":
        from gpt.anthropic_batch import poll_batch_status as fn
        return fn(batch_id, timeout_seconds=timeout_seconds)
    if _is_adapter_provider():
        instance = _get_adapter_instance()
        result = instance.poll_batch(batch_id, timeout_seconds=timeout_seconds)
        # Return a normalised dictionary matching OpenAI's return structure
        mock_batch = MockBatch(batch_id, result["status"])
        return {"status": result["status"], "batch": mock_batch}
    from gpt.batch_api import poll_batch_status as fn
    return fn(batch_id, timeout_seconds=timeout_seconds)


def download_batch_results(batch_id, save_path):
    if _provider() == "anthropic":
        from gpt.anthropic_batch import download_batch_results as fn
        return fn(batch_id, save_path)
    if _is_adapter_provider():
        return _adapter_download_results(batch_id, save_path)
    from gpt.batch_api import download_batch_results as fn
    return fn(batch_id, save_path)


def download_batch_results_if_available(batch_id, save_path):
    if _provider() == "anthropic":
        from gpt.anthropic_batch import download_batch_results_if_available as fn
        return fn(batch_id, save_path)
    if _is_adapter_provider():
        try:
            _adapter_download_results(batch_id, save_path)
            return os.path.exists(save_path) and os.path.getsize(save_path) > 0
        except Exception:
            return False
    from gpt.batch_api import download_batch_results_if_available as fn
    return fn(batch_id, save_path)


def get_processed_custom_ids(result_path):
    if _provider() == "anthropic" or _is_adapter_provider():
        from gpt.anthropic_batch import get_processed_custom_ids as fn
    else:
        from gpt.batch_api import get_processed_custom_ids as fn
    return fn(result_path)


def get_active_enqueued_tokens():
    if _provider() == "anthropic":
        from gpt.anthropic_batch import get_active_enqueued_tokens as fn
        return fn()
    if _is_adapter_provider():
        # Adapter providers process requests synchronously; no server-side queue.
        return 0
    from gpt.batch_api import get_active_enqueued_tokens as fn
    return fn()


def probe_enqueued_capacity(model, max_wait=7200, poll_interval=300):
    if _provider() == "anthropic":
        from gpt.anthropic_batch import probe_enqueued_capacity as fn
        return fn(model, max_wait=max_wait, poll_interval=poll_interval)
    if _is_adapter_provider():
        # No ghost-token issue — capacity always available for synchronous providers.
        return True
    from gpt.batch_api import probe_enqueued_capacity as fn
    return fn(model, max_wait=max_wait, poll_interval=poll_interval)


def add_estimated_batch_cost(requests, model):
    if _provider() == "anthropic":
        from gpt.anthropic_batch import add_estimated_batch_cost as fn
        return fn(requests, model)
    if _is_adapter_provider():
        # Basic cost estimation for Gemini / DeepSeek
        _adapter_add_estimated_cost(requests, model)
        return
    from gpt.batch_api import add_estimated_batch_cost as fn
    return fn(requests, model)


def _adapter_add_estimated_cost(requests, model: str) -> None:
    """Rough cost estimate for Gemini/DeepSeek (no official batch discount)."""
    # Approximate pricing per 1M tokens in USD
    pricing = {
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
        "deepseek-chat": {"input": 0.07, "output": 1.10},
    }
    model_pricing = pricing.get(model, {"input": 0.50, "output": 1.50})
    input_tokens = sum(r.get("meta", {}).get("estimated_tokens", 300) for r in requests)
    output_tokens = len(requests) * 300
    cost = (
        (input_tokens / 1_000_000) * model_pricing["input"]
        + (output_tokens / 1_000_000) * model_pricing["output"]
    )
    try:
        from scheduler.cost_tracker import add_cost
        from utils.logger import setup_logger
        log = setup_logger()
        log.info(f"Estimated cost for {_provider()} batch: ${cost:.4f}")
        add_cost(cost)
    except Exception:
        pass


def clean_storage():
    """Clean provider's remote file storage before starting a run.

    For OpenAI, deletes old batch input/output files that accumulate and
    can block new submissions. For Anthropic/Gemini/DeepSeek, this is a no-op.
    """
    if _provider() == "openai":
        from gpt.batch_api import clean_storage as fn
        fn()


def retrieve_batch(batch_id):
    """Retrieve a batch object for status checks."""
    if _provider() == "anthropic":
        from gpt.anthropic_batch import retrieve_batch as fn
        return fn(batch_id)
    if _is_adapter_provider():
        instance = _get_adapter_instance()
        result = instance.poll_batch(batch_id)
        return MockBatch(batch_id, result["status"])
    import openai
    return openai.batches.retrieve(batch_id)


def _extract_json_from_text(text: str) -> str:
    """Extract JSON from text that may be wrapped in markdown code fences.

    Anthropic often returns ```json ... ``` followed by reasoning text.
    This extracts just the JSON block.
    """
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"[\{\[].*[\}\]]", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def extract_content_from_result(result_line: dict) -> tuple[str, str]:
    """Extract (custom_id, content_text) from a result line regardless of provider.

    OpenAI format:  {"custom_id": "...", "response": {"body": {"choices": [{"message": {"content": "..."}}]}}}
    Normalised format (Anthropic / Gemini / DeepSeek): {"custom_id": "...", "content": "..."}

    For non-OpenAI providers the content may be wrapped in markdown code fences;
    this function strips them so the caller always receives raw JSON text.
    """
    custom_id = result_line["custom_id"]

    if _provider() in ("anthropic", "gemini", "deepseek"):
        content = result_line.get("content", "")
        content = _extract_json_from_text(content)
    else:
        # OpenAI nested format — content is already pure JSON
        content = result_line["response"]["body"]["choices"][0]["message"]["content"]

    return custom_id, content
