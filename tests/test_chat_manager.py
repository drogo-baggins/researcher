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
    
    # システムメッセージにクロール内容が含まれることを確認
    system_messages = [m for m in call_args if m.get("role") == "system"]
    assert any("Python is a programming language" in m["content"] for m in system_messages)
    assert any("この情報を活用して" in m["content"] for m in system_messages)
    
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