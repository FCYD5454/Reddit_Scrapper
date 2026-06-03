import pytest
from gpt.mocks.mock_provider import MockProvider
from gpt.gemini_provider import GeminiProvider
from gpt.deepseek_provider import DeepSeekProvider


# ---------------------------------------------------------------------------
# MockProvider
# ---------------------------------------------------------------------------

def test_mock_provider_lifecycle():
    provider = MockProvider()
    payload = [{"id": "p1", "input": "Hello"}, {"id": "p2", "input": "World"}]
    batch_id = provider.submit_batch(payload)
    assert batch_id.startswith("mockbatch_")
    status = provider.poll_batch(batch_id)
    assert status["status"] == "completed"
    results = provider.fetch_batch_result(batch_id)
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["id"] == "p1"
    assert "mocked response" in results[0]["output"]


# ---------------------------------------------------------------------------
# GeminiProvider — mock mode (no API key)
# ---------------------------------------------------------------------------

@pytest.fixture()
def gemini_mock(tmp_path, monkeypatch):
    """GeminiProvider in mock mode: GEMINI_API_KEY is cleared for the test."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return GeminiProvider({"results_dir": str(tmp_path)})


def test_gemini_provider_mock_mode_no_key(gemini_mock):
    """GeminiProvider without an API key runs in mock mode."""
    assert gemini_mock._mock_mode is True


def test_gemini_provider_mock_lifecycle(gemini_mock):
    """Full submit → poll → fetch lifecycle in mock mode."""
    payload = [
        {"id": "g1", "messages": [{"role": "user", "content": "Hello Gemini"}]},
        {"id": "g2", "messages": [{"role": "user", "content": "Test message"}]},
    ]
    batch_id = gemini_mock.submit_batch(payload)
    assert batch_id.startswith("gemini_mock_")

    status = gemini_mock.poll_batch(batch_id)
    assert status["status"] == "completed"

    results = gemini_mock.fetch_batch_result(batch_id)
    assert isinstance(results, list)
    assert len(results) == 2

    ids = {r["id"] for r in results}
    assert ids == {"g1", "g2"}
    for r in results:
        assert "[mock]" in r["output"]
        assert "usage" in r


def test_gemini_provider_mock_cancel(gemini_mock):
    """cancel_batch is always a no-op and returns True in mock mode."""
    assert gemini_mock.cancel_batch("gemini_mock_12345") is True


def test_gemini_provider_fetch_missing_batch(gemini_mock):
    """fetch_batch_result returns an empty list for unknown batch ids."""
    assert gemini_mock.fetch_batch_result("nonexistent_batch") == []


def test_gemini_messages_to_gemini_conversion(gemini_mock):
    """_messages_to_gemini correctly separates system from conversation turns."""
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
        {"role": "user", "content": "How are you?"},
    ]
    system_instruction, contents = gemini_mock._messages_to_gemini(messages)

    assert system_instruction is not None
    assert "You are helpful." in system_instruction["parts"][0]["text"]

    assert len(contents) == 3
    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"   # assistant → model
    assert contents[2]["role"] == "user"


# ---------------------------------------------------------------------------
# DeepSeekProvider — mock mode (no API key)
# ---------------------------------------------------------------------------

@pytest.fixture()
def deepseek_mock(tmp_path, monkeypatch):
    """DeepSeekProvider in mock mode: DEEPSEEK_API_KEY is cleared for the test."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    return DeepSeekProvider({"results_dir": str(tmp_path)})


def test_deepseek_provider_mock_mode_no_key(deepseek_mock):
    """DeepSeekProvider without an API key runs in mock mode."""
    assert deepseek_mock._mock_mode is True


def test_deepseek_provider_mock_lifecycle(deepseek_mock):
    """Full submit → poll → fetch lifecycle in mock mode."""
    payload = [
        {"id": "d1", "messages": [{"role": "user", "content": "Hello DeepSeek"}]},
        {"id": "d2", "messages": [{"role": "user", "content": "Another message"}]},
    ]
    batch_id = deepseek_mock.submit_batch(payload)
    assert batch_id.startswith("deepseek_mock_")

    status = deepseek_mock.poll_batch(batch_id)
    assert status["status"] == "completed"

    results = deepseek_mock.fetch_batch_result(batch_id)
    assert isinstance(results, list)
    assert len(results) == 2

    ids = {r["id"] for r in results}
    assert ids == {"d1", "d2"}
    for r in results:
        assert "[mock]" in r["output"]
        assert "usage" in r


def test_deepseek_provider_mock_cancel(deepseek_mock):
    """cancel_batch is always a no-op and returns True in mock mode."""
    assert deepseek_mock.cancel_batch("deepseek_mock_12345") is True


def test_deepseek_provider_fetch_missing_batch(deepseek_mock):
    """fetch_batch_result returns an empty list for unknown batch ids."""
    assert deepseek_mock.fetch_batch_result("nonexistent_batch") == []


def test_deepseek_build_messages_with_system(deepseek_mock):
    """_build_messages hoists a top-level 'system' key into the messages list."""
    item = {
        "id": "x1",
        "system": "Be concise.",
        "messages": [{"role": "user", "content": "What is 2+2?"}],
    }
    messages = deepseek_mock._build_messages(item)
    assert messages[0] == {"role": "system", "content": "Be concise."}
    assert messages[1] == {"role": "user", "content": "What is 2+2?"}


def test_deepseek_empty_payload(deepseek_mock):
    """submit_batch with an empty payload returns a valid batch_id."""
    batch_id = deepseek_mock.submit_batch([])
    assert batch_id.startswith("deepseek_mock_")
    assert deepseek_mock.fetch_batch_result(batch_id) == []
