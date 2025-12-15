import pytest
from unittest.mock import patch, MagicMock
from researcher.ollama_client import OllamaClient

class DummyResponse:
    def __init__(self):
        self._payload = {"message": {"content": "Hello!"}}

    def __getitem__(self, key):
        return self._payload[key]

    def __contains__(self, key):
        return key in self._payload

@patch("ollama.chat")
def test_test_connection_success(mock_chat):
    mock_chat.return_value = DummyResponse()
    client = OllamaClient()
    assert client.test_connection() is True

@patch("ollama.chat")
def test_generate_response_success(mock_chat):
    mock_chat.return_value = DummyResponse()
    client = OllamaClient()
    messages = [{"role": "user", "content": "Hi"}]
    assert client.generate_response(messages) == "Hello!"

@patch("ollama.chat")
def test_generate_response_stream_success(mock_chat):
    mock_chat.return_value = iter([
        {"message": {"content": "Hel"}},
        {"message": {"content": "lo!"}}
    ])
    client = OllamaClient()
    messages = [{"role": "user", "content": "Hi"}]
    chunks = list(client.generate_response_stream(messages))
    assert "".join(chunks) == "Hello!"

@pytest.mark.integration
def test_integration_with_ollama():
    client = OllamaClient()
    try:
        assert client.test_connection() is True
    except RuntimeError:
        pytest.skip("Ollamaサーバーが起動していないためスキップ")


@patch("ollama.embeddings")
def test_get_embeddings_from_dict(mock_embeddings):
    mock_embeddings.return_value = {"embedding": [1, 2, 3]}
    client = OllamaClient()
    assert client.get_embeddings("text", model="foo") == [1, 2, 3]
    mock_embeddings.assert_called_once()


@patch("ollama.embeddings")
def test_get_embeddings_handles_empty(mock_embeddings):
    mock_embeddings.return_value = {}
    client = OllamaClient()
    assert client.get_embeddings("text") == []


@patch("ollama.embeddings")
def test_get_embeddings_raises_when_api_fails(mock_embeddings):
    mock_embeddings.side_effect = RuntimeError("boom")
    client = OllamaClient()
    with pytest.raises(RuntimeError):
        client.get_embeddings("text")
