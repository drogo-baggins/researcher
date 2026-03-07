import json
import logging
import re
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger(__name__)


class QueryAgent:
    SYSTEM_PROMPT_JA = (
        "あなたはクエリ分析の専門家です。ユーザーの質問が以下のいずれかに該当する場合、Web検索が必要と判断してください:\n"
        "- 最新ニュース・時事問題（例: 「ウクライナの最新動向」「今日の株価」）\n"
        "- 統計データ・数値情報（例: 「2025年の人口」「GDP成長率」）\n"
        "- 現在のイベント・スケジュール（例: 「今週末のイベント」「オリンピック日程」）\n"
        "- 不明な事実・確認が必要な情報（例: 「○○社のCEOは誰？」「△△の発売日」）\n"
        "- 企業製品の最新版・機能・リリースノート（例: 「TIBCO EBXの最新機能」「Salesforceの新バージョン」「製品Xのリリースノート」）\n"
        "公式ドキュメント、製品サイト、リリースノートを優先的に検索してください。\n"
        "出力はJSONで、{\"needs_search\": bool, \"keywords\": [\"...\"], \"reasoning\": \"...\"} の形式にしてください。"
    )

    SYSTEM_PROMPT_EN = (
        "You are a query analysis expert. Determine if the user's question requires a web search in the following cases:\n"
        "- Latest news or current events (e.g., 'latest on Ukraine', 'today's stock prices')\n"
        "- Statistical data or numerical information (e.g., '2025 population', 'GDP growth rate')\n"
        "- Current events or schedules (e.g., 'events this weekend', 'Olympics schedule')\n"
        "- Unknown facts or information requiring verification (e.g., 'Who is the CEO of X?', 'Release date of Y')\n"
        "- Latest versions, features, or release notes of enterprise products (e.g., 'TIBCO EBX latest features', 'Salesforce new version', 'Product X release notes')\n"
        "Prioritize official documentation, product sites, and release notes in your search.\n"
        "Output in JSON format: {\"needs_search\": bool, \"keywords\": [\"...\"], \"reasoning\": \"...\"}."
    )

    def __init__(self, ollama_client: Any, language: str = "ja") -> None:
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
                f"公式ドキュメント、製品サイト、リリースノートを優先する検索語を提案してください。\n"
                f"元のクエリ: {original_query}\n"
                f"前回のキーワード: {', '.join(previous_keywords) if previous_keywords else '（なし）'}\n"
                f"新しい検索クエリのみを出力してください（JSON不要、1行のクエリのみ）。"
            )
        else:
            prompt = (
                f"Previous crawl failed for domains: {', '.join(failed_domains) if failed_domains else '(none)'}.\n"
                f"Suggest alternative search terms to avoid these and find information from different sources.\n"
                f"Prioritize search terms that emphasize official documentation, product sites, and release notes.\n"
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
    
    def generate_search_retry_query(
        self, 
        original_query: str, 
        failure_reason: str = "unknown",
        retry_count: int = 1
    ) -> str:
        """
        検索失敗時の代替クエリを生成
        
        検索エンジンの応答がない場合、段階的にクエリを簡潔化・一般化して再試行を促す。
        リトライ回数に応じて異なる戦略を採用:
        - 1回目: クエリの簡潔化（複雑な演算子や括弧を削除）
        - 2回目: キーワードの一般化（具体的な製品名から一般的な概念へ）
        - 3回目: 最小限のキーワード（最重要キーワードのみ）
        
        Args:
            original_query: 元のクエリ
            failure_reason: 失敗の原因（"timeout", "connection_error", "http_error", "parse_error", "empty_results", "unknown"）
            retry_count: リトライ回数（1, 2, 3）
        
        Returns:
            新しい検索クエリ文字列、または失敗時は元のクエリ
        """
        if self.language == "ja":
            if retry_count == 1:
                # 1回目のリトライ：クエリの簡潔化
                prompt = (
                    f"検索エンジンが応答しません（原因: {failure_reason}）。\n"
                    f"以下のクエリをより簡潔で単純な形に変更してください。\n"
                    f"複雑な演算子（OR, AND, NOT）や括弧を避け、最も重要なキーワード3-5個に絞ってください。\n"
                    f"元のクエリ: {original_query}\n"
                    f"新しい検索クエリのみを出力してください（1行のみ）。"
                )
            elif retry_count == 2:
                # 2回目のリトライ：キーワードの一般化
                prompt = (
                    f"検索エンジンが応答しません（原因: {failure_reason}）。\n"
                    f"以下のクエリを、より一般的で広い範囲をカバーするクエリに変更してください。\n"
                    f"具体的な製品名やバージョン番号よりも、一般的な概念や分野を優先してください。\n"
                    f"例: 「ROG Flow Z13 2025」→「ノートパソコン」、「Ollama」→「ローカルLLM」\n"
                    f"元のクエリ: {original_query}\n"
                    f"新しい検索クエリのみを出力してください（1行のみ）。"
                )
            else:  # retry_count >= 3
                # 3回目のリトライ：最後の試み
                prompt = (
                    f"検索エンジンが応答しません（原因: {failure_reason}）。\n"
                    f"以下のクエリを、最も基本的で一般的な形に変更してください。\n"
                    f"1-2個の最重要キーワードのみを使用してください。\n"
                    f"元のクエリ: {original_query}\n"
                    f"新しい検索クエリのみを出力してください（1行のみ）。"
                )
        else:  # English
            if retry_count == 1:
                prompt = (
                    f"Search engine is not responding (reason: {failure_reason}).\n"
                    f"Simplify the following query to be more concise and straightforward.\n"
                    f"Avoid complex operators (OR, AND, NOT) or parentheses, and focus on 3-5 most important keywords.\n"
                    f"Original query: {original_query}\n"
                    f"Output only the new search query (single line only)."
                )
            elif retry_count == 2:
                prompt = (
                    f"Search engine is not responding (reason: {failure_reason}).\n"
                    f"Broaden the following query to cover a wider range of information.\n"
                    f"Prioritize general concepts and fields over specific product names or version numbers.\n"
                    f"Example: 'ROG Flow Z13 2025' → 'laptop', 'Ollama' → 'local LLM'\n"
                    f"Original query: {original_query}\n"
                    f"Output only the new search query (single line only)."
                )
            else:
                prompt = (
                    f"Search engine is not responding (reason: {failure_reason}).\n"
                    f"Reduce the following query to its most basic and general form.\n"
                    f"Use only 1-2 most essential keywords.\n"
                    f"Original query: {original_query}\n"
                    f"Output only the new search query (single line only)."
                )
        
        messages = [{"role": "system", "content": prompt}]
        try:
            response = self.ollama_client.generate_response(messages)
            return response.strip() or original_query
        except Exception as exc:
            LOGGER.warning("Search retry query generation failed: %s", exc)
            return original_query
    
    def generate_conversation_title(self, messages: List[Dict[str, str]], max_length: int = 50) -> str:
        """
        Generate a concise conversation title from message history using LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_length: Maximum title length (default: 50 characters)
        
        Returns:
            Generated title (max_length characters)
        """
        # Extract recent user and assistant messages for context (last 3-5 messages)
        recent_messages = [m for m in messages if m.get("role") in ["user", "assistant"]][-5:]
        
        conversation_text = ""
        for msg in recent_messages:
            role = "ユーザー" if msg["role"] == "user" else "AI"
            conversation_text += f"{role}: {msg['content'][:200]}\n"
        
        if not conversation_text:
            return "新しい会話"
        
        prompt = (
            f"以下の会話から、会話の主要なトピックを表す簡潔なタイトルを生成してください。\n"
            f"タイトルは{max_length}文字以内にしてください。\n"
            f"タイトルのみを出力してください（説明や引用符は不要）。\n\n"
            f"会話:\n{conversation_text}\n\n"
            f"タイトル:"
        ) if self.language == "ja" else (
            f"Generate a concise title that captures the main topic of the following conversation.\n"
            f"Keep the title within {max_length} characters.\n"
            f"Output only the title (no explanations or quotes).\n\n"
            f"Conversation:\n{conversation_text}\n\n"
            f"Title:"
        )
        
        title_messages = [{"role": "user", "content": prompt}]
        try:
            response = self.ollama_client.generate_response(title_messages)
            title = response.strip()
            
            # Remove quotes if present
            title = title.strip('"\'「」『』')
            
            # Truncate to max_length
            if len(title) > max_length:
                title = title[:max_length] + "..."
            
            return title if title else "新しい会話"
        except Exception as exc:
            LOGGER.warning("Conversation title generation failed: %s", exc)
            # Fallback: use first user message
            first_user_msg = next((msg['content'] for msg in messages if msg.get('role') == 'user'), None)
            if first_user_msg:
                return first_user_msg[:max_length] + ("..." if len(first_user_msg) > max_length else "")
            return "新しい会話"