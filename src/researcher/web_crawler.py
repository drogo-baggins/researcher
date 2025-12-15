import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


LOGGER = logging.getLogger(__name__)


class WebCrawler:
    """Crawl and extract content from web URLs using BeautifulSoup."""
    
    def __init__(self, timeout: int = 10, max_chars: int = 1000, blacklist_domains: Optional[set] = None) -> None:
        self.timeout = timeout
        self.max_chars = max_chars
        self.blacklist_domains = blacklist_domains if blacklist_domains is not None else set()
    
    def crawl_url(self, url: str) -> Optional[str]:
        """
        Crawl a URL and extract main text content using BeautifulSoup.
        Returns None if crawling fails or domain is blacklisted.
        """
        # Domain extraction and blacklist check
        try:
            domain = urlparse(url).netloc
        except Exception:
            LOGGER.warning("Failed to parse URL: %s", url)
            return None
        
        # Check blacklist
        if domain in self.blacklist_domains:
            LOGGER.info("Skipping blacklisted domain: %s", domain)
            return None
        
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            # Parse HTML with BeautifulSoup, with fallback parser
            try:
                soup = BeautifulSoup(response.text, 'lxml')
            except Exception:
                # Fallback to html.parser if lxml fails
                soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script, style, nav, and footer tags (noise reduction)
            for tag in soup(['script', 'style', 'nav', 'footer', 'noscript']):
                tag.decompose()
            
            # Extract text content
            text = soup.get_text(separator=' ', strip=True)
            
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
            
            # Check for empty content
            if not text:
                LOGGER.warning("Empty content from %s, adding to blacklist", url)
                self.blacklist_domains.add(domain)
                return None
            
            # Return text up to max_chars limit
            return text[:self.max_chars]
        except Exception as exc:
            LOGGER.warning("Failed to crawl %s, adding domain to blacklist", url, exc_info=True)
            self.blacklist_domains.add(domain)
            return None
    
    def crawl_results(self, results: List[Dict[str, Any]], max_urls: int = 3) -> Dict[str, Any]:
        """
        Crawl top N URLs from search results and return content with metadata.
        
        Returns:
            {
                "content": Dict[str, str],  # URL -> extracted content
                "failed_domains": Set[str],  # Domains that failed during this call
                "success_rate": float,  # successful_crawls / total_attempts
                "total_attempts": int,
                "successful_crawls": int
            }
        """
        crawled_content = {}
        failed_domains_this_call = set()
        total_attempts = 0
        
        for result in results[:max_urls]:
            url = result.get("url")
            if not url:
                continue
            
            total_attempts += 1
            initial_blacklist_size = len(self.blacklist_domains)
            
            content = self.crawl_url(url)
            
            if content:
                crawled_content[url] = content
            else:
                # Check if domain was added to blacklist during this crawl
                if len(self.blacklist_domains) > initial_blacklist_size:
                    try:
                        domain = urlparse(url).netloc
                        failed_domains_this_call.add(domain)
                    except Exception:
                        pass
        
        successful_crawls = len(crawled_content)
        success_rate = successful_crawls / total_attempts if total_attempts > 0 else 0.0
        
        return {
            "content": crawled_content,
            "failed_domains": failed_domains_this_call,
            "success_rate": success_rate,
            "total_attempts": total_attempts,
            "successful_crawls": successful_crawls
        }
    
    def format_crawled_content(self, crawled_content: Dict[str, str]) -> str:
        """Format crawled content for inclusion in LLM context."""
        if not crawled_content:
            return ""
        
        lines = ["[Web Content from Search Results]"]
        for url, content in crawled_content.items():
            lines.append(f"\n{url}:")
            lines.append(content)
        
        return "\n".join(lines)
