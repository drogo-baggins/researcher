from typing import Any, Dict, List, Optional


class ChatManager:
    def __init__(
        self,
        ollama_client,
        searxng_client: Optional[Any] = None,
        agent: Optional[Any] = None,
        reranker: Optional[Any] = None,
        mcp_client: Optional[Any] = None,
        citation_manager: Optional[Any] = None,
        web_crawler: Optional[Any] = None,
        language: str = "ja",
    ):
        self.ollama_client = ollama_client
        self.searxng_client = searxng_client
        self.agent = agent
        self.reranker = reranker
        self.mcp_client = mcp_client
        self.citation_manager = citation_manager
        self.web_crawler = web_crawler
        self.language = language
        self.messages = []
        self.current_citation_ids: List[int] = []
        self.last_search_content: str = ""  # Store crawled content from last search
        self.last_search_turns_remaining: int = 0  # Number of turns to keep injecting crawled content

    def add_system_message(self, content, search_result: bool = False):
        self.messages.append(
            {"role": "system", "content": content, "search_result": search_result}
        )

    def add_user_message(self, content):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content):
        self.messages.append({"role": "assistant", "content": content})

    def _get_rag_system_prompt(self) -> str:
        """Get language-aware RAG system message template."""
        if self.language == "en":
            return (
                "The following is content extracted from web pages retrieved from search results. "
                "Use this information to generate accurate and detailed answers to the user's questions.\n\n"
            )
        else:  # Default to Japanese
            return (
                "以下は検索結果から取得したWebページの内容です。"
                "この情報を活用して、ユーザーの質問に対して正確で詳細な回答を生成してください。\n\n"
            )

    def get_response(self):
        # Build messages with optional crawled content injection
        messages = self.messages.copy()
        
        # If we have crawled content from recent search and turns remaining, inject it as a system message
        if self.last_search_content and self.last_search_turns_remaining > 0:
            crawl_system_msg = {
                "role": "system",
                "content": self._get_rag_system_prompt() + self.last_search_content
            }
            # 既存のシステムメッセージの後に挿入
            system_count = sum(1 for m in messages if m.get("role") == "system")
            messages.insert(system_count, crawl_system_msg)
        
        response = self.ollama_client.generate_response(messages)
        citations_md = self._format_citations_markdown()
        if citations_md:
            response = response + "\n\n" + citations_md
        self.add_assistant_message(response)
        self.current_citation_ids.clear()
        
        # Decrement the remaining turns and clear if expired
        if self.last_search_turns_remaining > 0:
            self.last_search_turns_remaining -= 1
            if self.last_search_turns_remaining == 0:
                self.last_search_content = ""
        
        return response

    def get_response_stream(self):
        chunks = []
        
        # Build messages with optional crawled content injection
        messages = self.messages.copy()
        
        # If we have crawled content from recent search and turns remaining, inject it as a system message
        if self.last_search_content and self.last_search_turns_remaining > 0:
            crawl_system_msg = {
                "role": "system",
                "content": self._get_rag_system_prompt() + self.last_search_content
            }
            # 既存のシステムメッセージの後に挿入
            system_count = sum(1 for m in messages if m.get("role") == "system")
            messages.insert(system_count, crawl_system_msg)

        def stream():
            for chunk in self.ollama_client.generate_response_stream(messages):
                chunks.append(chunk)
                yield chunk
            response = "".join(chunks)
            citations_md = self._format_citations_markdown()
            if citations_md:
                yield "\n\n" + citations_md
                response = response + "\n\n" + citations_md
            self.add_assistant_message(response)
            self.current_citation_ids.clear()
            
            # Decrement the remaining turns and clear if expired
            if self.last_search_turns_remaining > 0:
                self.last_search_turns_remaining -= 1
                if self.last_search_turns_remaining == 0:
                    self.last_search_content = ""

        return stream()

    def search(self, query: str, *, use_reranker: bool = True, **kwargs: Any) -> Dict[str, Any]:
        if not self.searxng_client:
            raise RuntimeError("検索機能が有効化されていません")

        payload = self.searxng_client.search(query, **kwargs)
        results = payload.get("results", [])
        
        # Reranker は embedding 取得に失敗することが多いため、結果が 0 になった場合は元の結果を使用
        if use_reranker and self.reranker is not None:
            try:
                reranked_results = self.reranker.rerank(query, results)
                if reranked_results:  # reranked結果がある場合のみ使用
                    results = reranked_results
            except Exception:
                # rerank失敗時は元の結果を使用（サイレントフォールバック）
                pass
        
        # CitationManagerで引用を追加（エラーハンドリング付き）
        # Store citation_id directly on result dict to maintain mapping even if some citations fail
        self.current_citation_ids.clear()
        if self.citation_manager:
            for result in results:
                try:
                    citation_id = self.citation_manager.add_citation(
                        url=result.get("url", ""),
                        title=result.get("title", ""),
                        snippet=result.get("snippet", ""),
                        date_str=result.get("published_date"),
                        relevance_score=result.get("score", 0.5),
                    )
                    # Store citation_id on result dict for later use
                    result["_citation_id"] = citation_id
                    self.current_citation_ids.append(citation_id)
                except Exception:
                    # Citation追加に失敗してもサーチ全体は続行
                    continue
        
        # Crawl top URLs to extract content for RAG context and update citations
        self.last_search_content = ""
        self.last_search_turns_remaining = 0  # Reset turns counter
        if self.web_crawler and results:
            try:
                crawl_result = self.web_crawler.crawl_results(results, max_urls=3)
                crawled_content = crawl_result["content"]
                
                # Log crawl statistics
                import logging
                logger = logging.getLogger(__name__)
                logger.info(
                    "Crawl stats: %d/%d successful (%.1f%%), failed domains: %s",
                    crawl_result["successful_crawls"],
                    crawl_result["total_attempts"],
                    crawl_result["success_rate"] * 100,
                    crawl_result["failed_domains"]
                )
                
                if crawled_content:
                    self.last_search_content = self.web_crawler.format_crawled_content(crawled_content)
                    # Set to 1 turn to inject crawled content for the next response only
                    self.last_search_turns_remaining = 1
                    
                    # Update citation snippets with crawled content
                    if self.citation_manager:
                        for result in results:
                            url = result.get("url")
                            # Use _citation_id stored on result dict instead of positional index
                            citation_id = result.get("_citation_id")
                            if url in crawled_content and citation_id is not None:
                                # Use first 500 characters of crawled content as snippet
                                snippet = crawled_content[url][:500]
                                self.citation_manager.update_citation_snippet(citation_id, snippet)
            except Exception:
                # Web crawling failure is non-critical, continue without it
                pass
        
        formatted = self._format_search_results(query, results)
        self.add_system_message(formatted, search_result=True)
        return {"formatted": formatted, "raw": payload.get("raw", payload), "results": results}

    def auto_search(self, query: str) -> Dict[str, Any]:
        if not self.agent:
            raise RuntimeError("Agentが設定されていません")

        analysis = self.agent.analyze_query(query)
        if not analysis.get("needs_search"):
            return {"searched": False, "formatted": "", "results": [], "analysis": analysis}

        # キーワードが返された場合は、元のクエリを補強
        # trim、空文字値除外、重複排除を実施
        seen = set()
        keywords = []
        for kw in analysis.get("keywords", []):
            cleaned = kw.strip() if isinstance(kw, str) else ""
            if cleaned and cleaned not in seen:
                keywords.append(cleaned)
                seen.add(cleaned)
        
        if keywords:
            # OR結合でキーワードを追加（例: "元のクエリ (keyword1 OR keyword2 OR keyword3)"）
            or_keywords = " OR ".join(keywords)
            search_query = f"{query} ({or_keywords})"
        else:
            # キーワードなしの場合は元のクエリを使用
            search_query = query
        
        search_result = self.search(search_query)
        return {
            "searched": True,
            "formatted": search_result["formatted"],
            "results": search_result["results"],
            "analysis": analysis,
        }

    def _format_search_results(self, query: str, results: List[Dict[str, Any]]) -> str:
        lines = [f"[検索結果: {query}]"]
        if not results:
            lines.append("検索結果は見つかりませんでした。")
        for idx, item in enumerate(results, start=1):
            title = item.get("title") or "(タイトルなし)"
            url = item.get("url") or "(URLなし)"
            snippet = item.get("snippet") or ""
            cid = item.get("_citation_id")
            citation_ref = f" [{cid}]" if cid else ""
            lines.append(f"{idx}. {title} - {url}{citation_ref}")
            if snippet:
                lines.append(f"   {snippet}")
        return "\n".join(lines)

    def clear_history(self, keep_system=True, clear_citations: bool = True):
        if keep_system:
            self.messages = [
                m
                for m in self.messages
                if m["role"] == "system" and not m.get("search_result")
            ]
        else:
            self.messages = []
        
        self.current_citation_ids.clear()
        self.last_search_content = ""  # Clear crawled content
        self.last_search_turns_remaining = 0  # Reset search context expiration
        if clear_citations and self.citation_manager:
            self.citation_manager.clear_citations()

    def get_history(self):
        return self.messages

    def execute_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.mcp_client:
            raise RuntimeError("MCP機能が有効化されていません")

        result = self.mcp_client.call_tool(tool_name, arguments)
        formatted = self._format_mcp_result(tool_name, arguments, result)
        self.add_system_message(formatted, search_result=False)
        return {"formatted": formatted, "raw": result, "isError": result.get("isError", False)}

    def _format_mcp_result(self, tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any]) -> str:
        server = result.get("server", "unknown")
        is_error = result.get("isError", False)
        prefix = "[ERROR]" if is_error else "[MCP]"
        lines = [f"{prefix} {server}.{tool_name}"]
        lines.append(f"引数: {arguments}")
        if is_error:
            lines.append(f"エラー: {result.get('error', '詳細不明')}")
        else:
            content = result.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        lines.append(f"  {item}")
                    else:
                        lines.append(f"  {item}")
            else:
                lines.append(f"  {content}")
        return "\n".join(lines)

    def _format_citations_markdown(self) -> str:
        """引用IDのマークダウン形式を生成"""
        if not self.citation_manager or not self.current_citation_ids:
            return ""
        lines = ["## 参照"]
        for cid in self.current_citation_ids:
            markdown = self.citation_manager.format_citation_markdown(cid)
            if markdown:
                lines.append(markdown)
        return "\n".join(lines)

