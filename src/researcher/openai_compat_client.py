"""OpenAI-compatible LLM client.

Supports any provider that exposes the OpenAI chat-completions and embeddings
REST API (VeniceAI, Azure OpenAI, OpenRouter, OpenAI itself, etc.).

The same duck-typed interface as OllamaClient is implemented so that all
callers (ChatManager, QueryAgent, EmbeddingReranker …) can work with either
client without modification.
"""

from __future__ import annotations

import json
import logging
from typing import Generator, List, Optional

import requests

LOGGER = logging.getLogger(__name__)


class OpenAICompatClient:
    """Client for OpenAI-compatible REST APIs.

    Args:
        model: Model identifier as used by the provider (e.g. ``"gpt-4o"``).
        base_url: Provider base URL **without** trailing slash
                  (e.g. ``"https://api.venice.ai/api/v1"``).
        api_key: Bearer token.  May be empty for local servers that require no
                 authentication.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        timeout: int = 120,
    ) -> None:
        import urllib.parse
        _scheme = urllib.parse.urlparse(base_url).scheme.lower()
        if _scheme not in ("http", "https"):
            raise ValueError(
                f"プロバイダのベースURLには http または https スキームが必要です: {base_url!r}"
            )
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _embeddings_url(self) -> str:
        return f"{self.base_url}/embeddings"

    # ------------------------------------------------------------------
    # Public interface (mirrors OllamaClient)
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        """Send a minimal chat request to verify connectivity and API key.

        Raises:
            ValueError: When model is not configured.
            RuntimeError: On HTTP / network errors.
        """
        if not self.model:
            raise ValueError(
                "モデル名が設定されていません。Settingsページでモデルを選択してください。"
            )
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5,
            }
            resp = requests.post(
                self._chat_url(),
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return bool(data.get("choices"))
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"プロバイダへの接続に失敗しました: {exc}") from exc

    def generate_response(self, messages: list) -> str:
        """Generate a non-streaming chat completion.

        Args:
            messages: List of ``{"role": ..., "content": ...}`` dicts.

        Returns:
            The assistant reply as a plain string.

        Raises:
            RuntimeError: On API or network errors.
        """
        if not self.model:
            raise ValueError(
                "モデル名が設定されていません。Settingsページでモデルを選択してください。"
            )
        try:
            # Strip internal keys (search_result, search_results) that are
            # researcher-internal and not part of the OpenAI message schema.
            clean = [
                {"role": m["role"], "content": m["content"]}
                for m in messages
                if m.get("role") in ("system", "user", "assistant")
            ]
            payload = {"model": self.model, "messages": clean}
            resp = requests.post(
                self._chat_url(),
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"OpenAI互換API応答エラー: {exc}") from exc
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"OpenAI互換APIレスポンス解析エラー: {exc}") from exc

    def generate_response_stream(self, messages: list) -> Generator[str, None, None]:
        """Generate a streaming chat completion, yielding content chunks.

        Args:
            messages: List of ``{"role": ..., "content": ...}`` dicts.

        Yields:
            Text fragments as they arrive from the SSE stream.

        Raises:
            RuntimeError: On API or network errors.
        """
        if not self.model:
            raise ValueError(
                "モデル名が設定されていません。Settingsページでモデルを選択してください。"
            )
        try:
            clean = [
                {"role": m["role"], "content": m["content"]}
                for m in messages
                if m.get("role") in ("system", "user", "assistant")
            ]
            payload = {"model": self.model, "messages": clean, "stream": True}
            with requests.post(
                self._chat_url(),
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
                stream=True,
            ) as resp:
                resp.raise_for_status()
                for raw_line in resp.iter_lines():
                    if not raw_line:
                        continue
                    line: str = (
                        raw_line.decode("utf-8")
                        if isinstance(raw_line, bytes)
                        else raw_line
                    )
                    if line.startswith("data: "):
                        line = line[len("data: "):]
                    if line.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = (
                                choices[0]
                                .get("delta", {})
                                .get("content")
                            )
                            if delta:
                                yield delta
                    except json.JSONDecodeError:
                        LOGGER.debug("SSEチャンク解析スキップ: %s", line)
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"OpenAI互換APIストリームエラー: {exc}") from exc

    def get_embeddings(
        self, prompt: str, model: Optional[str] = None
    ) -> List[float]:
        """Fetch a text embedding vector.

        Args:
            prompt: Text to embed.
            model: Override embedding model name (defaults to ``self.model``).

        Returns:
            List of floats, or empty list on error.
        """
        model_name = model or self.model
        if not model_name:
            LOGGER.warning("埋め込みモデルが未設定です")
            return []
        try:
            payload = {"model": model_name, "input": prompt}
            resp = requests.post(
                self._embeddings_url(),
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            # Standard OpenAI response: {"data": [{"embedding": [...]}]}
            embedding = data.get("data", [{}])[0].get("embedding", [])
            return embedding if isinstance(embedding, list) else []
        except Exception as exc:
            LOGGER.warning("OpenAI互換API埋め込み取得エラー: %s", exc)
            return []

    def list_models(self) -> List[str]:
        """Return models configured for this provider.

        Unlike OllamaClient, OpenAI-compatible providers require you to know
        the model names in advance (different providers expose different model
        lists, and the ``/models`` endpoint may not be available).  The list
        is therefore stored in the provider configuration in settings.json and
        passed in at construction time.

        Returns an empty list here so that the Settings page can fall back to
        showing the manually configured model list.
        """
        return []
