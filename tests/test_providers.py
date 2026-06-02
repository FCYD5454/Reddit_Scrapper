import pytest
from gpt.mocks.mock_provider import MockProvider

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