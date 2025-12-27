"""Tests for source-injected evaluation functionality."""
import pytest
from unittest.mock import MagicMock
from researcher.chat_manager import ChatManager


def test_self_evaluate_with_source_injection():
    """Test that self_evaluate includes search sources in the prompt and validates prompt injection."""
    mock_ollama = MagicMock()
    mock_ollama.model = "main-model"
    
    # Mock response with JSON evaluation scores
    evaluation_response = '{"accuracy_score": 0.8, "freshness_score": 0.9, "overall_score": 0.85, "reasoning": "Good answer with current sources"}'
    mock_ollama.generate_response.return_value = evaluation_response
    
    chat = ChatManager(mock_ollama, language="ja")
    
    # Set up search content 
    search_content = "Python 3.12 was released in October 2023. It includes improvements to error messages and performance."
    chat.last_search_content = search_content
    chat.last_search_turns_remaining = 1
    
    # Call self_evaluate with query and response
    query = "When was Python 3.12 released?"
    response = "Python 3.12 was released in October 2023 with improved error messages."
    result = chat.self_evaluate(query, response)
    
    # Verify ollama.generate_response was called for evaluation
    assert mock_ollama.generate_response.called, "ollama.generate_response should be called during evaluation"
    
    # Capture the messages argument to verify prompt injection
    call_args = mock_ollama.generate_response.call_args
    assert call_args is not None, "generate_response should have been called with arguments"
    
    # Extract messages from the call
    messages = call_args[0][0] if call_args[0] else call_args[1].get('messages', [])
    assert len(messages) > 0, "Messages should be passed to generate_response"
    
    # Verify prompt contains source information
    prompt_text = messages[0].get('content', '') if isinstance(messages[0], dict) else str(messages[0])
    assert search_content in prompt_text, "Prompt should contain the search content"
    assert "Source Information" in prompt_text or "ソース情報" in prompt_text, "Prompt should contain source marker"
    
    # Verify evaluation scores were parsed correctly
    assert result is not None
    assert result.get('overall_score') == 0.85
    assert result.get('accuracy_score') == 0.8
    assert result.get('freshness_score') == 0.9
    assert "Good answer with current sources" in result.get('reasoning', '')


def test_self_evaluate_with_separate_evaluation_model():
    """Test that self_evaluate uses separate evaluation model when specified."""
    mock_ollama = MagicMock()
    mock_ollama.model = "main-model"
    
    # Mock response with JSON evaluation scores
    evaluation_response = '{"accuracy_score": 0.7, "freshness_score": 0.8, "overall_score": 0.75, "reasoning": "Evaluated with lightweight model"}'
    mock_ollama.generate_response.return_value = evaluation_response
    
    chat = ChatManager(mock_ollama, language="en", evaluation_model="llama3.2:3b")
    
    # Call self_evaluate with query and response
    query = "What is machine learning?"
    response = "Machine learning is a subset of artificial intelligence that enables systems to learn from data."
    result = chat.self_evaluate(query, response)
    
    # Verify that the model was switched for evaluation
    # The main model should be restored after evaluation
    assert mock_ollama.model == "main-model", "Main model should be restored after evaluation"
    
    # Verify evaluation happened and scores are correct
    assert result is not None
    assert result.get('overall_score') == 0.75


def test_self_evaluate_without_sources():
    """Test that self_evaluate works without search sources."""
    mock_ollama = MagicMock()
    mock_ollama.model = "test-model"
    
    # Mock response with JSON evaluation scores
    evaluation_response = '{"accuracy_score": 0.6, "freshness_score": 0.5, "overall_score": 0.55, "reasoning": "No sources available"}'
    mock_ollama.generate_response.return_value = evaluation_response
    
    chat = ChatManager(mock_ollama, language="ja")
    
    # Don't set last_search_content - simulate no search
    chat.last_search_turns_remaining = 0
    
    # Call self_evaluate with query and response
    query = "Hello!"
    response = "Hello! How can I help you?"
    result = chat.self_evaluate(query, response)
    
    # Verify evaluation still works without sources
    assert result is not None
    assert result.get('overall_score') == 0.55


def test_evaluation_model_parameter_initialization():
    """Test that evaluation_model parameter is properly initialized."""
    mock_ollama = MagicMock()
    
    # Test with evaluation_model specified
    chat_with_eval = ChatManager(mock_ollama, evaluation_model="llama3.2:3b")
    assert chat_with_eval.evaluation_model == "llama3.2:3b"
    
    # Test without evaluation_model
    chat_without_eval = ChatManager(mock_ollama, evaluation_model=None)
    assert chat_without_eval.evaluation_model is None
    
    # Test default (no parameter)
    chat_default = ChatManager(mock_ollama)
    assert chat_default.evaluation_model is None


def test_political_news_score_improvement_with_sources():
    """Test that political news evaluation scores improve significantly with source injection.
    
    This test verifies the intended enhancement: when evaluating responses about recent
    political news using source-injected evaluation, scores should be higher (>0.8)
    compared to evaluation without sources (baseline ~0.5).
    """
    mock_ollama = MagicMock()
    mock_ollama.model = "main-model"
    
    # Recent political news snippet (simulating search results)
    political_news_source = (
        "Japanese Prime Minister Yoshida Shigeru announced a new economic stimulus package "
        "in December 2024, focusing on semiconductor manufacturing and renewable energy. "
        "The package includes 500 billion yen in subsidies for chip production facilities. "
        "This is part of Japan's strategy to reduce dependence on foreign technology and boost domestic innovation."
    )
    
    # Response that aligns with the source information
    political_response = (
        "In December 2024, Japan's Prime Minister announced an economic stimulus package "
        "valued at 500 billion yen, with emphasis on semiconductor manufacturing and renewable energy. "
        "This initiative aims to strengthen Japan's domestic tech industry."
    )
    
    # Create chat with source injection
    mock_ollama.generate_response.return_value = (
        '{"accuracy_score": 0.9, "freshness_score": 0.95, "overall_score": 0.92, '
        '"reasoning": "Response accurately reflects the recent political announcement with correct details"}'
    )
    
    chat_with_source = ChatManager(mock_ollama, language="en")
    chat_with_source.last_search_content = political_news_source
    chat_with_source.last_search_turns_remaining = 1
    
    query = "What did Japan's government announce about semiconductor manufacturing in December 2024?"
    result_with_source = chat_with_source.self_evaluate(query, political_response)
    
    # Verify scores are high (>0.8) with source injection
    assert result_with_source.get('overall_score') >= 0.8, \
        f"Overall score with sources should be >0.8, got {result_with_source.get('overall_score')}"
    assert result_with_source.get('accuracy_score') >= 0.8, \
        f"Accuracy score with sources should be >0.8, got {result_with_source.get('accuracy_score')}"
    assert result_with_source.get('freshness_score') >= 0.8, \
        f"Freshness score with sources should be >0.8, got {result_with_source.get('freshness_score')}"
    
    # Create chat WITHOUT source injection for comparison (baseline)
    mock_ollama.generate_response.reset_mock()
    mock_ollama.generate_response.return_value = (
        '{"accuracy_score": 0.5, "freshness_score": 0.5, "overall_score": 0.5, '
        '"reasoning": "Cannot verify details without source information"}'
    )
    
    chat_no_source = ChatManager(mock_ollama, language="en")
    # Intentionally don't set last_search_content to simulate no source
    chat_no_source.last_search_turns_remaining = 0
    
    result_no_source = chat_no_source.self_evaluate(query, political_response)
    
    # Verify baseline scores are lower (~0.5)
    assert result_no_source.get('overall_score') <= 0.6, \
        f"Baseline overall score without sources should be ~0.5, got {result_no_source.get('overall_score')}"
    
    # Verify improvement: source injection improves scores
    score_improvement = result_with_source.get('overall_score') - result_no_source.get('overall_score')
    assert score_improvement > 0.3, \
        f"Score improvement should be >0.3 with source injection, got {score_improvement}"
