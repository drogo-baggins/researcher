from typing import Any, Dict, List, Optional
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
        self.messages = []
        self.current_citation_ids: List[int] = []
        self.last_search_content: str = ""  # Store crawled content from last search
        self.last_search_turns_remaining: int = 0  # Number of turns to keep injecting crawled content
        self.last_evaluation_score: Optional[Dict[str, Any]] = None  # Store latest evaluation score

    def add_system_message(self, content, search_result: bool = False):
        self.messages.append(
            {"role": "system", "content": content, "search_result": search_result}
        )

    def add_user_message(self, content):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content):
        self.messages.append({"role": "assistant", "content": content})

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
        self.add_assistant_message(response)
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
                            self.add_assistant_message(response)
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
            self.add_assistant_message(response)
            self.current_citation_ids.clear()
            
            # Get last user query for evaluation
            last_user_query = None
            for msg in reversed(self.messages[:-1]):  # Exclude newly added assistant message
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
                                
                                self.add_assistant_message(retry_response)
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
            
            # Decrement the remaining turns and clear if expired
            if self.last_search_turns_remaining > 0:
                self.last_search_turns_remaining -= 1
                if self.last_search_turns_remaining == 0:
                    self.last_search_content = ""

        return stream()

    def search(self, query: str, *, use_reranker: bool = True, previous_keywords: Optional[List[str]] = None, **kwargs: Any) -> Dict[str, Any]:
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
                            retry_payload = self.searxng_client.search(retry_query, **kwargs)
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
                    
                    # Ensure all results have citations
                    if self.citation_manager:
                        for result in results:
                            if "_citation_id" not in result:
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
                                except Exception:
                                    # Citation追加に失敗してもサーチ全体は続行
                                    continue

                
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
        
        search_result = self.search(search_query, previous_keywords=keywords)
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
        """Evaluate response quality using LLM self-evaluation with JSON output.
        
        Returns evaluation scores including accuracy_score, freshness_score, overall_score, and reasoning.
        On JSON parse failure, returns safe default values.
        
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
            # Build evaluation prompt
            if self.language == "en":
                eval_prompt = (
                    f"Evaluate the following assistant response for accuracy and freshness.\n"
                    f"Return ONLY a JSON object with these fields:\n"
                    f"- accuracy_score (0-1): Is the response factually correct?\n"
                    f"- freshness_score (0-1): Is the response current/up-to-date?\n"
                    f"- overall_score (0-1): Overall quality score\n"
                    f"- reasoning (string): Brief explanation\n\n"
                    f"User Query: {query}\n"
                    f"Response: {response}\n\n"
                    f"Return ONLY valid JSON, no other text."
                )
            else:
                eval_prompt = (
                    f"以下のアシスタント応答の正確性と最新性を評価してください。\n"
                    f"以下のフィールドを含むJSONオブジェクトをRETURNしてください:\n"
                    f"- accuracy_score (0-1): 応答は事実上正確ですか？\n"
                    f"- freshness_score (0-1): 応答は最新の情報ですか？\n"
                    f"- overall_score (0-1): 全体的な品質スコア\n"
                    f"- reasoning (string): 簡潔な説明\n\n"
                    f"ユーザークエリ: {query}\n"
                    f"応答: {response}\n\n"
                    f"JSONのみを返してください。他のテキストは不要です。"
                )
            
            # Call LLM for evaluation
            messages = [{"role": "user", "content": eval_prompt}]
            eval_response = self.ollama_client.generate_response(messages)
            
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
                        f"Self-evaluation completed: "
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

