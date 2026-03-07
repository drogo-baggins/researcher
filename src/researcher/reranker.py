import logging
import math
from typing import Any, Dict, Iterable, List, Optional

LOGGER = logging.getLogger(__name__)


class EmbeddingReranker:
    def __init__(self, ollama_client: Any, model: Optional[str] = None, threshold: float = 0.5):
        self.ollama_client = ollama_client
        self.model = model
        self.threshold = threshold

    def rerank(self, query: str, results: Iterable[Dict[str, Optional[str]]]) -> List[Dict[str, object]]:
        query_embedding = self._get_embedding(query)
        if not query_embedding:
            return []

        scored: List[Dict[str, object]] = []
        for item in results:
            text = self._combine_text(item)
            embedding = self._get_embedding(text)
            if not embedding:
                continue
            score = self._cosine_similarity(query_embedding, embedding)
            if score >= self.threshold:
                entry: Dict[str, object] = dict(item)
                entry["relevance_score"] = score
                scored.append(entry)

        return sorted(scored, key=lambda entry: entry["relevance_score"], reverse=True)

    def _get_embedding(self, text: str) -> List[float]:
        if not text:
            return []
        try:
            vector = self.ollama_client.get_embeddings(text, model=self.model)
        except Exception as exc:
            LOGGER.warning("Failed to fetch embedding: %s", exc)
            return []
        if not vector:
            return []
        return vector

    @staticmethod
    def _combine_text(result: Dict[str, Optional[str]]) -> str:
        title = result.get("title") or ""
        snippet = result.get("snippet") or ""
        return f"{title} {snippet}".strip()

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm_a = math.sqrt(sum(a * a for a in vec1))
        norm_b = math.sqrt(sum(b * b for b in vec2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)