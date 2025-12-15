import pytest
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse
from researcher.web_crawler import WebCrawler


class TestWebCrawler:
    """Test WebCrawler functionality."""
    
    def setup_method(self):
        """Setup before each test: mock load_blacklist_domains and save_blacklist_domains to prevent file I/O."""
        self.patcher_load = patch("researcher.web_crawler.load_blacklist_domains")
        self.patcher_save = patch("researcher.web_crawler.save_blacklist_domains")
        self.mock_load = self.patcher_load.start()
        self.mock_save = self.patcher_save.start()
        self.mock_load.return_value = set()
    
    def teardown_method(self):
        """Cleanup after each test."""
        self.patcher_load.stop()
        self.patcher_save.stop()
    
    def test_crawl_results_returns_dict(self):
        """Test that crawl_results returns a dictionary with correct structure."""
        crawler = WebCrawler()
        results = [
            {"url": "https://example.com", "title": "Example"},
            {"url": "https://example.org", "title": "Example Org"},
        ]
        
        with patch.object(crawler, "crawl_url") as mock_crawl:
            mock_crawl.side_effect = ["Content 1", "Content 2"]
            result = crawler.crawl_results(results, max_urls=2)
        
        # Check new structure
        assert isinstance(result, dict)
        assert "content" in result
        assert isinstance(result["content"], dict)
        assert len(result["content"]) == 2
        assert result["content"]["https://example.com"] == "Content 1"
        assert result["content"]["https://example.org"] == "Content 2"
        
        # Check metadata
        assert result["success_rate"] == 1.0
        assert result["total_attempts"] == 2
        assert result["successful_crawls"] == 2
        assert len(result["failed_domains"]) == 0
    
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
            result = crawler.crawl_results(results, max_urls=2)
        
        assert len(result["content"]) == 2
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
            result = crawler.crawl_results(results, max_urls=2)
        
        assert len(result["content"]) == 1
        assert result["content"]["https://example.com"] == "Content 1"
        assert result["successful_crawls"] == 1
        assert result["total_attempts"] == 2
        assert pytest.approx(result["success_rate"], 0.01) == 0.5
    
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

    # ===== Blacklist Tests =====
    
    def test_blacklist_initialization_empty(self):
        """Test that blacklist is initialized as empty set."""
        crawler = WebCrawler()
        assert isinstance(crawler.blacklist_domains, set)
        assert len(crawler.blacklist_domains) == 0
    
    def test_blacklist_initialization_with_domains(self):
        """Test that blacklist can be initialized with domains."""
        initial_blacklist = {"example.com", "blocked.org"}
        crawler = WebCrawler(blacklist_domains=initial_blacklist)
        assert crawler.blacklist_domains == initial_blacklist
    
    @patch("researcher.web_crawler.requests.get")
    def test_crawl_url_skips_blacklisted_domain(self, mock_get):
        """Test that crawl_url skips blacklisted domains without making requests."""
        crawler = WebCrawler(blacklist_domains={"example.com"})
        
        content = crawler.crawl_url("https://example.com/page")
        
        assert content is None
        mock_get.assert_not_called()  # リクエストしない
    
    @patch("researcher.web_crawler.requests.get")
    def test_crawl_url_adds_to_blacklist_on_exception(self, mock_get):
        """Test that failed domain is added to blacklist on exception."""
        mock_get.side_effect = Exception("Connection error")
        crawler = WebCrawler()
        
        content = crawler.crawl_url("https://paywall.com/article")
        
        assert content is None
        assert "paywall.com" in crawler.blacklist_domains
    
    @patch("researcher.web_crawler.requests.get")
    def test_crawl_url_adds_to_blacklist_on_empty_content(self, mock_get):
        """Test that domain is blacklisted when content is empty."""
        mock_response = MagicMock()
        mock_response.text = "<html><body></body></html>"  # 空コンテンツ
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        crawler = WebCrawler()
        content = crawler.crawl_url("https://empty.com/page")
        
        assert content is None
        assert "empty.com" in crawler.blacklist_domains
    
    def test_crawl_results_tracks_failed_domains(self):
        """Test that crawl_results tracks failed domains and success rate."""
        crawler = WebCrawler()
        results = [
            {"url": "https://success.com/page"},
            {"url": "https://fail1.com/page"},
            {"url": "https://fail2.com/page"},
        ]
        
        with patch.object(crawler, "crawl_url") as mock_crawl:
            # 1成功、2失敗（失敗時にブラックリスト追加をシミュレート）
            def side_effect(url):
                if "fail" in url:
                    domain = urlparse(url).netloc
                    crawler.blacklist_domains.add(domain)
                    return None
                return "Success content"
            
            mock_crawl.side_effect = side_effect
            result = crawler.crawl_results(results, max_urls=3)
        
        assert result["total_attempts"] == 3
        assert result["successful_crawls"] == 1
        assert pytest.approx(result["success_rate"], 0.01) == 1/3
        assert "fail1.com" in result["failed_domains"]
        assert "fail2.com" in result["failed_domains"]
        assert len(result["content"]) == 1
    
    def test_crawl_results_all_failures(self):
        """Test crawl_results when all URLs fail."""
        crawler = WebCrawler()
        results = [{"url": "https://fail.com/1"}, {"url": "https://fail.com/2"}]
        
        with patch.object(crawler, "crawl_url", return_value=None):
            result = crawler.crawl_results(results, max_urls=2)
        
        assert result["success_rate"] == 0.0
        assert result["successful_crawls"] == 0
        assert len(result["content"]) == 0
        assert result["total_attempts"] == 2
    
    def test_blacklist_loads_from_config(self):
        """Test that blacklist is loaded from config on initialization."""
        with patch("researcher.web_crawler.load_blacklist_domains") as mock_load:
            mock_load.return_value = {"blocked.com", "paywall.com"}
            crawler = WebCrawler()
            
            assert crawler.blacklist_domains == {"blocked.com", "paywall.com"}
            mock_load.assert_called_once()
    
    def test_blacklist_saves_on_failure(self):
        """Test that blacklist is saved when domain fails."""
        with patch("researcher.web_crawler.load_blacklist_domains", return_value=set()):
            with patch("researcher.web_crawler.save_blacklist_domains") as mock_save:
                crawler = WebCrawler()
                
                # Mock crawl failure to trigger blacklist addition
                with patch("requests.get") as mock_get:
                    mock_get.side_effect = Exception("Network error")
                    result = crawler.crawl_url("https://example.com/page")
                    
                    assert result is None
                    assert "example.com" in crawler.blacklist_domains
                    mock_save.assert_called_once()
    
    def test_add_to_blacklist(self):
        """Test manual blacklist addition."""
        with patch("researcher.web_crawler.load_blacklist_domains", return_value=set()):
            with patch("researcher.web_crawler.save_blacklist_domains") as mock_save:
                crawler = WebCrawler()
                crawler.add_to_blacklist("example.com")
                
                assert "example.com" in crawler.blacklist_domains
                mock_save.assert_called_once_with({"example.com"})
    
    def test_domain_normalization(self):
        """Test that domain normalization works correctly."""
        from researcher.web_crawler import normalize_domain
        
        assert normalize_domain("WSJ.com") == "wsj.com"
        assert normalize_domain("www.example.com") == "example.com"
        assert normalize_domain("WWW.EXAMPLE.COM") == "example.com"
        assert normalize_domain("sub.example.com") == "sub.example.com"
        assert normalize_domain("  example.com  ") == "example.com"
    
    def test_crawl_url_with_www_domain(self):
        """Test that crawl_url normalizes www. prefix in domain."""
        with patch("researcher.web_crawler.load_blacklist_domains", return_value={"example.com"}):
            with patch("researcher.web_crawler.save_blacklist_domains"):
                crawler = WebCrawler()
                
                # www.example.com should be blacklisted if example.com is
                result = crawler.crawl_url("https://www.example.com/page")
                assert result is None
    
    def test_add_to_blacklist_normalizes_input(self):
        """Test that add_to_blacklist normalizes domain input."""
        with patch("researcher.web_crawler.load_blacklist_domains", return_value=set()):
            with patch("researcher.web_crawler.save_blacklist_domains") as mock_save:
                crawler = WebCrawler()
                
                # Add www.WSJ.COM, should be normalized to wsj.com
                crawler.add_to_blacklist("www.WSJ.COM")
                assert "wsj.com" in crawler.blacklist_domains
                mock_save.assert_called_once_with({"wsj.com"})
    
    def test_crawl_results_normalizes_failed_domains(self):
        """Test that crawl_results normalizes domains in failed_domains set.
        
        This ensures that failed domains with www. prefix or uppercase characters
        are stored in normalized form matching self.blacklist_domains, making
        logged failures and QueryAgent.generate_retry_query() fully consistent.
        """
        crawler = WebCrawler()
        results = [
            {"url": "https://WWW.EXAMPLE.COM/page"},
            {"url": "https://www.fail.com/page"},
        ]
        
        with patch.object(crawler, "crawl_url") as mock_crawl:
            def side_effect(url):
                if "www.fail.com" in url.lower():
                    # Simulate failure adding to blacklist
                    domain = "www.fail.com"
                    crawler.blacklist_domains.add("fail.com")  # normalize_domain applied
                    return None
                return "Success content"
            
            mock_crawl.side_effect = side_effect
            result = crawler.crawl_results(results, max_urls=2)
        
        # Verify failed_domains contains normalized form
        assert result["successful_crawls"] == 1
        assert len(result["failed_domains"]) == 1
        # Should be normalized to lowercase, www. stripped
        assert "fail.com" in result["failed_domains"]
        # Should NOT contain uppercase or www. prefix
        assert "www.fail.com" not in result["failed_domains"]
        assert "FAIL.COM" not in result["failed_domains"]