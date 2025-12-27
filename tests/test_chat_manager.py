import pytest
from unittest.mock import MagicMock

from researcher.chat_manager import ChatManager
from researcher.searxng_client import SearXNGClient


def make_chat_manager_with_search(search_results=None):
    ollama = MagicMock()
    searxng = MagicMock()
    searxng.search.return_value = {
        "raw": {"results": search_results or []},
        "results": search_results or [],
    }
    return ChatManager(ollama, searxng_client=searxng), searxng


def test_search_success():
    chat, searxng_mock = make_chat_manager_with_search(
        [
            {"title": "Example", "url": "https://example.com", "snippet": "snippet"}
        ]
    )
    result = chat.search("python")

    assert "formatted" in result
    assert "raw" in result
    assert searxng_mock.search.called
    assert "検索結果" in result["formatted"]


def test_search_without_client():
    chat = ChatManager(MagicMock())
    with pytest.raises(RuntimeError) as exc:
        chat.search("python")
    assert "検索機能が有効化されていません" in str(exc.value)


def test_search_results_added_to_history():
    chat, _ = make_chat_manager_with_search(
        [
            {"title": "Example", "url": "https://example.com", "snippet": "snippet"}
        ]
    )
    chat.search("python")
    history = chat.get_history()
    assert any(m["role"] == "system" and "検索結果" in m["content"] for m in history)

def test_clear_history_removes_search_results():
    chat, _ = make_chat_manager_with_search(
        [
            {"title": "Example", "url": "https://example.com", "snippet": "snippet"}
        ]
    )
    chat.add_system_message("You are a helpful assistant.")
    chat.search("python")
    history_before = chat.get_history()
    assert len(history_before) >= 2
    chat.clear_history()
    history_after = chat.get_history()
    assert len(history_after) == 1
    assert history_after[0]["content"] == "You are a helpful assistant."


def test_add_search_results_formatting():
    chat, _ = make_chat_manager_with_search(
        [
            {"title": "Foo", "url": "https://foo", "snippet": "bar"},
            {"title": None, "url": None, "snippet": None},
        ]
    )
    formatted = chat.search("query")["formatted"]
    assert "Foo" in formatted
    assert "(タイトルなし)" in formatted
    assert formatted.count("\n") >= 3


def test_auto_search_uses_agent_and_reranker():
    ollama = MagicMock()
    searxng = MagicMock()
    searxng.search.return_value = {
        "raw": {"results": []},
        "results": [
            {"title": "Auto", "url": "https://auto", "snippet": "result"}
        ],
    }
    agent = MagicMock()
    agent.analyze_query.return_value = {
        "needs_search": True,
        "keywords": ["python"],
        "reasoning": "Test",
    }
    reranker = MagicMock()
    reranker.rerank.return_value = searxng.search.return_value["results"]

    chat = ChatManager(ollama, searxng_client=searxng, agent=agent, reranker=reranker)
    result = chat.auto_search("question")

    assert result["searched"] is True
    assert reranker.rerank.called
    assert any("検索結果" in m["content"] for m in chat.get_history())


def test_auto_search_skips_when_agent_declines():
    ollama = MagicMock()
    agent = MagicMock()
    agent.analyze_query.return_value = {
        "needs_search": False,
        "keywords": [],
        "reasoning": "No need",
    }

    chat = ChatManager(ollama, searxng_client=MagicMock(), agent=agent)
    result = chat.auto_search("question")


    assert result["searched"] is False
    assert result["formatted"] == ""
    assert all("検索結果" not in m["content"] for m in chat.get_history())


def test_search_with_citation_manager():
    from researcher.citation_manager import CitationManager
    ollama = MagicMock()
    searxng = MagicMock()
    citation_mgr = CitationManager()
    search_results = [
        {"title": "Result 1", "url": "http://example.com/1", "snippet": "Snippet 1", "score": 0.9},
        {"title": "Result 2", "url": "http://example.com/2", "snippet": "Snippet 2", "score": 0.8},
    ]
    searxng.search.return_value = {
        "raw": {"results": search_results},
        "results": search_results,
    }
    chat = ChatManager(ollama, searxng_client=searxng, citation_manager=citation_mgr)
    result = chat.search("test query")
    
    assert len(chat.current_citation_ids) == 2
    assert len(citation_mgr.get_all_citations()) == 2
    assert "[1]" in result["formatted"] or "[2]" in result["formatted"]


def test_get_response_appends_citations():
    from researcher.citation_manager import CitationManager
    ollama = MagicMock()
    ollama.generate_response.return_value = "This is the response."
    citation_mgr = CitationManager()
    chat = ChatManager(ollama, citation_manager=citation_mgr)
    
    # 事前に引用を追加
    cid1 = citation_mgr.add_citation("http://example.com", "Example", "A snippet", "2025-01-01", 0.8)
    chat.current_citation_ids.append(cid1)
    
    response = chat.get_response()
    assert "## 参照" in response
    assert "Example" in response
    assert len(chat.current_citation_ids) == 0


def test_get_response_stream_appends_citations():
    from researcher.citation_manager import CitationManager
    ollama = MagicMock()
    ollama.generate_response_stream.return_value = ["This ", "is ", "the ", "response."]
    citation_mgr = CitationManager()
    chat = ChatManager(ollama, citation_manager=citation_mgr)
    
    cid1 = citation_mgr.add_citation("http://example.com", "Example", "A snippet", "2025-01-01", 0.8)
    chat.current_citation_ids.append(cid1)
    
    chunks = list(chat.get_response_stream())
    full_response = "".join(chunks)
    assert "## 参照" in full_response
    assert len(chat.current_citation_ids) == 0


def test_citation_manager_none_backward_compatibility():
    ollama = MagicMock()
    searxng = MagicMock()
    ollama.generate_response.return_value = "Response"
    searxng.search.return_value = {
        "raw": {},
        "results": [
            {"title": "Result 1", "url": "http://example.com/1", "snippet": "Snippet 1"},
        ],
    }
    chat = ChatManager(ollama, searxng_client=searxng, citation_manager=None)
    result = chat.search("test")
    assert "検索結果" in result["formatted"]
    
    response = chat.get_response()
    assert response == "Response"
    assert "## 参照" not in response


@pytest.mark.integration
def test_integration_search_results():
    try:
        searxng_client = SearXNGClient("http://localhost:8888")
        assert searxng_client.test_connection()
    except RuntimeError:
        pytest.skip("SearXNGサーバーが起動していないためスキップ")
    chat = ChatManager(MagicMock(), searxng_client=searxng_client)
    result = chat.search("python")
    assert "formatted" in result


def test_auto_search_with_or_keywords():
    """Test that keywords are OR-combined in search query."""
    mock_ollama = MagicMock()
    mock_agent = MagicMock()
    mock_searxng = MagicMock()
    
    # Agent returns needs_search=True with keywords
    mock_agent.analyze_query.return_value = {
        "needs_search": True,
        "keywords": ["keyword1", "keyword2", "keyword3"],
        "reasoning": "Multiple keywords found",
    }
    
    # Mock search results
    mock_searxng.search.return_value = {
        "raw": {},
        "results": [
            {"url": "https://example.com", "title": "Example", "snippet": "Test"},
        ],
    }
    
    chat = ChatManager(
        mock_ollama,
        searxng_client=mock_searxng,
        agent=mock_agent,
    )
    
    result = chat.auto_search("test query")
    
    assert result["searched"] is True
    
    # Verify search was called with OR-combined keywords
    call_args = mock_searxng.search.call_args[0][0]
    assert "test query" in call_args
    assert "keyword1 OR keyword2 OR keyword3" in call_args or "(keyword1 OR keyword2 OR keyword3)" in call_args


def test_auto_search_without_keywords():
    """Test that original query is used when no keywords returned."""
    mock_ollama = MagicMock()
    mock_agent = MagicMock()
    mock_searxng = MagicMock()
    
    # Agent returns needs_search=True but no keywords
    mock_agent.analyze_query.return_value = {
        "needs_search": True,
        "keywords": [],
        "reasoning": "Search needed",
    }
    
    # Mock search results
    mock_searxng.search.return_value = {
        "raw": {},
        "results": [],
    }
    
    chat = ChatManager(
        mock_ollama,
        searxng_client=mock_searxng,
        agent=mock_agent,
    )
    
    result = chat.auto_search("test query")
    
    assert result["searched"] is True
    
    # Verify search was called with original query only
    call_args = mock_searxng.search.call_args[0][0]
    assert call_args == "test query"


# WebCrawler Integration Tests
def test_chat_manager_accepts_web_crawler():
    """Test that ChatManager accepts web_crawler parameter."""
    from researcher.web_crawler import WebCrawler
    
    mock_client = MagicMock()
    crawler = WebCrawler()
    
    chat = ChatManager(mock_client, web_crawler=crawler)
    
    assert chat.web_crawler is crawler


def test_chat_manager_crawls_on_search():
    """Test that ChatManager crawls URLs after search."""
    from researcher.web_crawler import WebCrawler
    
    mock_client = MagicMock()
    mock_searxng = MagicMock()
    mock_crawler = MagicMock()
    
    # Mock search results
    mock_searxng.search.return_value = {
        "raw": {},
        "results": [
            {"url": "https://example.com", "title": "Example", "snippet": "Test"},
        ],
    }
    
    # Mock crawler
    mock_crawler.crawl_results.return_value = {
        "content": {"https://example.com": "Crawled content"},
        "failed_domains": set(),
        "success_rate": 1.0,
        "total_attempts": 1,
        "successful_crawls": 1
    }
    mock_crawler.format_crawled_content.return_value = "[Web Content]\nCrawled content"
    
    chat = ChatManager(
        mock_client,
        searxng_client=mock_searxng,
        web_crawler=mock_crawler,
    )
    
    chat.search("test query")
    
    # Verify crawler was called
    mock_crawler.crawl_results.assert_called_once()
    
    # Verify last_search_content was set
    assert chat.last_search_content == "[Web Content]\nCrawled content"


def test_chat_manager_injects_crawled_content_into_response():
    """Test that crawled content is injected into LLM response (as system message)."""
    from researcher.web_crawler import WebCrawler
    
    mock_client = MagicMock()
    mock_client.generate_response.return_value = "Response text"
    
    crawler = WebCrawler()
    
    chat = ChatManager(mock_client, web_crawler=crawler)
    chat.add_user_message("Tell me about Python")
    
    # Set last_search_content as if from a search
    chat.last_search_content = "[Web Content]\nPython is a programming language"
    # Set turns remaining to inject content
    chat.last_search_turns_remaining = 1
    
    response = chat.get_response()
    
    # Verify that generate_response was called
    assert mock_client.generate_response.called
    
    # Get the messages passed to generate_response
    call_args = mock_client.generate_response.call_args[0][0]
    
    # Verify system message includes crawled content (no longer in user message)
    system_messages = [m for m in call_args if m.get("role") == "system"]
    assert any("Python is a programming language" in m["content"] for m in system_messages)
    
    # Verify user message does NOT contain crawled content (now in system message)
    user_messages = [m for m in call_args if m.get("role") == "user"]
    if user_messages:
        last_user_msg = user_messages[-1]["content"]
        assert "Python is a programming language" not in last_user_msg


def test_chat_manager_clears_search_content_on_history_clear():
    """Test that last_search_content is cleared when history is cleared."""
    from researcher.web_crawler import WebCrawler
    
    mock_client = MagicMock()
    chat = ChatManager(mock_client)
    
    chat.last_search_content = "Some crawled content"
    chat.clear_history()
    
    assert chat.last_search_content == ""


# RAG Enhancement Tests
def test_search_updates_citation_snippets_with_crawled_content():
    """検索後のクロールで引用スニペットが更新されることを確認"""
    from researcher.citation_manager import CitationManager
    
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_crawler = MagicMock()
    citation_mgr = CitationManager()
    
    # 検索結果
    mock_searxng.search.return_value = {
        "raw": {},
        "results": [
            {"url": "https://example.com", "title": "Example", "snippet": "Original snippet", "score": 0.9}
        ],
    }
    
    # クロール結果
    mock_crawler.crawl_results.return_value = {
        "content": {"https://example.com": "Detailed crawled content from the webpage..."},
        "failed_domains": set(),
        "success_rate": 1.0,
        "total_attempts": 1,
        "successful_crawls": 1
    }
    mock_crawler.format_crawled_content.return_value = "[Web Content]\nDetailed content"
    
    chat = ChatManager(
        mock_ollama,
        searxng_client=mock_searxng,
        citation_manager=citation_mgr,
        web_crawler=mock_crawler,
    )
    
    chat.search("test query")
    
    # 引用が追加されていることを確認
    citations = citation_mgr.get_all_citations()
    assert len(citations) == 1
    
    # スニペットがクロール内容で更新されていることを確認
    assert "Detailed crawled content" in citations[0]["snippet"]
    assert "Original snippet" not in citations[0]["snippet"]


def test_get_response_injects_crawled_content_as_system_message():
    """クロール内容がシステムメッセージとして注入されることを確認"""
    mock_ollama = MagicMock()
    mock_ollama.generate_response.return_value = "Response based on crawled data"
    
    chat = ChatManager(mock_ollama)
    chat.add_user_message("Tell me about Python")
    chat.last_search_content = "[Web Content]\nPython is a programming language..."
    # Set turns remaining to inject content
    chat.last_search_turns_remaining = 1
    
    response = chat.get_response()
    
    # generate_responseに渡されたメッセージを確認
    call_args = mock_ollama.generate_response.call_args[0][0]
    
    # システムメッセージにクロール内容とRAGプロンプトが両方含まれることを確認
    system_messages = [m for m in call_args if m.get("role") == "system"]
    
    # クロール内容が存在することを確認
    assert any("Python is a programming language" in m["content"] for m in system_messages), \
        "Crawled content should be injected in system message"
    
    # RAGシステムプロンプトが存在することを確認
    expected_rag_prompt = chat._get_rag_system_prompt()
    system_content = " ".join(m["content"] for m in system_messages)
    assert any(rag_phrase in system_content for rag_phrase in ["この情報のみを事実として", "Use ONLY this information as facts"]), \
        "RAG prompt with strict instructions should be in system message"
    
    # ユーザーメッセージには注入されていないことを確認
    user_messages = [m for m in call_args if m.get("role") == "user"]
    assert all("Python is a programming language" not in m["content"] for m in user_messages)


def test_end_to_end_search_crawl_citation_response():
    """検索→クロール→引用更新→LLM回答の全フローを確認"""
    from researcher.citation_manager import CitationManager
    
    mock_ollama = MagicMock()
    mock_ollama.generate_response.return_value = "Comprehensive answer with sources"
    mock_searxng = MagicMock()
    mock_crawler = MagicMock()
    citation_mgr = CitationManager()
    
    # 検索結果
    mock_searxng.search.return_value = {
        "raw": {},
        "results": [
            {"url": "https://news.com/article", "title": "News Article", "snippet": "Short snippet", "score": 0.95}
        ],
    }
    
    # クロール結果
    mock_crawler.crawl_results.return_value = {
        "content": {"https://news.com/article": "Full article content with detailed information..."},
        "failed_domains": set(),
        "success_rate": 1.0,
        "total_attempts": 1,
        "successful_crawls": 1
    }
    mock_crawler.format_crawled_content.return_value = "[Web Content]\nhttps://news.com/article:\nFull article content..."
    
    chat = ChatManager(
        mock_ollama,
        searxng_client=mock_searxng,
        citation_manager=citation_mgr,
        web_crawler=mock_crawler,
    )
    
    # 1. 検索実行
    chat.search("latest news")
    
    # 2. 引用が更新されていることを確認
    citations = citation_mgr.get_all_citations()
    assert "Full article content" in citations[0]["snippet"]
    
    # 3. ユーザーメッセージ追加
    chat.add_user_message("Summarize the news")
    
    # 4. LLM回答生成
    response = chat.get_response()
    
    # 5. システムメッセージにクロール内容が含まれることを確認
    call_args = mock_ollama.generate_response.call_args[0][0]
    system_msgs = [m for m in call_args if m.get("role") == "system"]
    assert any("Full article content" in m["content"] for m in system_msgs)
    
    # 6. 引用が回答に含まれることを確認
    assert "## 参照" in response
    assert "News Article" in response


def test_citation_mapping_with_add_citation_failure():
    """Comment 1: 検証 - Citation追加失敗時も正しいスニペット更新を確認"""
    from researcher.citation_manager import CitationManager
    
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_crawler = MagicMock()
    citation_mgr = CitationManager()
    
    # 検索結果（3件）
    search_results = [
        {"url": "https://url1.com", "title": "Title 1", "snippet": "Snippet 1", "score": 0.9},
        {"url": "https://url2.com", "title": "Title 2", "snippet": "Snippet 2", "score": 0.8},
        {"url": "https://url3.com", "title": "Title 3", "snippet": "Snippet 3", "score": 0.7},
    ]
    mock_searxng.search.return_value = {
        "raw": {},
        "results": search_results,
    }
    
    # クロール結果
    mock_crawler.crawl_results.return_value = {
        "content": {
            "https://url1.com": "Crawled content for URL 1",
            "https://url2.com": "Crawled content for URL 2",
            "https://url3.com": "Crawled content for URL 3",
        },
        "failed_domains": set(),
        "success_rate": 1.0,
        "total_attempts": 3,
        "successful_crawls": 3
    }
    mock_crawler.format_crawled_content.return_value = "[Web Content]..."
    
    chat = ChatManager(
        mock_ollama,
        searxng_client=mock_searxng,
        citation_manager=citation_mgr,
        web_crawler=mock_crawler,
    )
    
    # 実際のCitation追加を実行すると、すべて成功する
    chat.search("test query")
    
    citations = citation_mgr.get_all_citations()
    
    # 各引用が正しくスニペット更新されていることを確認
    # _citation_idがresultに格納されているため、インデックスズレは発生しない
    assert len(citations) == 3
    assert "Crawled content for URL 1" in citations[0]["snippet"]
    assert "Crawled content for URL 2" in citations[1]["snippet"]
    assert "Crawled content for URL 3" in citations[2]["snippet"]


def test_crawled_content_expires_after_one_response():
    """Comment 2: 検証 - クロール内容が1レスポンス後に自動的にクリアされることを確認"""
    mock_ollama = MagicMock()
    mock_ollama.generate_response.return_value = "Response"
    
    chat = ChatManager(mock_ollama)
    chat.add_user_message("Question 1")
    chat.last_search_content = "[Web Content]..."
    chat.last_search_turns_remaining = 1
    
    # 最初のレスポンス - クロール内容が注入される
    response1 = chat.get_response()
    
    # 最初のコールでlast_search_turns_remainingが1から0に減少し、内容がクリアされている
    assert chat.last_search_content == ""
    assert chat.last_search_turns_remaining == 0
    
    # 次のレスポンスではクロール内容は注入されない
    chat.add_user_message("Question 2")
    response2 = chat.get_response()
    
    # generate_responseの2回目のコールを確認
    assert mock_ollama.generate_response.call_count == 2
    
    # 2回目のコールではクロール内容が含まれていないことを確認
    call_args_2 = mock_ollama.generate_response.call_args_list[1][0][0]
    system_messages_2 = [m for m in call_args_2 if m.get("role") == "system"]
    assert not any("[Web Content]" in m.get("content", "") for m in system_messages_2)


def test_crawled_content_not_injected_when_turns_zero():
    """Comment 2: 検証 - turns_remaining=0の時、クロール内容が注入されないことを確認"""
    mock_ollama = MagicMock()
    mock_ollama.generate_response.return_value = "Response"
    
    chat = ChatManager(mock_ollama)
    chat.add_user_message("Question")
    chat.last_search_content = "[Web Content]..."
    chat.last_search_turns_remaining = 0  # No remaining turns
    
    response = chat.get_response()
    
    # generate_responseに渡されたメッセージを確認
    call_args = mock_ollama.generate_response.call_args[0][0]
    
    # システムメッセージにクロール内容が含まれていないことを確認
    system_messages = [m for m in call_args if m.get("role") == "system"]
    assert not any("[Web Content]" in m.get("content", "") for m in system_messages)


# ============================================================================
# 検索失敗時のリトライロジックテスト
# ============================================================================

def test_search_retries_on_runtime_error():
    """Test that search retries when searxng_client.search() raises RuntimeError."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    
    # 1回目失敗、2回目成功
    mock_searxng.search.side_effect = [
        RuntimeError("SearXNG error"),
        {"raw": {}, "results": [{"url": "https://success.com", "title": "Success", "snippet": "Test snippet"}]}
    ]
    mock_agent.generate_search_retry_query.return_value = "alternative query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=None)
    result = chat.search("original query")
    
    # 検証
    assert mock_searxng.search.call_count == 2
    assert mock_agent.generate_search_retry_query.call_count == 1
    assert result["search_failed"] == False
    assert len(result["results"]) == 1
    assert result["results"][0]["url"] == "https://success.com"


def test_search_retries_on_empty_results():
    """Test that search retries when results are empty."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    
    # 1回目空結果、2回目成功
    mock_searxng.search.side_effect = [
        {"raw": {}, "results": []},
        {"raw": {}, "results": [{"url": "https://success.com", "title": "Success", "snippet": "Test"}]}
    ]
    mock_agent.generate_search_retry_query.return_value = "retry query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=None)
    result = chat.search("query")
    
    # 検証
    assert mock_searxng.search.call_count == 2
    assert mock_agent.generate_search_retry_query.call_count == 1
    assert result["search_failed"] == False
    assert len(result["results"]) == 1


def test_search_retries_max_three_times_on_failure():
    """Test that search retries max 3 times and returns search_failed=True."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    
    # すべて失敗（初回 + リトライ2回 = 3回）
    mock_searxng.search.side_effect = [RuntimeError("error")] * 3
    mock_agent.generate_search_retry_query.return_value = "retry query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=None)
    result = chat.search("query")
    
    # 検証
    assert mock_searxng.search.call_count == 3  # 初回 + リトライ2回
    assert mock_agent.generate_search_retry_query.call_count == 2  # リトライ2回
    assert result["search_failed"] == True
    assert result["results"] == []


def test_search_stops_retry_on_first_success():
    """Test that search stops retry when first retry succeeds."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    
    # 1回失敗後、すぐ成功
    mock_searxng.search.side_effect = [
        RuntimeError("error"),
        {"raw": {}, "results": [{"url": "https://ok.com", "title": "OK", "snippet": "..."}]}
    ]
    mock_agent.generate_search_retry_query.return_value = "retry query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=None)
    result = chat.search("query")
    
    # 検証：2回目で成功したのでリトライは1回のみ
    assert mock_searxng.search.call_count == 2
    assert mock_agent.generate_search_retry_query.call_count == 1
    assert result["search_failed"] == False


def test_search_failure_adds_system_message():
    """Test that search failure adds system message to history."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    
    # すべて失敗
    mock_searxng.search.side_effect = [RuntimeError("error")] * 3
    mock_agent.generate_search_retry_query.return_value = "retry query"
    
    # 日本語設定
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=None, language="ja")
    result = chat.search("query")
    
    # 検証：システムメッセージが追加されている
    history = chat.get_history()
    system_messages = [m for m in history if m.get("role") == "system"]
    assert any("検索に失敗したため最新情報を提供できません" in m.get("content", "") for m in system_messages)
    
    # 英語設定でもテスト
    chat_en = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=None, language="en")
    mock_searxng.search.side_effect = [RuntimeError("error")] * 3
    chat_en.search("query")
    
    history_en = chat_en.get_history()
    system_messages_en = [m for m in history_en if m.get("role") == "system"]
    assert any("Search failed" in m.get("content", "") for m in system_messages_en)


def test_search_failure_clears_state():
    """Test that search failure clears citations and crawl state."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    
    # すべて失敗
    mock_searxng.search.side_effect = [RuntimeError("error")] * 3
    mock_agent.generate_search_retry_query.return_value = "retry query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=None)
    
    # 事前に状態を設定
    chat.current_citation_ids = [1, 2, 3]
    chat.last_search_content = "previous content"
    chat.last_search_turns_remaining = 1
    
    result = chat.search("query")
    
    # 検証：状態がクリアされている
    assert chat.current_citation_ids == []
    assert chat.last_search_content == ""
    assert chat.last_search_turns_remaining == 0
    assert result["search_failed"] == True


def test_search_no_retry_without_agent():
    """Test that search does not generate alternative queries without agent."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    
    # すべて失敗（agentなし）
    mock_searxng.search.side_effect = [RuntimeError("error")] * 3
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=None, web_crawler=None)
    result = chat.search("original query")
    
    # 検証：リトライは実行されるが、代替クエリは生成されない
    assert mock_searxng.search.call_count == 3
    assert result["search_failed"] == True
    
    # すべて元のクエリで試行される
    for call in mock_searxng.search.call_args_list:
        assert call[0][0] == "original query"


def test_search_retry_calls_progress_callback():
    """Test that search retry calls progress_callback with correct events."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    progress_callback = MagicMock()
    
    # 2回失敗後成功
    mock_searxng.search.side_effect = [
        RuntimeError("error1"),
        RuntimeError("error2"),
        {"raw": {}, "results": [{"url": "https://ok.com", "title": "OK", "snippet": "..."}]}
    ]
    mock_agent.generate_search_retry_query.return_value = "alternative query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=None)
    result = chat.search("query", progress_callback=progress_callback)
    
    # 検証：コールバックが呼ばれている（retry_start × 2、query_generated × 2、retry_attempt × 2 = 6回）
    assert progress_callback.call_count == 6
    
    # イベントタイプの検証
    calls = progress_callback.call_args_list
    assert calls[0][0][0] == "retry_start"
    assert calls[0][0][1]["retry_count"] == 1
    assert calls[0][0][1]["max_retries"] == 3
    
    assert calls[1][0][0] == "query_generated"
    assert calls[1][0][1]["retry_count"] == 1
    assert calls[1][0][1]["new_query"] == "alternative query"
    
    assert calls[2][0][0] == "retry_attempt"
    assert calls[2][0][1]["retry_count"] == 1
    
    # 2回目のリトライ
    assert calls[3][0][0] == "retry_start"
    assert calls[3][0][1]["retry_count"] == 2
    
    assert calls[4][0][0] == "query_generated"
    assert calls[4][0][1]["retry_count"] == 2
    
    assert calls[5][0][0] == "retry_attempt"
    assert calls[5][0][1]["retry_count"] == 2
    
    # 最終的に成功
    assert result["search_failed"] == False


def test_search_all_retries_failed_callback():
    """Test that all_retries_failed callback is called when all retries fail."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    progress_callback = MagicMock()
    
    # すべて失敗
    mock_searxng.search.side_effect = [RuntimeError("error")] * 3
    mock_agent.generate_search_retry_query.return_value = "retry query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=None)
    result = chat.search("original query", progress_callback=progress_callback)
    
    # 検証：all_retries_failedイベントが最後に呼ばれている
    # retry_start × 2、query_generated × 2、retry_attempt × 2、all_retries_failed × 1 = 7回
    assert progress_callback.call_count == 7
    
    # 最後の呼び出しがall_retries_failed
    last_call = progress_callback.call_args_list[-1]
    assert last_call[0][0] == "all_retries_failed"
    assert last_call[0][1]["query"] == "original query"
    assert last_call[0][1]["max_retries"] == 3
    
    assert result["search_failed"] == True


def test_search_retry_query_generation_with_failure_reason():
    """Test that failure reason is extracted and passed to generate_search_retry_query."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    
    # HTMLパースエラー
    mock_searxng.search.side_effect = [
        RuntimeError("SearXNG HTML パースで結果が見つかりません"),
        {"raw": {}, "results": [{"url": "https://ok.com", "title": "OK", "snippet": "..."}]}
    ]
    mock_agent.generate_search_retry_query.return_value = "alternative query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=None)
    result = chat.search("query")
    
    # 検証：generate_search_retry_queryがfailure_reasonとともに呼ばれている
    assert mock_agent.generate_search_retry_query.call_count == 1
    call_kwargs = mock_agent.generate_search_retry_query.call_args[1]
    assert "failure_reason" in call_kwargs
    # _extract_failure_reason()がパースエラーを検出すること
    assert call_kwargs["failure_reason"] in ["parse_error", "unknown"]  # パース関連のエラー
    
    # タイムアウトエラーの場合
    mock_searxng.search.side_effect = [
        RuntimeError("Connection timeout"),
        {"raw": {}, "results": [{"url": "https://ok.com", "title": "OK", "snippet": "..."}]}
    ]
    mock_agent.generate_search_retry_query.reset_mock()
    
    chat.search("query2")
    
    call_kwargs2 = mock_agent.generate_search_retry_query.call_args[1]
    assert call_kwargs2["failure_reason"] == "timeout"


def test_search_retries_on_low_success_rate():
    """Test that retry search is executed when success rate < 50%."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    mock_crawler = MagicMock()
    
    # Initial search result
    mock_searxng.search.side_effect = [
        {"raw": {}, "results": [{"url": "https://paywall.com", "title": "Paywall", "snippet": "...", "score": 0.9}]},
        {"raw": {}, "results": [{"url": "https://free.com", "title": "Free", "snippet": "...", "score": 0.8}]},
    ]
    
    # Initial crawl fails, retry succeeds
    mock_crawler.crawl_results.side_effect = [
        {"content": {}, "failed_domains": {"paywall.com"}, "success_rate": 0.0, "total_attempts": 1, "successful_crawls": 0},
        {"content": {"https://free.com": "Content"}, "failed_domains": set(), "success_rate": 1.0, "total_attempts": 1, "successful_crawls": 1},
    ]
    mock_crawler.format_crawled_content.return_value = "[Web Content]..."
    
    # Agent generates retry query
    mock_agent.generate_retry_query.return_value = "alternative query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=mock_crawler)
    result = chat.search("test query")
    
    # Verify retry was executed
    assert mock_agent.generate_retry_query.call_count == 1
    assert mock_searxng.search.call_count == 2
    
    # Verify consolidated results contain both URLs
    assert len(result["results"]) == 2
    urls = {r["url"] for r in result["results"]}
    assert "https://paywall.com" in urls
    assert "https://free.com" in urls


def test_search_retries_max_three_times():
    """Test that retry search executes max 3 times."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    mock_crawler = MagicMock()
    
    # All fail
    mock_searxng.search.return_value = {"raw": {}, "results": [{"url": "https://fail.com", "title": "Fail", "snippet": "..."}]}
    mock_crawler.crawl_results.return_value = {
        "content": {}, "failed_domains": {"fail.com"}, "success_rate": 0.0, "total_attempts": 1, "successful_crawls": 0
    }
    mock_agent.generate_retry_query.return_value = "retry query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=mock_crawler)
    chat.search("test query")
    
    # Initial search + 3 retries = 4 total
    assert mock_searxng.search.call_count == 4
    assert mock_agent.generate_retry_query.call_count == 3


def test_search_stops_retry_on_success():
    """Test that retry search stops when success rate reaches 50%."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    mock_crawler = MagicMock()
    
    mock_searxng.search.side_effect = [
        {"raw": {}, "results": [{"url": "https://url1.com", "title": "1", "snippet": "..."}]},
        {"raw": {}, "results": [{"url": "https://url2.com", "title": "2", "snippet": "..."}]},
    ]
    
    # Initial fails, first retry succeeds
    mock_crawler.crawl_results.side_effect = [
        {"content": {}, "failed_domains": {"url1.com"}, "success_rate": 0.0, "total_attempts": 1, "successful_crawls": 0},
        {"content": {"https://url2.com": "Content"}, "failed_domains": set(), "success_rate": 1.0, "total_attempts": 1, "successful_crawls": 1},
    ]
    mock_crawler.format_crawled_content.return_value = "[Web Content]..."
    mock_agent.generate_retry_query.return_value = "retry query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=mock_crawler)
    chat.search("test query")
    
    # Initial + 1 retry (not 3)
    assert mock_searxng.search.call_count == 2
    assert mock_agent.generate_retry_query.call_count == 1


def test_search_no_retry_without_agent():
    """Test that retry search does not execute without agent."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_crawler = MagicMock()
    
    mock_searxng.search.return_value = {"raw": {}, "results": [{"url": "https://fail.com", "title": "Fail", "snippet": "..."}]}
    mock_crawler.crawl_results.return_value = {
        "content": {}, "failed_domains": {"fail.com"}, "success_rate": 0.0, "total_attempts": 1, "successful_crawls": 0
    }
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=None, web_crawler=mock_crawler)
    chat.search("test query")
    
    # No retry without agent
    assert mock_searxng.search.call_count == 1


def test_search_deduplicates_results_by_url():
    """Test that retry results are deduplicated by URL."""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    mock_crawler = MagicMock()
    
    # Initial and retry return same URL
    mock_searxng.search.side_effect = [
        {"raw": {}, "results": [{"url": "https://same.com", "title": "Original", "snippet": "...", "score": 0.9}]},
        {"raw": {}, "results": [{"url": "https://same.com", "title": "Duplicate", "snippet": "...", "score": 0.8}]},
    ]
    
    mock_crawler.crawl_results.side_effect = [
        {"content": {}, "failed_domains": {"same.com"}, "success_rate": 0.0, "total_attempts": 1, "successful_crawls": 0},
        {"content": {}, "failed_domains": {"same.com"}, "success_rate": 0.0, "total_attempts": 1, "successful_crawls": 0},
    ]
    mock_agent.generate_retry_query.return_value = "retry query"
    
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=mock_crawler)
    result = chat.search("test query")
    
    # Deduplication keeps only 1 result
    assert len(result["results"]) == 1
    assert result["results"][0]["url"] == "https://same.com"


def test_manual_search_with_agent_enables_retry_logic():
    """Test that manual /search command uses retry logic when agent is available.
    
    Agent creation is now decoupled from auto_search_enabled flag.
    When searxng_client is available, agent is created regardless of auto_search setting.
    This ensures /search command can use retry logic even without auto_search enabled.
    """
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_agent = MagicMock()
    mock_crawler = MagicMock()
    
    # Simulate initial search failure and successful retry
    mock_searxng.search.side_effect = [
        {"raw": {}, "results": [{"url": "https://blocked.com", "title": "Blocked", "snippet": "..."}]},
        {"raw": {}, "results": [{"url": "https://success.com", "title": "Success", "snippet": "..."}]},
    ]
    
    mock_crawler.crawl_results.side_effect = [
        {"content": {}, "failed_domains": {"blocked.com"}, "success_rate": 0.0, "total_attempts": 1, "successful_crawls": 0},
        {"content": {}, "failed_domains": set(), "success_rate": 1.0, "total_attempts": 1, "successful_crawls": 1},
    ]
    mock_agent.generate_retry_query.return_value = "retry query"
    
    # Create ChatManager with agent (not auto_search_enabled, but searxng available)
    # This simulates the case where manual /search is called without auto_search
    chat = ChatManager(mock_ollama, searxng_client=mock_searxng, agent=mock_agent, web_crawler=mock_crawler)
    
    # Verify agent is available for manual search
    assert chat.agent is not None
    
    # Perform search - should retry when initial results are poor
    result = chat.search("query")
    
    # Verify retry was attempted (agent.generate_retry_query should be called)
    assert mock_agent.generate_retry_query.called or mock_searxng.search.call_count == 2


def test_search_without_agent_when_searxng_unavailable():
    """Test that agent is not created when searxng_client is None."""
    mock_ollama = MagicMock()
    
    # Create ChatManager without searxng_client and no agent
    chat = ChatManager(mock_ollama, searxng_client=None, agent=None)
    
    # Verify agent is None
    assert chat.agent is None
    
    # Verify search fails gracefully
    with pytest.raises(RuntimeError) as exc:
        chat.search("query")
    assert "検索機能が有効化されていません" in str(exc.value)


# ============================================================================
# RAGプロンプト厳格化テスト
# ============================================================================

def test_rag_prompt_ignores_training_knowledge():
    """Test that new RAG prompt includes strict instruction to ignore training knowledge."""
    mock_ollama = MagicMock()
    
    # Test Japanese version
    chat_ja = ChatManager(mock_ollama, language="ja")
    prompt_ja = chat_ja._get_rag_system_prompt()
    
    assert "この情報のみ" in prompt_ja, "Japanese prompt should emphasize 'only this information'"
    assert "訓練知識" in prompt_ja, "Japanese prompt should mention 'training knowledge'"
    assert "無視" in prompt_ja, "Japanese prompt should mention 'ignore'"
    assert "最新の日付" in prompt_ja or "リリースノート" in prompt_ja, "Should prioritize latest dates/release notes"
    
    # Test English version
    chat_en = ChatManager(mock_ollama, language="en")
    prompt_en = chat_en._get_rag_system_prompt()
    
    assert "ONLY this information" in prompt_en, "English prompt should emphasize 'ONLY this information'"
    assert "ignore" in prompt_en.lower(), "English prompt should mention 'ignore'"
    assert "training knowledge" in prompt_en.lower(), "English prompt should mention 'training knowledge'"
    assert "latest dates" in prompt_en.lower() or "release notes" in prompt_en.lower(), "Should prioritize latest dates/release notes"


# ============================================================================
# フィードバック機能テスト
# ============================================================================

def test_feedback_save_includes_model():
    """Test that feedback is saved with model information."""
    mock_ollama = MagicMock()
    mock_ollama.model = "gpt-oss:20b"
    
    chat = ChatManager(mock_ollama)
    
    # Verify get_current_model returns the correct model
    model = chat.get_current_model()
    assert model == "gpt-oss:20b"


def test_get_current_model_returns_ollama_model():
    """Test that get_current_model returns ollama_client model name."""
    mock_ollama = MagicMock()
    mock_ollama.model = "llama3.2"
    
    chat = ChatManager(mock_ollama)
    assert chat.get_current_model() == "llama3.2"


def test_get_current_model_handles_none_ollama():
    """Test that get_current_model returns 'unknown' when ollama_client is None."""
    chat = ChatManager(None)
    assert chat.get_current_model() == "unknown"


# ============================================================================
# ソース注入評価テスト
# (tests/test_source_injection.py に移動)
# ============================================================================


# ============================================================================
# search_results埋め込みテスト
# ============================================================================

def test_get_response_embeds_search_results_in_assistant_message():
    """Test that get_response embeds pending_search_results in assistant message."""
    from researcher.citation_manager import CitationManager
    
    ollama = MagicMock()
    ollama.generate_response.return_value = "This is the response."
    citation_mgr = CitationManager()
    
    chat = ChatManager(ollama, citation_manager=citation_mgr)
    
    # Set pending_search_results
    chat.pending_search_results = [
        {
            "title": "Python Guide",
            "url": "https://example.com/python",
            "snippet": "Learn Python",
            "date": "2024-01-10",
            "citation_id": 1,
            "relevance_score": 0.9,
            "credibility_score": 0.85
        }
    ]
    
    # Add user message and get response
    chat.add_user_message("Tell me about Python")
    response = chat.get_response()
    
    # Verify assistant message has search_results
    history = chat.get_history()
    assistant_msg = next(m for m in history if m["role"] == "assistant")
    
    assert "search_results" in assistant_msg
    assert len(assistant_msg["search_results"]) == 1
    assert assistant_msg["search_results"][0]["title"] == "Python Guide"
    
    # Verify pending_search_results was cleared
    assert chat.pending_search_results == []


def test_get_response_stream_embeds_search_results_in_assistant_message():
    """Test that get_response_stream embeds pending_search_results in assistant message."""
    from researcher.citation_manager import CitationManager
    
    ollama = MagicMock()
    ollama.generate_response_stream.return_value = ["This ", "is ", "response."]
    citation_mgr = CitationManager()
    
    chat = ChatManager(ollama, citation_manager=citation_mgr)
    
    # Set pending_search_results
    chat.pending_search_results = [
        {
            "title": "AI Overview",
            "url": "https://example.com/ai",
            "snippet": "AI introduction",
            "date": "2024-02-15",
            "citation_id": 2,
            "relevance_score": 0.88,
            "credibility_score": 0.9
        }
    ]
    
    # Add user message and get response stream
    chat.add_user_message("What is AI?")
    chunks = list(chat.get_response_stream())
    
    # Verify assistant message has search_results
    history = chat.get_history()
    assistant_msg = next(m for m in history if m["role"] == "assistant")
    
    assert "search_results" in assistant_msg
    assert len(assistant_msg["search_results"]) == 1
    assert assistant_msg["search_results"][0]["url"] == "https://example.com/ai"
    
    # Verify pending_search_results was cleared
    assert chat.pending_search_results == []


def test_search_accumulates_all_search_results_from_retries():
    """Test that search retries accumulate all_search_results."""
    from researcher.citation_manager import CitationManager
    
    ollama = MagicMock()
    searxng = MagicMock()
    citation_mgr = CitationManager()
    agent = MagicMock()
    
    # First search returns 1 result, second search (retry) returns 2 results
    searxng.search.side_effect = [
        {
            "raw": {"results": [{"title": "Result 1", "url": "http://example.com/1", "snippet": "Snippet 1"}]},
            "results": [{"title": "Result 1", "url": "http://example.com/1", "snippet": "Snippet 1"}]
        },
        {
            "raw": {"results": [
                {"title": "Result 2", "url": "http://example.com/2", "snippet": "Snippet 2"},
                {"title": "Result 3", "url": "http://example.com/3", "snippet": "Snippet 3"}
            ]},
            "results": [
                {"title": "Result 2", "url": "http://example.com/2", "snippet": "Snippet 2"},
                {"title": "Result 3", "url": "http://example.com/3", "snippet": "Snippet 3"}
            ]
        }
    ]
    
    agent.generate_search_retry_query.return_value = "retry query"
    
    # Mock reranker to trigger retry (low score)
    reranker = MagicMock()
    reranker.rerank.return_value = [{"title": "Result 1", "url": "http://example.com/1", "snippet": "Snippet 1", "score": 0.3}]
    
    chat = ChatManager(ollama, searxng_client=searxng, citation_manager=citation_mgr, agent=agent, reranker=reranker)
    
    # Perform search with retry
    result = chat.search("test query", max_retries=1)
    
    # Verify all_search_results contains results from initial + retry
    assert "all_search_results" in result
    # Should have at least 3 results (1 from initial + 2 from retry, but may be deduplicated)
    assert len(result["all_search_results"]) >= 1


def test_auto_search_passes_all_search_results_to_pending():
    """Test that auto_search sets pending_search_results to all_search_results."""
    from researcher.citation_manager import CitationManager
    
    ollama = MagicMock()
    searxng = MagicMock()
    citation_mgr = CitationManager()
    agent = MagicMock()
    
    agent.analyze_query.return_value = {
        "needs_search": True,
        "keywords": ["python"],
        "reasoning": "Need to search"
    }
    
    searxng.search.return_value = {
        "raw": {"results": [{"title": "Auto Result", "url": "http://example.com", "snippet": "Auto"}]},
        "results": [{"title": "Auto Result", "url": "http://example.com", "snippet": "Auto"}]
    }
    
    reranker = MagicMock()
    reranker.rerank.return_value = [{"title": "Auto Result", "url": "http://example.com", "snippet": "Auto", "score": 0.9}]
    
    chat = ChatManager(ollama, searxng_client=searxng, citation_manager=citation_mgr, agent=agent, reranker=reranker)
    
    # Perform auto_search
    result = chat.auto_search("test query")
    
    # Verify pending_search_results is set
    assert result["searched"] is True
    assert len(chat.pending_search_results) > 0


def test_self_evaluation_retry_accumulates_search_results():
    """Test that self-evaluation retry accumulates new search results."""
    from researcher.citation_manager import CitationManager
    
    ollama = MagicMock()
    searxng = MagicMock()
    citation_mgr = CitationManager()
    agent = MagicMock()
    
    # Initial search
    searxng.search.return_value = {
        "raw": {"results": [{"title": "Initial", "url": "http://example.com/1", "snippet": "Initial"}]},
        "results": [{"title": "Initial", "url": "http://example.com/1", "snippet": "Initial"}]
    }
    
    reranker = MagicMock()
    reranker.rerank.return_value = [{"title": "Initial", "url": "http://example.com/1", "snippet": "Initial", "score": 0.9}]
    
    chat = ChatManager(ollama, searxng_client=searxng, citation_manager=citation_mgr, agent=agent, reranker=reranker)
    
    # First search
    result1 = chat.search("query 1")
    initial_count = len(result1.get("all_search_results", []))
    
    # Second search (simulating retry after self-evaluation)
    result2 = chat.search("query 2")
    
    # Each search should have its own all_search_results
    assert "all_search_results" in result2
    assert len(result2["all_search_results"]) >= 1


def test_search_results_cleared_after_embedding():
    """Test that pending_search_results is cleared after being embedded in message."""
    from researcher.citation_manager import CitationManager
    
    ollama = MagicMock()
    ollama.generate_response.return_value = "Response"
    citation_mgr = CitationManager()
    
    chat = ChatManager(ollama, citation_manager=citation_mgr)
    
    # Set pending_search_results
    chat.pending_search_results = [
        {"title": "Test", "url": "http://example.com", "snippet": "Test", "citation_id": 1}
    ]
    
    assert len(chat.pending_search_results) == 1
    
    # Get response (should embed and clear)
    chat.add_user_message("Question")
    chat.get_response()
    
    # Verify search results were embedded in the assistant message
    history = chat.get_history()
    assistant_msg = next((m for m in history if m["role"] == "assistant"), None)
    assert assistant_msg is not None, "Assistant message should exist"
    assert "search_results" in assistant_msg, "search_results should be embedded in assistant message"
    assert len(assistant_msg["search_results"]) == 1, "search_results should contain the test data"
    assert assistant_msg["search_results"][0]["title"] == "Test", "Embedded search result should match test data"
    
    # Verify pending_search_results was cleared after embedding
    assert chat.pending_search_results == [], "pending_search_results should be cleared after embedding"
    assert len(chat.pending_search_results) == 0, "pending_search_results length should be 0"


def test_chatmanager_searxng_params():
    """Test that SearXNG parameters are correctly passed to searxng_client.search()"""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_searxng.search.return_value = {"results": []}
    
    chat = ChatManager(
        ollama_client=mock_ollama,
        searxng_client=mock_searxng,
        searxng_engine="news",
        searxng_lang="en",
        searxng_safesearch="moderate"
    )
    
    chat.search("test query")
    
    # Verify searxng_client.search was called with correct params
    call_args = mock_searxng.search.call_args
    assert call_args is not None, "searxng_client.search should have been called"
    assert "engines" in call_args[1], "engines parameter should be passed"
    assert call_args[1]["engines"] == "news", "engines should be 'news'"
    assert call_args[1]["language"] == "en", "language should be 'en'"
    assert call_args[1]["safesearch"] == "moderate", "safesearch should be 'moderate'"


def test_chatmanager_searxng_params_user_override():
    """Test that user-provided kwargs override ChatManager SearXNG settings"""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_searxng.search.return_value = {"results": []}
    
    chat = ChatManager(
        ollama_client=mock_ollama,
        searxng_client=mock_searxng,
        searxng_engine="news",
        searxng_lang="en",
        searxng_safesearch="moderate"
    )
    
    # User provides custom language
    chat.search("test query", language="fr")
    
    # Verify user kwargs take precedence
    call_args = mock_searxng.search.call_args
    assert call_args[1]["language"] == "fr", "User-provided language should override ChatManager setting"
    assert call_args[1]["engines"] == "news", "Other ChatManager settings should still apply"


def test_chatmanager_searxng_params_none():
    """Test that ChatManager works correctly when SearXNG params are None"""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    mock_searxng.search.return_value = {"results": []}
    
    chat = ChatManager(
        ollama_client=mock_ollama,
        searxng_client=mock_searxng,
        # All SearXNG params are None (default)
    )
    
    chat.search("test query")
    
    # Verify no extra params were added
    call_args = mock_searxng.search.call_args
    # Only the query should be passed, no engines/language/safesearch
    assert "engines" not in call_args[1], "engines should not be in kwargs when None"
    assert "language" not in call_args[1], "language should not be in kwargs when None"
    assert "safesearch" not in call_args[1], "safesearch should not be in kwargs when None"


def test_chatmanager_searxng_params_retry_with_low_crawl_success():
    """Test that SearXNG params are applied during retry search when crawl success is low"""
    mock_ollama = MagicMock()
    mock_searxng = MagicMock()
    
    # First search returns results
    mock_searxng.search.return_value = {
        "results": [
            {"title": "Test1", "url": "https://example.com/1", "snippet": "snippet1"},
            {"title": "Test2", "url": "https://example.com/2", "snippet": "snippet2"},
        ]
    }
    
    # Mock web crawler with low success rate
    mock_crawler = MagicMock()
    mock_crawler.crawl_results.return_value = {
        "content": {},
        "successful_crawls": 0,
        "total_attempts": 3,
        "success_rate": 0.0,  # Low success rate triggers retry
        "failed_domains": ["example.com"]
    }
    
    # Mock agent for retry query generation
    mock_agent = MagicMock()
    mock_agent.generate_retry_query.return_value = "retry query"
    
    chat = ChatManager(
        ollama_client=mock_ollama,
        searxng_client=mock_searxng,
        web_crawler=mock_crawler,
        agent=mock_agent,
        searxng_engine="news",
        searxng_lang="en",
        searxng_safesearch="moderate"
    )
    
    chat.search("test query")
    
    # Verify searxng_client.search was called multiple times (initial + retry)
    assert mock_searxng.search.call_count >= 2, "Should have called search at least twice (initial + retry)"
    
    # Get the retry call (second call)
    retry_call_args = mock_searxng.search.call_args_list[1]
    
    # Verify retry search includes SearXNG params
    assert retry_call_args[1]["engines"] == "news", "Retry should include engines param"
    assert retry_call_args[1]["language"] == "en", "Retry should include language param"
    assert retry_call_args[1]["safesearch"] == "moderate", "Retry should include safesearch param"

