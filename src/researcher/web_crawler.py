import logging
import re
from typing import Any, Dict, List, Optional
import requests
from bs4 import BeautifulSoup


LOGGER = logging.getLogger(__name__)


class WebCrawler:
    """Crawl and extract content from web URLs using BeautifulSoup."""
    
    def __init__(self, timeout: int = 10, max_chars: int = 1000) -> None:
        self.timeout = timeout
        self.max_chars = max_chars
    
    def crawl_url(self, url: str) -> Optional[str]:
        """
        Crawl a URL and extract main text content using BeautifulSoup.
        Returns None if crawling fails.
        """
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
            
            # Return text up to max_chars limit
            return text[:self.max_chars] if text else None
        except Exception as exc:
            LOGGER.warning("Failed to crawl %s", url, exc_info=True)
            return None
    
    def crawl_results(self, results: List[Dict[str, Any]], max_urls: int = 3) -> Dict[str, str]:
        """
        Crawl top N URLs from search results and return their content.
        Returns dict mapping URL to extracted content.
        """
        crawled_content = {}
        
        for result in results[:max_urls]:
            url = result.get("url")
            if not url:
                continue
            
            content = self.crawl_url(url)
            if content:
                crawled_content[url] = content
        
        return crawled_content
    
    def format_crawled_content(self, crawled_content: Dict[str, str]) -> str:
        """Format crawled content for inclusion in LLM context."""
        if not crawled_content:
            return ""
        
        lines = ["[Web Content from Search Results]"]
        for url, content in crawled_content.items():
            lines.append(f"\n{url}:")
            lines.append(content)
        
        return "\n".join(lines)
