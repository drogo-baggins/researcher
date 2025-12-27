from typing import Any, Callable, Dict, List, Optional
import json
import logging

LOGGER = logging.getLogger(__name__)

# Maximum number of self-evaluation retries (loop-based, not recursive)
MAX_SELF_EVAL_RETRIES = 1


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
        enable_self_evaluation: bool = False,
        enable_feedback_adjustment: bool = True,
        evaluation_model: Optional[str] = None,
        searxng_engine: Optional[str] = None,
        searxng_lang: Optional[str] = None,
        searxng_safesearch: Optional[str] = None,
    ):
        self.ollama_client = ollama_client
        self.searxng_client = searxng_client
        self.agent = agent
        self.reranker = reranker
        self.mcp_client = mcp_client
        self.citation_manager = citation_manager
        self.web_crawler = web_crawler
        self.language = language
        self.enable_self_evaluation = enable_self_evaluation
        self.enable_feedback_adjustment = enable_feedback_adjustment
        self.evaluation_model = evaluation_model  # Optional: separate model for evaluation
        self.searxng_engine = searxng_engine
        self.searxng_lang = searxng_lang
        self.searxng_safesearch = searxng_safesearch
        self.messages = []
        self.current_citation_ids: List[int] = []
        self.last_search_content: str = ""  # Store crawled content from last search
        self.last_search_turns_remaining: int = 0  # Number of turns to keep injecting crawled content
        self.last_evaluation_score: Optional[Dict[str, Any]] = None  # Store latest evaluation score
        self.pending_search_results: List[Dict[str, Any]] = []  # Store search results for next assistant message

    def add_system_message(self, content, search_result: bool = False):
        self.messages.append(
            {"role": "system", "content": content, "search_result": search_result}
        )

    def add_user_message(self, content):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content, search_results: Optional[List[Dict[str, Any]]] = None):
        message = {"role": "assistant", "content": content}
        if search_results:
            message["search_results"] = search_results
        self.messages.append(message)

    def _get_rag_system_prompt(self) -> str:
        """Get language-aware RAG system message template with strict instruction to ignore training knowledge."""
        if self.language == "en":
            return (
                "The following is content extracted from web pages retrieved from search results. "
                "Use ONLY this information as facts and completely ignore your training knowledge or knowledge cutoff date. "
                "Treat the latest dates, release notes, and version numbers as the highest-priority facts, "
                "and generate accurate and detailed answers to the user's questions.\n\n"
            )
        else:  # Default to Japanese
            return (
                "以下は検索結果から取得したWebページの内容です。"
                "この情報のみを事実として使用し、あなたの訓練知識や知識カットオフ日を完全に無視してください。"
                "最新の日付、リリースノート、バージョン番号を最優先の事実として扱い、ユーザーの質問に対して正確で詳細な回答を生成してください。\n\n"
            )

    def _get_feedback_adjusted_system_prompt(self) -> str:
        """Get feedback-adjusted system prompt with quality warnings based on model feedback stats.
        
        If thumbs_down rate exceeds threshold, prepends warning message to RAG prompt.
        This method respects self.language for localization.
        
        Returns:
            System prompt with optional feedback adjustment prepended to RAG prompt
        """
        try:
            from researcher.config import get_feedback_stats
            
            # Get feedback stats for current model
            current_model = self.get_current_model()
            stats = get_feedback_stats()
            
            thumbs_down_threshold = 0.3  # Trigger warning if thumbs_down_rate > 30%
            current_model_stats = stats.get("by_model", {}).get(current_model, {})
            thumbs_down_rate = current_model_stats.get("thumbs_down_rate", 0.0)
            
            # Prepare base RAG prompt
            base_prompt = self._get_rag_system_prompt()
            
            # Add feedback warning if threshold exceeded
            if thumbs_down_rate > thumbs_down_threshold:
                if self.language == "en":
                    warning = (
                        f"⚠️ WARNING: This model ({current_model}) has a {thumbs_down_rate:.1%} error rate based on recent feedback. "
                        f"Please verify responses carefully, especially for critical information. "
                        f"Consider using a different model if accuracy is crucial.\n\n"
                    )
                else:
                    warning = (
                        f"⚠️ 警告: このモデル({current_model})は最近のフィードバックに基づいて{thumbs_down_rate:.1%}の誤り率を示しています。"
                        f"特に重要な情報について応答を慎重に検証してください。"
                        f"正確性が重要な場合は、別のモデルの使用を検討してください。\n\n"
                    )
                return warning + base_prompt
            else:
                return base_prompt
        
        except Exception as e:
            # Silently fall back to base RAG prompt if adjustment fails
            LOGGER.debug(f"Feedback adjustment failed: {e}")
            return self._get_rag_system_prompt()
    
    def _get_search_failure_system_message(self) -> str:
        """
        検索失敗時にLLMに注入するシステムメッセージを生成
        
        LLMが訓練データに基づくハルシネーションを避け、検索失敗を明示的に
        ユーザーに伝えるよう指示するメッセージを返します。
        
        Returns:
            言語設定に応じた検索失敗メッセージ
        """
        if self.language == "en":
            return (
                "Search failed. Unable to provide up-to-date information. "
                "Please avoid responses based on training data and inform the user that the search failed."
            )
        else:
            return (
                "検索に失敗したため最新情報を提供できません。"
                "訓練データに基づく回答を避け、検索失敗をユーザーに伝えてください。"
            )

    def get_response(self, evaluation_threshold: float = 0.7):
        # Build messages with optional crawled content injection
        messages = self.messages.copy()
        
        # If we have crawled content from recent search and turns remaining, inject it as a system message
        if self.last_search_content and self.last_search_turns_remaining > 0:
            # Use feedback-adjusted RAG prompt if enabled, otherwise use base RAG prompt
            rag_prompt = self._get_feedback_adjusted_system_prompt() if self.enable_feedback_adjustment else self._get_rag_system_prompt()
            crawl_system_msg = {
                "role": "system",
                "content": rag_prompt + self.last_search_content
            }
            # 既存のシステムメッセージの後に挿入
            system_count = sum(1 for m in messages if m.get("role") == "system")
            messages.insert(system_count, crawl_system_msg)
        
        response = self.ollama_client.generate_response(messages)
        citations_md = self._format_citations_markdown()
        if citations_md:
            response = response + "\n\n" + citations_md
        self.add_assistant_message(response, search_results=self.pending_search_results)
        self.pending_search_results = []
        self.current_citation_ids.clear()
        
        # Get last user query for evaluation
        last_user_query = None
        for msg in reversed(self.messages):
            if msg.get("role") == "user":
                last_user_query = msg.get("content", "")
                break
        
        # Self-evaluation with explicit loop-based retry (not recursive)
        if self.enable_self_evaluation and last_user_query:
            retries_remaining = MAX_SELF_EVAL_RETRIES
            while retries_remaining > 0:
                eval_result = self.self_evaluate(last_user_query, response)
                overall_score = eval_result.get("overall_score", 0.5)
                
                if overall_score < evaluation_threshold and self.searxng_client and self.agent and retries_remaining > 0:
                    try:
                        # Auto-search and regenerate
                        LOGGER.info(f"Response quality low (score: {overall_score:.2f}), executing retry {MAX_SELF_EVAL_RETRIES - retries_remaining + 1}/{MAX_SELF_EVAL_RETRIES}")
                        auto_result = self.auto_search(last_user_query)
                        self.pending_search_results = auto_result.get("all_search_results", [])
                        if auto_result.get("searched"):
                            # Re-generate response with search context
                            self.messages.pop()  # Remove previous response
                            messages = self.messages.copy()
                            
                            # Inject crawled content
                            if self.last_search_content and self.last_search_turns_remaining > 0:
                                rag_prompt = self._get_feedback_adjusted_system_prompt() if self.enable_feedback_adjustment else self._get_rag_system_prompt()
                                crawl_system_msg = {
                                    "role": "system",
                                    "content": rag_prompt + self.last_search_content
                                }
                                system_count = sum(1 for m in messages if m.get("role") == "system")
                                messages.insert(system_count, crawl_system_msg)
                            
                            # Generate new response
                            response = self.ollama_client.generate_response(messages)
                            citations_md = self._format_citations_markdown()
                            if citations_md:
                                response = response + "\n\n" + citations_md
                            self.add_assistant_message(response, search_results=self.pending_search_results)
                            self.pending_search_results = []
                            self.current_citation_ids.clear()
                        else:
                            break  # No search results, stop retrying
                    except Exception as e:
                        LOGGER.warning(f"Auto-retry failed: {e}")
                        break  # Stop retrying on error
                    finally:
                        retries_remaining -= 1
                else:
                    # Score is acceptable or no retry available
                    break
        
        # Decrement the remaining turns and clear if expired
        if self.last_search_turns_remaining > 0:
            self.last_search_turns_remaining -= 1
            if self.last_search_turns_remaining == 0:
                self.last_search_content = ""
        
        return response

    def get_response_stream(self, evaluation_threshold: float = 0.7):
        chunks = []
        
        # Build messages with optional crawled content injection
        messages = self.messages.copy()
        
        # If we have crawled content from recent search and turns remaining, inject it as a system message
        if self.last_search_content and self.last_search_turns_remaining > 0:
            # Use feedback-adjusted RAG prompt if enabled, otherwise use base RAG prompt
            rag_prompt = self._get_feedback_adjusted_system_prompt() if self.enable_feedback_adjustment else self._get_rag_system_prompt()
            crawl_system_msg = {
                "role": "system",
                "content": rag_prompt + self.last_search_content
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
            self.add_assistant_message(response, search_results=self.pending_search_results)
            self.pending_search_results = []
            self.current_citation_ids.clear()
            
            # Get last user query for evaluation
            last_user_query = None
            for msg in reversed(self.messages[:-1]):  # Exclude newly added assistant message
                if msg.get("role") == "user":
                    last_user_query = msg.get("content", "")
                    break
            
            # Self-evaluation with explicit loop-based retry (not recursive)
            if self.enable_self_evaluation and last_user_query:
                LOGGER.debug(f"Starting self-evaluation: enable={self.enable_self_evaluation}, query={bool(last_user_query)}")
                retries_remaining = MAX_SELF_EVAL_RETRIES
                while retries_remaining > 0:
                    eval_result = self.self_evaluate(last_user_query, response)
                    LOGGER.debug(f"Evaluation completed: {eval_result}")
                    overall_score = eval_result.get("overall_score", 0.5)
                    
                    if overall_score < evaluation_threshold and self.searxng_client and self.agent and retries_remaining > 0:
                        try:
                            # Auto-search and regenerate
                            LOGGER.info(f"Response quality low (score: {overall_score:.2f}), executing retry {MAX_SELF_EVAL_RETRIES - retries_remaining + 1}/{MAX_SELF_EVAL_RETRIES}")
                            auto_result = self.auto_search(last_user_query)
                            self.pending_search_results = auto_result.get("all_search_results", [])
                            if auto_result.get("searched"):
                                # Re-generate response with search context (non-recursive)
                                self.messages.pop()  # Remove previous response
                                
                                # Build new messages with updated search content
                                new_messages = self.messages.copy()
                                if self.last_search_content and self.last_search_turns_remaining > 0:
                                    rag_prompt = self._get_feedback_adjusted_system_prompt() if self.enable_feedback_adjustment else self._get_rag_system_prompt()
                                    crawl_system_msg = {
                                        "role": "system",
                                        "content": rag_prompt + self.last_search_content
                                    }
                                    system_count = sum(1 for m in new_messages if m.get("role") == "system")
                                    new_messages.insert(system_count, crawl_system_msg)
                                
                                # Generate new response (reset chunks for new attempt)
                                retry_chunks = []
                                for chunk in self.ollama_client.generate_response_stream(new_messages):
                                    retry_chunks.append(chunk)
                                    yield chunk
                                
                                retry_response = "".join(retry_chunks)
                                retry_citations_md = self._format_citations_markdown()
                                if retry_citations_md:
                                    yield "\n\n" + retry_citations_md
                                    retry_response = retry_response + "\n\n" + retry_citations_md
                                
                                self.add_assistant_message(retry_response, search_results=self.pending_search_results)
                                self.pending_search_results = []
                                self.current_citation_ids.clear()
                                response = retry_response  # Update for final evaluation
                            else:
                                break  # No search results, stop retrying
                        except Exception as e:
                            LOGGER.warning(f"Auto-retry failed: {e}")
                            break  # Stop retrying on error
                        finally:
                            retries_remaining -= 1
                    else:
                        # Score is acceptable or no retry available
                        break
                
                # 評価処理完了をログに記録
                LOGGER.info(f"Self-evaluation finished: last_evaluation_score set to {self.last_evaluation_score}")
            
            # Decrement the remaining turns and clear if expired
            if self.last_search_turns_remaining > 0:
                self.last_search_turns_remaining -= 1
                if self.last_search_turns_remaining == 0:
                    self.last_search_content = ""

        return stream()

    def search(self, query: str, *, use_reranker: bool = True, previous_keywords: Optional[List[str]] = None, progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None, **kwargs: Any) -> Dict[str, Any]:
        if not self.searxng_client:
            raise RuntimeError("検索機能が有効化されていません")

        # 検索リトライループの初期化
        current_query = query
        search_retry_count = 0
        max_search_retries = 3
        payload = None
        results = []
        all_search_results = []  # Collect all search results including retries

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"検索開始: {query}")

        # 検索リトライループ（最大3回）
        while search_retry_count < max_search_retries:
            try:
                # Build SearXNG parameters
                searxng_params = {}
                if self.searxng_engine:
                    searxng_params["engines"] = self.searxng_engine
                if self.searxng_lang:
                    searxng_params["language"] = self.searxng_lang
                if self.searxng_safesearch:
                    searxng_params["safesearch"] = self.searxng_safesearch
                
                # Merge with user-provided kwargs (user kwargs take precedence)
                searxng_params.update(kwargs)
                
                payload = self.searxng_client.search(current_query, **searxng_params)
                results = payload.get("results", [])
                
                # 結果が空の場合も失敗とみなす
                if not results:
                    raise RuntimeError(f"検索結果が空です: {current_query}")
                
                # 成功した場合はループを抜ける
                logger.info(f"検索成功: {len(results)}件の結果を取得")
                
                # Apply reranker immediately to search results before adding to all_search_results
                if use_reranker and self.reranker is not None:
                    try:
                        reranked_results = self.reranker.rerank(current_query, results)
                        if reranked_results:  # reranked結果がある場合のみ使用
                            results = reranked_results
                    except Exception:
                        # rerank失敗時は元の結果を使用（サイレントフォールバック）
                        pass
                
                # Add citations and accumulate to all_search_results for this attempt
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
                            result["_citation_id"] = citation_id
                            self.current_citation_ids.append(citation_id)
                            
                            # Add to all_search_results immediately
                            citation = self.citation_manager.get_citation(citation_id)
                            all_search_results.append({
                                "title": result.get("title", ""),
                                "url": result.get("url", ""),
                                "snippet": result.get("snippet", ""),
                                "date": result.get("published_date"),
                                "citation_id": citation_id,
                                "relevance_score": result.get("score", 0.5),
                                "credibility_score": citation.get("credibility_score", 0.5)
                            })
                        except Exception:
                            # Citation追加に失敗してもサーチ全体は続行
                            continue
                
                break
                
            except RuntimeError as exc:
                search_retry_count += 1
                failure_reason = self._extract_failure_reason(str(exc))
                logger.warning(f"検索失敗 (試行 {search_retry_count}/{max_search_retries}): {exc}")
                
                # プログレスコールバック: リトライ開始
                if progress_callback:
                    progress_callback("retry_start", {
                        "retry_count": search_retry_count,
                        "max_retries": max_search_retries,
                        "query": current_query,
                        "error": str(exc)
                    })
                
                if search_retry_count >= max_search_retries:
                    # すべてのリトライが失敗
                    logger.error(f"検索が最大リトライ回数に達しました: {query}")
                    # プログレスコールバック: 最終失敗
                    if progress_callback:
                        progress_callback("all_retries_failed", {
                            "query": query,
                            "max_retries": max_search_retries
                        })
                    # 検索失敗をLLMに明示的に通知
                    self.add_system_message(self._get_search_failure_system_message())
                    # 古い引用とクロール状態をクリアして次回答への混入を防止
                    self.current_citation_ids.clear()
                    self.last_search_content = ""
                    self.last_search_turns_remaining = 0
                    return {
                        "formatted": "",
                        "raw": {},
                        "results": [],
                        "search_failed": True
                    }
                
                # 検索失敗専用のリトライクエリを生成
                if self.agent:
                    current_query = self.agent.generate_search_retry_query(
                        query,
                        failure_reason=failure_reason,
                        retry_count=search_retry_count
                    )
                    logger.info(f"代替クエリで再試行 (試行 {search_retry_count}/{max_search_retries}): {current_query}")
                    # プログレスコールバック: 代替クエリ生成
                    if progress_callback:
                        progress_callback("query_generated", {
                            "retry_count": search_retry_count,
                            "new_query": current_query,
                            "failure_reason": failure_reason,
                            "max_retries": max_search_retries
                        })
                else:
                    # agentがない場合は元のクエリで再試行
                    logger.warning("Agentが設定されていないため、元のクエリで再試行します")
                
                # プログレスコールバック: リトライ試行前
                if progress_callback:
                    progress_callback("retry_attempt", {
                        "retry_count": search_retry_count,
                        "query": current_query
                    })
        
        # Crawl top URLs to extract content for RAG context and update citations
        self.last_search_content = ""
        self.last_search_turns_remaining = 0  # Reset turns counter
        crawl_result = None
        
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
                
                # Retry logic if success rate is low and agent is available
                if crawl_result["success_rate"] < 0.5 and self.agent and crawl_result["failed_domains"]:
                    logger.info("Low success rate (%.1f%%), attempting retry searches...", crawl_result["success_rate"] * 100)
                    
                    # Result consolidation: preserve URL-less results and deduplicate URL-bearing items
                    url_less_results = [r for r in results if not r.get("url")]
                    all_results = {r.get("url"): r for r in results if r.get("url")}
                    retry_count = 0
                    max_retries = 3
                    
                    while retry_count < max_retries and crawl_result["success_rate"] < 0.5:
                        retry_count += 1
                        retry_query = self.agent.generate_retry_query(
                            query, crawl_result["failed_domains"], previous_keywords or []
                        )
                        logger.info("Retry %d/%d with query: %s", retry_count, max_retries, retry_query)
                        
                        # Retry search
                        try:
                            # Build SearXNG parameters (same as main search loop)
                            retry_searxng_params = {}
                            if self.searxng_engine:
                                retry_searxng_params["engines"] = self.searxng_engine
                            if self.searxng_lang:
                                retry_searxng_params["language"] = self.searxng_lang
                            if self.searxng_safesearch:
                                retry_searxng_params["safesearch"] = self.searxng_safesearch
                            
                            # Merge with user-provided kwargs (user kwargs take precedence)
                            retry_searxng_params.update(kwargs)
                            
                            retry_payload = self.searxng_client.search(retry_query, **retry_searxng_params)
                            retry_results = retry_payload.get("results", [])
                            
                            # Apply reranker to retry results
                            if use_reranker and self.reranker is not None:
                                try:
                                    reranked = self.reranker.rerank(retry_query, retry_results)
                                    if reranked:
                                        retry_results = reranked
                                except Exception:
                                    pass
                            
                            # Deduplicate and consolidate results by URL
                            for r in retry_results:
                                if r.get("url") and r["url"] not in all_results:
                                    all_results[r["url"]] = r
                                    
                                    # Add citation and accumulate to all_search_results for retry attempt
                                    if self.citation_manager and "_citation_id" not in r:
                                        try:
                                            citation_id = self.citation_manager.add_citation(
                                                url=r.get("url", ""),
                                                title=r.get("title", ""),
                                                snippet=r.get("snippet", ""),
                                                date_str=r.get("published_date"),
                                                relevance_score=r.get("score", 0.5),
                                            )
                                            r["_citation_id"] = citation_id
                                            self.current_citation_ids.append(citation_id)
                                            
                                            # Add to all_search_results for this retry attempt
                                            citation = self.citation_manager.get_citation(citation_id)
                                            all_search_results.append({
                                                "title": r.get("title", ""),
                                                "url": r.get("url", ""),
                                                "snippet": r.get("snippet", ""),
                                                "date": r.get("published_date"),
                                                "citation_id": citation_id,
                                                "relevance_score": r.get("score", 0.5),
                                                "credibility_score": citation.get("credibility_score", 0.5)
                                            })
                                        except Exception:
                                            pass
                            
                            # Retry crawl
                            if self.web_crawler:
                                retry_crawl = self.web_crawler.crawl_results(list(all_results.values()), max_urls=5)
                                crawl_result = retry_crawl  # Update with latest success rate
                                crawled_content = retry_crawl["content"]  # Update with consolidated crawl content
                                logger.info("Retry %d success rate: %.1f%%", retry_count, crawl_result["success_rate"] * 100)
                        except Exception as exc:
                            logger.warning("Retry %d failed: %s", retry_count, exc)
                    
                    # Reflect consolidated results back to results list (URL-bearing + URL-less)
                    results = list(all_results.values()) + url_less_results
                    logger.info("Final integrated results: %d items", len(results))

                
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
        
        # Update payload with consolidated results
        if self.web_crawler and crawl_result and crawl_result["success_rate"] < 0.5:
            # If retry happened, update payload results field
            payload["results"] = results
        
        formatted = self._format_search_results(query, results)
        self.add_system_message(formatted, search_result=True)
        return {
            "formatted": formatted, 
            "raw": payload.get("raw", payload) if payload else {}, 
            "results": results,
            "all_search_results": all_search_results,
            "search_failed": False
        }

    def auto_search(self, query: str, progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        if not self.agent:
            raise RuntimeError("Agentが設定されていません")

        analysis = self.agent.analyze_query(query)
        if not analysis.get("needs_search"):
            return {"searched": False, "formatted": "", "results": [], "analysis": analysis, "search_failed": False}

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
        
        search_result = self.search(search_query, previous_keywords=keywords, progress_callback=progress_callback)
        
        # 検索失敗時の処理
        if search_result.get("search_failed", False):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"自動検索が失敗しました: {query}")
            # 注: search()が既に失敗メッセージを追加しているため、ここでは追加しない
            return {
                "searched": False,
                "formatted": "",
                "results": [],
                "all_search_results": [],
                "analysis": analysis,
                "search_failed": True
            }
        
        return {
            "searched": True,
            "formatted": search_result["formatted"],
            "results": search_result["results"],
            "all_search_results": search_result.get("all_search_results", []),
            "analysis": analysis,
            "search_failed": False
        }

    def _extract_failure_reason(self, error_message: str) -> str:
        """
        エラーメッセージから検索失敗の原因を抽出
        
        Args:
            error_message: エラーメッセージ文字列
        
        Returns:
            失敗原因を示す文字列（"timeout", "connection_error", "http_error", "parse_error", "empty_results", "unknown"）
        """
        error_lower = error_message.lower()
        
        if "timeout" in error_lower or "timed out" in error_lower:
            return "timeout"
        elif "connection" in error_lower or "接続" in error_message:
            return "connection_error"
        elif "http" in error_lower or "status" in error_lower or "403" in error_message or "500" in error_message:
            return "http_error"
        elif "parse" in error_lower or "html" in error_lower or "パース" in error_message:
            return "parse_error"
        elif "empty" in error_lower or "見つかりません" in error_message or "結果が空" in error_message:
            return "empty_results"
        else:
            return "unknown"
    
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

    def get_current_model(self) -> str:
        """Get the current model name from ollama_client."""
        return self.ollama_client.model if self.ollama_client else "unknown"

    def get_last_evaluation_score(self) -> Optional[Dict[str, Any]]:
        """Get the last evaluation score from self_evaluate().
        
        Returns:
            Dict with keys: accuracy_score, freshness_score, overall_score, reasoning
            or None if no evaluation has been performed yet.
        """
        return self.last_evaluation_score

    def self_evaluate(self, query: str, response: str) -> Dict[str, Any]:
        """Evaluate response quality using LLM self-evaluation with source injection.
        
        Injects last_search_content (crawled sources) into evaluation prompt
        to ensure evaluation is based on actual sources, not training data.
        Uses separate evaluation model if configured, otherwise uses response model.
        
        Args:
            query: Original user query
            response: Generated assistant response
            
        Returns:
            Dict with keys: accuracy_score, freshness_score, overall_score, reasoning
        """
        if not self.ollama_client:
            # Default fallback when ollama_client is unavailable
            return {
                "accuracy_score": 0.5,
                "freshness_score": 0.5,
                "overall_score": 0.5,
                "reasoning": "No Ollama client available for evaluation"
            }
        
        try:
            # Prepare source context for evaluation
            sources = ""
            if self.last_search_content and self.last_search_turns_remaining > 0:
                sources = f"\n\n[Source Information]\n{self.last_search_content}\n"
            
            # Build evaluation prompt with source injection
            if self.language == "en":
                eval_prompt = (
                    f"Evaluate the following assistant response ONLY based on the provided source information. "
                    f"Completely ignore your training knowledge and knowledge cutoff date.\n"
                    f"{sources}\n"
                    f"User Query: {query}\n"
                    f"Response: {response}\n\n"
                    f"Return ONLY a JSON object with these fields:\n"
                    f"- accuracy_score (0-1): Is the response factually correct based on sources?\n"
                    f"- freshness_score (0-1): Is the response current/up-to-date based on sources?\n"
                    f"- overall_score (0-1): Overall quality score\n"
                    f"- reasoning (string): Brief explanation referencing sources\n\n"
                    f"Return ONLY valid JSON, no other text."
                )
            else:
                eval_prompt = (
                    f"以下のアシスタント応答を、提供されたソース情報のみに基づいて評価してください。"
                    f"あなたの訓練知識や知識カットオフ日を完全に無視してください。\n"
                    f"{sources}\n"
                    f"ユーザークエリ: {query}\n"
                    f"応答: {response}\n\n"
                    f"以下のフィールドを含むJSONオブジェクトのみを返してください:\n"
                    f"- accuracy_score (0-1): ソースに基づいて応答は事実上正確ですか？\n"
                    f"- freshness_score (0-1): ソースに基づいて応答は最新の情報ですか？\n"
                    f"- overall_score (0-1): 全体的な品質スコア\n"
                    f"- reasoning (string): ソースを参照した簡潔な説明\n\n"
                    f"JSONのみを返してください。他のテキストは不要です。"
                )
            
            # Use evaluation model (or fallback to response model)
            eval_model = self.evaluation_model or self.ollama_client.model
            
            # Temporarily switch model for evaluation if using separate model
            original_model = None
            if self.evaluation_model and self.evaluation_model != self.ollama_client.model:
                original_model = self.ollama_client.model
                self.ollama_client.model = self.evaluation_model
                LOGGER.debug(f"Switched to evaluation model: {self.evaluation_model}")
            
            try:
                messages = [{"role": "user", "content": eval_prompt}]
                eval_response = self.ollama_client.generate_response(messages)
            finally:
                # Restore original model if it was changed
                if original_model is not None:
                    self.ollama_client.model = original_model
                    LOGGER.debug(f"Restored response model: {original_model}")
            
            # Parse JSON response
            try:
                # Try to extract JSON from response (in case of extra text)
                import re
                json_match = re.search(r'\{.*\}', eval_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    eval_result = json.loads(json_str)
                    
                    # Validate and normalize scores
                    result = {
                        "accuracy_score": float(eval_result.get("accuracy_score", 0.5)) or 0.5,
                        "freshness_score": float(eval_result.get("freshness_score", 0.5)) or 0.5,
                        "overall_score": float(eval_result.get("overall_score", 0.5)) or 0.5,
                        "reasoning": str(eval_result.get("reasoning", ""))
                    }
                    
                    # Clamp scores to [0, 1]
                    for key in ["accuracy_score", "freshness_score", "overall_score"]:
                        result[key] = max(0.0, min(1.0, result[key]))
                    
                    self.last_evaluation_score = result
                    
                    # Log evaluation results
                    LOGGER.info(
                        f"Self-evaluation completed (model={eval_model}, sources={'yes' if sources else 'no'}): "
                        f"accuracy={result['accuracy_score']:.2f}, "
                        f"freshness={result['freshness_score']:.2f}, "
                        f"overall={result['overall_score']:.2f} | "
                        f"reasoning: {result['reasoning'][:100]}"
                    )
                    
                    return result
                else:
                    raise ValueError("No JSON found in response")
            except (json.JSONDecodeError, ValueError) as e:
                LOGGER.warning(f"Failed to parse evaluation JSON: {e}")
                # Safe default fallback
                default = {
                    "accuracy_score": 0.5,
                    "freshness_score": 0.5,
                    "overall_score": 0.5,
                    "reasoning": "Evaluation parse error"
                }
                self.last_evaluation_score = default
                return default
        
        except Exception as e:
            LOGGER.warning(f"Self-evaluation failed: {e}")
            default = {
                "accuracy_score": 0.5,
                "freshness_score": 0.5,
                "overall_score": 0.5,
                "reasoning": "Evaluation error"
            }
            self.last_evaluation_score = default
            return default

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

