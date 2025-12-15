import pytest
from unittest.mock import MagicMock

from researcher.agent import QueryAgent
from researcher.ollama_client import OllamaClient


def test_analyze_query_returns_keywords():
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate_response.return_value = '{"needs_search": true, "keywords": ["python"], "reasoning": "Latest"}'

    agent = QueryAgent(mock_client)
    result = agent.analyze_query("Tell me about Python releases")

    assert result["needs_search"] is True
    assert result["keywords"] == ["python"]
    assert "reasoning" in result


def test_analyze_query_handles_invalid_json():
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate_response.return_value = "not json"

    agent = QueryAgent(mock_client)
    result = agent.analyze_query("Tell me about Python releases")

    assert result["needs_search"] is False
    assert result["keywords"] == []


def test_analyze_query_handles_client_error():
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate_response.side_effect = RuntimeError("boom")

    agent = QueryAgent(mock_client)
    result = agent.analyze_query("Tell me about Python releases")

    assert result["needs_search"] is False
    assert result["keywords"] == []


@pytest.mark.integration
def test_integration_query_agent():
    client = OllamaClient()
    agent = QueryAgent(client)
    try:
        analysis = agent.analyze_query("What is the latest news about Python?")
    except RuntimeError:
        pytest.skip("Ollamaサーバーに接続できないためスキップ")
    assert "needs_search" in analysis