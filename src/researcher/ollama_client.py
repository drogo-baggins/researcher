from typing import List, Optional
import logging

import ollama

LOGGER = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, model: str = "llama3"):
        self.model = model

    def test_connection(self) -> bool:
        try:
            response = ollama.chat(model=self.model, messages=[{"role": "user", "content": "Hello"}])
            return bool(response and "message" in response)
        except Exception as e:
            raise RuntimeError(f"Ollamaサーバーへの接続に失敗しました: {e}")

    def generate_response(self, messages):
        try:
            response = ollama.chat(model=self.model, messages=messages)
            return response["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Ollama応答エラー: {e}")

    def generate_response_stream(self, messages):
        try:
            stream = ollama.chat(model=self.model, messages=messages, stream=True)
            for chunk in stream:
                yield chunk["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Ollamaストリーム応答エラー: {e}")

    def get_embeddings(self, prompt: str, model: Optional[str] = None) -> List[float]:
        model_name = model or self.model
        try:
            response = ollama.embeddings(model=model_name, prompt=prompt)
        except Exception as exc:
            raise RuntimeError(f"Ollama埋め込み取得エラー: {exc}") from exc

        embedding = []
        if isinstance(response, dict):
            embedding = response.get("embedding") or response.get("embeddings") or response.get("data") or []
        elif isinstance(response, list):
            embedding = response

        if not embedding:
            return []

        if isinstance(embedding, list):
            return embedding

        return []

    def list_models(self) -> List[str]:
        """利用可能なOllamaモデルの一覧を取得
        
        Returns:
            モデル名のリスト（例: ["llama3:latest", "mixtral:8x7b"]）
            エラー時は空リスト
        """
        try:
            response = ollama.list()
            models = response.get("models", [])
            return [m.get("name", "") for m in models if m.get("name")]
        except Exception as e:
            LOGGER.warning(f"モデル一覧の取得に失敗: {e}")
            return []
