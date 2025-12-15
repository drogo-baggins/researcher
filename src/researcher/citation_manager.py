from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from dateutil import parser as date_parser


class CitationManager:
    def __init__(self) -> None:
        self.citations: Dict[int, Dict[str, Any]] = {}
        self.next_id = 1
        self.trusted_domains = {".edu", ".gov", "wikipedia.org", "arxiv.org"}
        self.major_news = {"nytimes.com", "bbc.com", "reuters.com", "apnews.com"}
        self.blacklist: Set[str] = set()

    def add_citation(
        self,
        url: str,
        title: str,
        snippet: str,
        date_str: Optional[str],
        relevance_score: float = 0.5,
    ) -> int:
        citation_id = self.next_id
        self.next_id += 1

        pub_date = self._parse_date(date_str)
        credibility = self.calculate_credibility_score(url, pub_date, relevance_score)

        self.citations[citation_id] = {
            "id": citation_id,
            "url": url,
            "title": title,
            "snippet": snippet,
            "date": pub_date.isoformat() if pub_date else None,
            "relevance_score": relevance_score,
            "credibility_score": credibility,
        }
        return citation_id

    def get_citation(self, citation_id: int) -> Dict[str, Any]:
        return self.citations.get(citation_id, {})

    def get_all_citations(self) -> List[Dict[str, Any]]:
        return list(self.citations.values())

    def update_citation_snippet(self, citation_id: int, new_snippet: str) -> bool:
        """指定IDの引用のスニペットを更新"""
        if citation_id not in self.citations:
            return False
        self.citations[citation_id]["snippet"] = new_snippet
        return True

    def clear_citations(self) -> None:
        self.citations.clear()
        self.next_id = 1

    def calculate_credibility_score(
        self, url: str, pub_date: Optional[datetime], relevance: float
    ) -> float:
        domain_score = self._get_domain_score(url)
        freshness_score = self._get_freshness_score(pub_date)
        rel = max(0.0, min(1.0, relevance))
        return (domain_score * 0.4) + (freshness_score * 0.3) + (rel * 0.3)

    def format_citation_markdown(self, citation_id: int) -> str:
        citation = self.get_citation(citation_id)
        if not citation:
            return ""
        score = citation["credibility_score"]
        return f"[{citation_id}] {citation['title']} - {citation['url']} (信頼性: {score:.2f})"

    def _get_domain_score(self, url: str) -> float:
        parsed = urlparse(url)
        host = (parsed.hostname or parsed.netloc or "").lower().split(":")[0]
        if self._matches_domain(host, self.blacklist):
            return 0.0
        if self._matches_domain(host, self.trusted_domains):
            return 1.0
        if self._matches_domain(host, self.major_news):
            return 0.8
        return 0.5

    def _matches_domain(self, host: str, domain_set: Set[str]) -> bool:
        if not host:
            return False
        for domain in domain_set:
            normalized = domain.lstrip(".").lower()
            if host == normalized or host.endswith(f".{normalized}"):
                return True
        return False

    def _get_freshness_score(self, pub_date: Optional[datetime]) -> float:
        if not pub_date:
            return 0.5
        days_old = (datetime.now() - pub_date).days
        if days_old <= 365:
            return 1.0
        if days_old <= 730:
            return 0.8
        if days_old <= 1095:
            return 0.6
        return 0.4

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return date_parser.parse(date_str)
        except Exception:
            return None
