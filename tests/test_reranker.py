from researcher.reranker import EmbeddingReranker


def test_rerank_filters_by_threshold(monkeypatch):
    reranker = EmbeddingReranker(object(), threshold=0.5)

    def fake_embedding(text):
        if text == "query":
            return [1.0, 0.0]
        if "Good" in text:
            return [0.9, 0.1]
        if "Bad" in text:
            return [0.1, 0.9]
        return []

    monkeypatch.setattr(reranker, "_get_embedding", fake_embedding)

    results = [
        {"title": "Good", "url": "https://good", "snippet": "match"},
        {"title": "Bad", "url": "https://bad", "snippet": "other"},
    ]

    reranked = reranker.rerank("query", results)
    assert len(reranked) == 1
    assert reranked[0]["title"] == "Good"
    assert reranked[0]["relevance_score"] > 0.5


def test_rerank_handles_empty_embeddings(monkeypatch):
    reranker = EmbeddingReranker(object(), threshold=0.0)

    def fake_embedding(_):
        return []

    monkeypatch.setattr(reranker, "_get_embedding", fake_embedding)

    results = [{"title": "Any", "url": "https://any", "snippet": "text"}]
    assert reranker.rerank("query", results) == []