import json
import logging
import re
from typing import Any, Dict, List, Optional

from researcher.ollama_client import OllamaClient

LOGGER = logging.getLogger(__name__)


class QueryAgent:
    SYSTEM_PROMPT_JA = (
        "あなたはクエリ分析の専門家です。ユーザーの質問が以下のいずれかに該当する場合、Web検索が必要と判断してください:\n"
        "- 最新ニュース・時事問題（例: 「ウクライナの最新動向」「今日の株価」）\n"
        "- 統計データ・数値情報（例: 「2025年の人口」「GDP成長率」）\n"
        "- 現在のイベント・スケジュール（例: 「今週末のイベント」「オリンピック日程」）\n"
        "- 不明な事実・確認が必要な情報（例: 「○○社のCEOは誰？」「△△の発売日」）\n"
        "出力はJSONで、{\"needs_search\": bool, \"keywords\": [\"...\"], \"reasoning\": \"...\"} の形式にしてください。"
    )

    SYSTEM_PROMPT_EN = (
        "You are a query analysis expert. Determine if the user's question requires a web search in the following cases:\n"
        "- Latest news or current events (e.g., 'latest on Ukraine', 'today's stock prices')\n"
        "- Statistical data or numerical information (e.g., '2025 population', 'GDP growth rate')\n"
        "- Current events or schedules (e.g., 'events this weekend', 'Olympics schedule')\n"
        "- Unknown facts or information requiring verification (e.g., 'Who is the CEO of X?', 'Release date of Y')\n"
        "Output in JSON format: {\"needs_search\": bool, \"keywords\": [\"...\"], \"reasoning\": \"...\"}."
    )

    def __init__(self, ollama_client: OllamaClient, language: str = "ja") -> None:
        self.ollama_client = ollama_client
        self.language = language
        self.system_prompt = self.SYSTEM_PROMPT_JA if language == "ja" else self.SYSTEM_PROMPT_EN

    def analyze_query(self, query: str) -> Dict[str, Any]:
        message = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query},
        ]
        try:
            response = self.ollama_client.generate_response(message)
        except Exception as exc:
            LOGGER.warning("Query analysis failed: %s", exc)
            return self._default_analysis()
        return self._parse_analysis_response(response)

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        if not response:
            return self._default_analysis()
        
        # Try direct JSON parse first
        try:
            payload = json.loads(response)
        except json.JSONDecodeError:
            # Extract JSON from response that contains text + JSON
            # Look for {...} pattern in the response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if not json_match:
                LOGGER.warning("Failed to find JSON in analysis response")
                return self._default_analysis()
            
            try:
                payload = json.loads(json_match.group(0))
            except json.JSONDecodeError as exc:
                LOGGER.warning("Failed to parse extracted JSON: %s", exc)
                return self._default_analysis()

        return {
            "needs_search": bool(payload.get("needs_search")),
            "keywords": list(payload.get("keywords", [])) if payload.get("keywords") else [],
            "reasoning": payload.get("reasoning", ""),
        }

    @staticmethod
    def _default_analysis() -> Dict[str, Any]:
        return {"needs_search": False, "keywords": [], "reasoning": "分析に失敗しました。"}

    def generate_retry_query(
        self, original_query: str, failed_domains: set, previous_keywords: Optional[List[str]] = None
    ) -> str:
        """
        Generate alternative search query to retry with different sources.
        Avoids previously failed domains by suggesting alternative search terms.
        
        Args:
            original_query: The original search query
            failed_domains: Set of domains that failed during crawling
            previous_keywords: Keywords extracted from previous search (optional)
        
        Returns:
            New search query string, or original_query on failure
        """
        if previous_keywords is None:
            previous_keywords = []
        
        if self.language == "ja":
            prompt = (
                f"前回の検索でクロールに失敗したドメイン: {', '.join(failed_domains) if failed_domains else '（なし）'}。\n"
                f"これらを避けて、異なるソースから情報を得られるよう代替の検索語を提案してください。\n"
                f"元のクエリ: {original_query}\n"
                f"前回のキーワード: {', '.join(previous_keywords) if previous_keywords else '（なし）'}\n"
                f"新しい検索クエリのみを出力してください（JSON不要、1行のクエリのみ）。"
            )
        else:
            prompt = (
                f"Previous crawl failed for domains: {', '.join(failed_domains) if failed_domains else '(none)'}.\n"
                f"Suggest alternative search terms to avoid these and find information from different sources.\n"
                f"Original query: {original_query}\n"
                f"Previous keywords: {', '.join(previous_keywords) if previous_keywords else '(none)'}\n"
                f"Output only the new search query (no JSON, single line only)."
            )
        
        messages = [{"role": "system", "content": prompt}]
        try:
            response = self.ollama_client.generate_response(messages)
            return response.strip() or original_query
        except Exception as exc:
            LOGGER.warning("Retry query generation failed: %s", exc)
            return original_query