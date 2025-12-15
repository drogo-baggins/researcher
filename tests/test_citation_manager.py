from datetime import datetime, timedelta

import pytest

from researcher.citation_manager import CitationManager


def test_add_citation_storage():
    manager = CitationManager()
    cid = manager.add_citation(
        "https://docs.python.org", "Python Docs", "Official", "2024-01-01", 0.7
    )
    citation = manager.get_citation(cid)
    assert citation["title"] == "Python Docs"
    assert citation["credibility_score"] > 0


def test_domain_score_trusted():
    manager = CitationManager()
    score = manager._get_domain_score("https://mit.edu/article")
    assert score == 1.0


def test_domain_score_major_news():
    manager = CitationManager()
    score = manager._get_domain_score("https://www.bbc.com/news")
    assert score == 0.8


def test_domain_score_precise_matching():
    manager = CitationManager()
    assert manager._get_domain_score("https://notgov.com/page") == 0.5
    assert manager._get_domain_score("https://news.nytimes.com/2024") == 0.8


def test_domain_score_neutral():
    manager = CitationManager()
    score = manager._get_domain_score("https://example.com")
    assert score == 0.5


def test_freshness_recent():
    manager = CitationManager()
    recent = datetime.now() - timedelta(days=10)
    assert manager._get_freshness_score(recent) == 1.0


def test_freshness_old():
    manager = CitationManager()
    old_date = datetime.now() - timedelta(days=1500)
    assert manager._get_freshness_score(old_date) == 0.4


def test_format_markdown_unknown_id():
    manager = CitationManager()
    assert manager.format_citation_markdown(99) == ""


def test_format_markdown_content():
    manager = CitationManager()
    cid = manager.add_citation(
        "https://example.com", "Example", "Snippet", "2024-01-01", 0.4
    )
    markdown = manager.format_citation_markdown(cid)
    assert markdown.startswith(f"[{cid}]")


def test_clear_citations():
    manager = CitationManager()
    manager.add_citation("https://example.com", "Example", "Snippet", "2024-01-01", 0.4)
    manager.clear_citations()
    assert manager.get_all_citations() == []


def test_blacklist_prevents_domain_score():
    manager = CitationManager()
    manager.blacklist.add("spam.com")
    assert manager._get_domain_score("https://spam.com/offers") == 0.0
    assert manager._get_domain_score("https://bad.spam.com/more") == 0.0


def test_calculate_credibility_score_weights():
    manager = CitationManager()
    pub_date = datetime.now() - timedelta(days=30)
    # neutral domain -> 0.5, freshness -> 1.0, relevance -> 0.6
    expected = (0.5 * 0.4) + (1.0 * 0.3) + (0.6 * 0.3)
    score = manager.calculate_credibility_score("https://example.com", pub_date, 0.6)
    assert abs(score - expected) < 1e-6


def test_integration_full_citation_flow():
    """
    End-to-end citation flow: add multiple citations, format to markdown,
    verify correct structure and credibility score calculations.
    """
    manager = CitationManager()
    
    # Add multiple citations with varying credibility
    pub_date_recent = datetime.now() - timedelta(days=1)
    pub_date_old = datetime.now() - timedelta(days=365)
    
    cid1 = manager.add_citation(
        url="https://arxiv.org/papers/2024001",
        title="Research Paper 2024",
        snippet="Recent advances in AI",
        date_str=pub_date_recent.isoformat(),
        relevance_score=0.95
    )
    
    cid2 = manager.add_citation(
        url="https://example.com/old-article",
        title="Old Article",
        snippet="Historical information",
        date_str=pub_date_old.isoformat(),
        relevance_score=0.6
    )
    
    cid3 = manager.add_citation(
        url="https://github.com/project/repo",
        title="GitHub Repository",
        snippet="Source code",
        date_str=pub_date_recent.isoformat(),
        relevance_score=0.8
    )
    
    # Verify citations are stored with correct IDs
    assert cid1 in [1, 2, 3]
    assert cid2 in [1, 2, 3]
    assert cid3 in [1, 2, 3]
    assert cid1 != cid2 != cid3
    
    # Verify credibility scores were calculated (use get_citation to avoid index dependency)
    citation1 = manager.get_citation(cid1)
    citation2 = manager.get_citation(cid2)
    citation3 = manager.get_citation(cid3)
    
    assert citation1["credibility_score"] is not None
    assert citation2["credibility_score"] is not None
    assert citation3["credibility_score"] is not None
    assert 0.0 <= citation1["credibility_score"] <= 1.0
    assert 0.0 <= citation2["credibility_score"] <= 1.0
    assert 0.0 <= citation3["credibility_score"] <= 1.0
    
    # Verify markdown formatting for each citation explicitly
    markdown1 = manager.format_citation_markdown(cid1)
    markdown2 = manager.format_citation_markdown(cid2)
    markdown3 = manager.format_citation_markdown(cid3)
    
    # Verify each markdown contains title, URL, and credibility pattern
    assert "Research Paper 2024" in markdown1
    assert "https://arxiv.org/papers/2024001" in markdown1
    assert "(信頼性:" in markdown1
    
    assert "Old Article" in markdown2
    assert "https://example.com/old-article" in markdown2
    assert "(信頼性:" in markdown2
    
    assert "GitHub Repository" in markdown3
    assert "https://github.com/project/repo" in markdown3
    assert "(信頼性:" in markdown3
    
    # Verify higher credibility for recent/relevant articles
    score1 = citation1["credibility_score"]
    score2 = citation2["credibility_score"]
    
    # Recent paper should have higher score than old article
    assert score1 > score2
    
    # Verify clear operation
    manager.clear_citations()
    assert manager.get_all_citations() == []
    assert manager.format_citation_markdown(cid1) == ""