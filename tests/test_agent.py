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


# ============================================================================
# Agent強化テスト: 企業製品検索対応
# ============================================================================

def test_agent_detects_enterprise_product_queries():
    """Test that Agent SYSTEM_PROMPT includes enterprise product detection."""
    # Test Japanese version
    assert "企業製品" in QueryAgent.SYSTEM_PROMPT_JA or "製品の最新版" in QueryAgent.SYSTEM_PROMPT_JA, \
        "Japanese prompt should mention enterprise products"
    assert "公式ドキュメント" in QueryAgent.SYSTEM_PROMPT_JA, \
        "Japanese prompt should prioritize official documentation"
    
    # Test English version
    assert "enterprise products" in QueryAgent.SYSTEM_PROMPT_EN.lower() or "product" in QueryAgent.SYSTEM_PROMPT_EN.lower(), \
        "English prompt should mention enterprise products"
    assert "official documentation" in QueryAgent.SYSTEM_PROMPT_EN.lower(), \
        "English prompt should prioritize official documentation"


def test_retry_query_prioritizes_official_docs():
    """Test that generate_retry_query prioritizes official documentation."""
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.generate_response.return_value = "TIBCO EBX official documentation latest release"
    
    # Test Japanese version
    agent_ja = QueryAgent(mock_ollama, language="ja")
    agent_ja.generate_retry_query("TIBCO EBX information", {"example.com"}, ["TIBCO"])
    
    # Check that the prompt includes official docs priority
    call_args_ja = mock_ollama.generate_response.call_args_list[0][0][0][0]["content"]
    assert "公式ドキュメント" in call_args_ja, \
        "Japanese retry prompt should mention official documentation"
    
    # Test English version
    mock_ollama.reset_mock()
    mock_ollama.generate_response.return_value = "TIBCO EBX official documentation latest release"
    agent_en = QueryAgent(mock_ollama, language="en")
    agent_en.generate_retry_query("TIBCO EBX information", {"example.com"}, ["TIBCO"])
    
    call_args_en = mock_ollama.generate_response.call_args_list[0][0][0][0]["content"]
    assert "official documentation" in call_args_en.lower() or "official" in call_args_en.lower(), \
        "English retry prompt should mention official documentation"


def test_generate_retry_query_success():
    """Test that retry query generation succeeds with proper input."""
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate_response.return_value = "alternative search terms for Python"
    
    agent = QueryAgent(mock_client, language="ja")
    retry_query = agent.generate_retry_query(
        "original python query",
        {"paywall.com", "blocked.com"},
        ["keyword1", "keyword2"]
    )
    
    assert retry_query == "alternative search terms for Python"
    assert mock_client.generate_response.called


def test_generate_retry_query_fallback_on_error():
    """Test that original query is returned on generation failure."""
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate_response.side_effect = Exception("LLM error")
    
    agent = QueryAgent(mock_client, language="ja")
    retry_query = agent.generate_retry_query("original query", {"fail.com"}, [])
    
    assert retry_query == "original query"


def test_generate_retry_query_strips_whitespace():
    """Test that generated query is stripped of whitespace."""
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate_response.return_value = "  alternative query  \n"
    
    agent = QueryAgent(mock_client, language="en")
    retry_query = agent.generate_retry_query("original", {"fail.com"}, [])
    
    assert retry_query == "alternative query"


def test_generate_retry_query_empty_response():
    """Test that original query is returned when response is empty."""
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate_response.return_value = "  \n  "
    
    agent = QueryAgent(mock_client, language="ja")
    retry_query = agent.generate_retry_query("original query", {"fail.com"}, [])
    
    assert retry_query == "original query"


def test_system_prompt_contains_enterprise_product_keywords():
    """Validate SYSTEM_PROMPT contains enterprise product detection and official docs priority keywords."""
    mock_client = MagicMock(spec=OllamaClient)
    agent = QueryAgent(mock_client)
    
    # Check Japanese SYSTEM_PROMPT
    assert "企業製品" in agent.SYSTEM_PROMPT_JA, \
        "SYSTEM_PROMPT_JA should mention enterprise products"
    assert any(phrase in agent.SYSTEM_PROMPT_JA for phrase in ["最新版", "リリースノート", "公式ドキュメント"]), \
        "SYSTEM_PROMPT_JA should contain latest version and release notes keywords"
    
    # Check English SYSTEM_PROMPT
    assert any(phrase in agent.SYSTEM_PROMPT_EN.lower() for phrase in ["enterprise products", "release notes"]), \
        "SYSTEM_PROMPT_EN should mention enterprise products or release notes"
    assert "official documentation" in agent.SYSTEM_PROMPT_EN.lower(), \
        "SYSTEM_PROMPT_EN should mention official documentation priority"


def test_retry_query_prompt_prioritizes_official_documentation():
    """Validate that retry query generation prioritizes official docs and product sites."""
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate_response.return_value = "refined search query"
    
    agent = QueryAgent(mock_client, language="ja")
    agent.generate_retry_query("original query", {"fail.com"}, [])
    
    # Extract the prompt from mock call arguments
    call_args = mock_client.generate_response.call_args[0][0]
    messages = call_args if isinstance(call_args, list) else call_args
    
    # Find system message with retry instructions
    system_messages = [m for m in messages if m.get("role") == "system"]
    retry_prompt = " ".join(m.get("content", "") for m in system_messages)
    
    # Check Japanese priority keywords
    assert any(phrase in retry_prompt for phrase in ["公式ドキュメント", "製品サイト", "リリースノート"]), \
        "Retry query prompt should prioritize official documentation, product sites, and release notes in Japanese"


def test_retry_query_prompt_english_official_documentation():
    """Validate English retry query prompt prioritizes official documentation."""
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.generate_response.return_value = "refined search query"
    
    agent = QueryAgent(mock_client, language="en")
    agent.generate_retry_query("original query", {"fail.com"}, [])
    
    # Extract the prompt from mock call arguments
    call_args = mock_client.generate_response.call_args[0][0]
    messages = call_args if isinstance(call_args, list) else call_args
    
    # Find system message with retry instructions
    system_messages = [m for m in messages if m.get("role") == "system"]
    retry_prompt = " ".join(m.get("content", "") for m in system_messages)
    
    # Check English priority keywords
    assert any(phrase in retry_prompt.lower() for phrase in ["official documentation", "product sites", "release notes"]), \
        "Retry query prompt should prioritize official documentation in English"


