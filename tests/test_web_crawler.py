import pytest
from unittest.mock import MagicMock, patch
from researcher.web_crawler import WebCrawler


class TestWebCrawler:
    """Test WebCrawler functionality."""
    
    def test_crawl_results_returns_dict(self):
        """Test that crawl_results returns a dictionary."""
        crawler = WebCrawler()
        results = [
            {"url": "https://example.com", "title": "Example"},
            {"url": "https://example.org", "title": "Example Org"},
        ]
        
        with patch.object(crawler, "crawl_url") as mock_crawl:
            mock_crawl.side_effect = ["Content 1", "Content 2"]
            crawled = crawler.crawl_results(results, max_urls=2)
        
        assert isinstance(crawled, dict)
        assert len(crawled) == 2
        assert crawled["https://example.com"] == "Content 1"
        assert crawled["https://example.org"] == "Content 2"
    
    def test_crawl_results_respects_max_urls(self):
        """Test that crawl_results respects max_urls parameter."""
        crawler = WebCrawler()
        results = [
            {"url": "https://example.com", "title": "Example 1"},
            {"url": "https://example.org", "title": "Example 2"},
            {"url": "https://example.net", "title": "Example 3"},
        ]
        
        with patch.object(crawler, "crawl_url") as mock_crawl:
            mock_crawl.side_effect = ["Content 1", "Content 2"]
            crawled = crawler.crawl_results(results, max_urls=2)
        
        assert len(crawled) == 2
        assert mock_crawl.call_count == 2
    
    def test_crawl_results_handles_failed_crawl(self):
        """Test that crawl_results handles failed URL crawls gracefully."""
        crawler = WebCrawler()
        results = [
            {"url": "https://example.com", "title": "Example 1"},
            {"url": "https://example.org", "title": "Example 2"},
        ]
        
        with patch.object(crawler, "crawl_url") as mock_crawl:
            mock_crawl.side_effect = ["Content 1", None]  # Second crawl fails
            crawled = crawler.crawl_results(results, max_urls=2)
        
        assert len(crawled) == 1
        assert crawled["https://example.com"] == "Content 1"
    
    def test_format_crawled_content(self):
        """Test that format_crawled_content returns properly formatted string."""
        crawler = WebCrawler()
        crawled_content = {
            "https://example.com": "Example content 1",
            "https://example.org": "Example content 2",
        }
        
        formatted = crawler.format_crawled_content(crawled_content)
        
        assert isinstance(formatted, str)
        assert "[Web Content from Search Results]" in formatted
        assert "https://example.com:" in formatted
        assert "Example content 1" in formatted
        assert "https://example.org:" in formatted
        assert "Example content 2" in formatted
    
    def test_format_crawled_content_empty(self):
        """Test that format_crawled_content returns empty string for empty dict."""
        crawler = WebCrawler()
        formatted = crawler.format_crawled_content({})
        assert formatted == ""
    
    @patch("researcher.web_crawler.requests.get")
    def test_crawl_url_success(self, mock_get):
        """Test successful URL crawl."""
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Test content</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        crawler = WebCrawler()
        content = crawler.crawl_url("https://example.com")
        
        assert content is not None
        assert "Test content" in content
    
    @patch("researcher.web_crawler.requests.get")
    def test_crawl_url_failure(self, mock_get):
        """Test failed URL crawl returns None."""
        mock_get.side_effect = Exception("Connection error")
        
        crawler = WebCrawler()
        content = crawler.crawl_url("https://example.com")
        
        assert content is None
    
    @patch("researcher.web_crawler.requests.get")
    def test_crawl_url_removes_scripts_and_styles(self, mock_get):
        """Test that crawl_url removes script and style tags."""
        mock_response = MagicMock()
        mock_response.text = """
            <html>
            <head><style>body { color: red; }</style></head>
            <body>
            <p>Main content</p>
            <script>alert('test');</script>
            </body>
            </html>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        crawler = WebCrawler()
        content = crawler.crawl_url("https://example.com")
        
        assert "Main content" in content
        assert "alert" not in content
        assert "color: red" not in content
    
    @patch("researcher.web_crawler.requests.get")
    def test_crawl_url_removes_nav_and_footer(self, mock_get):
        """Test that crawl_url removes nav and footer tags (BeautifulSoup specific)."""
        mock_response = MagicMock()
        mock_response.text = """
            <html>
            <body>
            <nav>Navigation menu</nav>
            <p>Main content here</p>
            <footer>Copyright 2025</footer>
            </body>
            </html>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        crawler = WebCrawler()
        content = crawler.crawl_url("https://example.com")
        
        assert "Main content here" in content
        assert "Navigation menu" not in content
        assert "Copyright 2025" not in content
    
    @patch("researcher.web_crawler.requests.get")
    def test_crawl_url_normalizes_whitespace(self, mock_get):
        """Test that crawl_url normalizes consecutive whitespace (BeautifulSoup specific)."""
        mock_response = MagicMock()
        mock_response.text = """
            <html>
            <body>
            <p>Text   with    multiple     spaces</p>
            </body>
            </html>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        crawler = WebCrawler()
        content = crawler.crawl_url("https://example.com")
        
        # Should have normalized whitespace
        assert "multiple     spaces" not in content
        assert "multiple spaces" in content
