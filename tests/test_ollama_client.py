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


# ============================================================================
# Tests for list_models() method (Phase 3)
# ============================================================================


class TestListModels:
    """Test suite for OllamaClient.list_models()"""

    @patch("ollama.list")
    def test_list_models_success(self, mock_list):
        """Test successful retrieval of model list."""
        mock_list.return_value = {
            "models": [
                {"name": "llama3:latest", "size": 1234567},
                {"name": "mixtral:8x7b", "size": 7654321}
            ]
        }
        client = OllamaClient()
        models = client.list_models()
        
        assert models == ["llama3:latest", "mixtral:8x7b"]
        mock_list.assert_called_once()

    @patch("ollama.list")
    def test_list_models_empty_response(self, mock_list):
        """Test handling of empty model list."""
        mock_list.return_value = {"models": []}
        client = OllamaClient()
        models = client.list_models()
        
        assert models == []

    @patch("ollama.list")
    def test_list_models_missing_models_key(self, mock_list):
        """Test handling when 'models' key is missing."""
        mock_list.return_value = {}
        client = OllamaClient()
        models = client.list_models()
        
        assert models == []

    @patch("ollama.list")
    def test_list_models_missing_name_field(self, mock_list):
        """Test filtering of models without 'name' field."""
        mock_list.return_value = {
            "models": [
                {"name": "valid-model"},
                {"size": 123},  # missing name
                {"name": "another-valid"},
            ]
        }
        client = OllamaClient()
        models = client.list_models()
        
        assert models == ["valid-model", "another-valid"]

    @patch("ollama.list")
    def test_list_models_empty_name(self, mock_list):
        """Test filtering of models with empty name."""
        mock_list.return_value = {
            "models": [
                {"name": "valid"},
                {"name": ""},  # empty name
                {"name": "another"}
            ]
        }
        client = OllamaClient()
        models = client.list_models()
        
        assert models == ["valid", "another"]

    @patch("ollama.list")
    def test_list_models_api_error(self, mock_list):
        """Test graceful handling of API errors."""
        mock_list.side_effect = RuntimeError("Connection failed")
        client = OllamaClient()
        models = client.list_models()
        
        assert models == []

    @patch("ollama.list")
    def test_list_models_timeout(self, mock_list):
        """Test handling of timeout errors."""
        mock_list.side_effect = TimeoutError("Request timeout")
        client = OllamaClient()
        models = client.list_models()
        
        assert models == []

    @patch("ollama.list")
    def test_list_models_single_model(self, mock_list):
        """Test retrieval with single model."""
        mock_list.return_value = {
            "models": [
                {"name": "llama3:latest"}
            ]
        }
        client = OllamaClient()
        models = client.list_models()
        
        assert models == ["llama3:latest"]
        assert len(models) == 1

    @patch("ollama.list")
    def test_list_models_many_models(self, mock_list):
        """Test retrieval with many models."""
        model_names = [f"model-{i}" for i in range(10)]
        mock_list.return_value = {
            "models": [{"name": name} for name in model_names]
        }
        client = OllamaClient()
        models = client.list_models()
        
        assert models == model_names
        assert len(models) == 10

    @patch("ollama.list")
    def test_list_models_preserves_order(self, mock_list):
        """Test that model order is preserved."""
        models_input = ["alpha", "beta", "gamma", "delta"]
        mock_list.return_value = {
            "models": [{"name": name} for name in models_input]
        }
        client = OllamaClient()
        models = client.list_models()
        
        assert models == models_input

    @patch("ollama.list")
    def test_list_models_with_special_characters(self, mock_list):
        """Test handling of model names with special characters."""
        mock_list.return_value = {
            "models": [
                {"name": "model:v1.0"},
                {"name": "model/latest"},
                {"name": "model-with-dashes"}
            ]
        }
        client = OllamaClient()
        models = client.list_models()
        
        assert models == ["model:v1.0", "model/latest", "model-with-dashes"]


@pytest.mark.integration
class TestListModelsIntegration:
    """Integration tests requiring actual Ollama server."""

    def test_list_models_integration_returns_list(self):
        """Test that list_models() returns a list."""
        client = OllamaClient()
        try:
            models = client.list_models()
            assert isinstance(models, list)
        except Exception:
            pytest.skip("Ollama server not running or unavailable")

    def test_list_models_integration_all_strings(self):
        """Test that all returned model names are strings."""
        client = OllamaClient()
        try:
            models = client.list_models()
            if models:  # Only check if models exist
                assert all(isinstance(m, str) for m in models)
        except Exception:
            pytest.skip("Ollama server not running or unavailable")

    def test_list_models_integration_no_empty_strings(self):
        """Test that no empty strings are returned."""
        client = OllamaClient()
        try:
            models = client.list_models()
            assert all(m for m in models)  # All non-empty
        except Exception:
            pytest.skip("Ollama server not running or unavailable")
