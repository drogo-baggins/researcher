from typing import List, Optional
import logging
import os

import ollama
import requests

LOGGER = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


class OllamaClient:
    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model
        self.base_url = (base_url or "").strip() or DEFAULT_OLLAMA_BASE_URL
        self._client = ollama.Client(host=self.base_url)

    def test_connection(self) -> bool:
        if not self.model:
            raise ValueError(
                "モデル名が設定されていません。Settingsページでモデルを選択してください。"
            )
        try:
            response = self._client.chat(
                model=self.model, messages=[{"role": "user", "content": "Hello"}]
            )
            return bool(response and "message" in response)
        except Exception as e:
            raise RuntimeError(f"Ollamaサーバーへの接続に失敗しました: {e}")

    def generate_response(self, messages):
        try:
            response = self._client.chat(model=self.model, messages=messages)
            return response["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Ollama応答エラー: {e}")

    def generate_response_stream(self, messages):
        try:
            stream = self._client.chat(model=self.model, messages=messages, stream=True)
            for chunk in stream:
                yield chunk["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Ollamaストリーム応答エラー: {e}")

    def get_embeddings(self, prompt: str, model: Optional[str] = None) -> List[float]:
        model_name = model or self.model
        try:
            response = self._client.embeddings(model=model_name, prompt=prompt)
        except Exception as exc:
            raise RuntimeError(f"Ollama埋め込み取得エラー: {exc}") from exc

        embedding = []
        if isinstance(response, dict):
            embedding = (
                response.get("embedding")
                or response.get("embeddings")
                or response.get("data")
                or []
            )
        elif isinstance(response, list):
            embedding = response

        if not embedding:
            return []

        if isinstance(embedding, list):
            return embedding

        return []

    def list_models(self) -> List[str]:
        try:
            response = self._client.list()
            if hasattr(response, "models") and response.models:
                return [m.model for m in response.models if m.model]
            elif isinstance(response, dict):
                models = response.get("models", [])
                if models:
                    return [
                        m.get("model", "") or m.get("name", "")
                        for m in models
                        if m.get("model") or m.get("name")
                    ]
        except Exception as e:
            LOGGER.debug(f"ollama.Client.list() failed: {e}, trying HTTP API...")

        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return [m.get("name", "") for m in models if m.get("name")]
        except requests.RequestException as e:
            LOGGER.warning(f"HTTP API call to Ollama failed: {e}")
        except Exception as e:
            LOGGER.warning(f"Error parsing Ollama models response: {e}")

        LOGGER.warning("Failed to retrieve model list from Ollama")
        return []
