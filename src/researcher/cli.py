import argparse
import json
import os
import sys
import re
from pathlib import Path
from typing import Any, Dict
from researcher.agent import QueryAgent
from researcher.chat_manager import ChatManager
from researcher.citation_manager import CitationManager
from researcher.session_manager import SessionManager
from researcher.config import (
    ensure_ollama_running,
    ensure_searxng_running,
    get_auto_search_default,
    get_embedding_model,
    get_evaluation_model,
    get_mcp_servers_config,
    get_relevance_threshold,
    get_searxng_url,
    save_feedback,
    get_feedback_stats,
)
from researcher.ollama_client import OllamaClient
from researcher.reranker import EmbeddingReranker
from researcher.searxng_client import SearXNGClient
from researcher.web_crawler import WebCrawler


def detect_language_from_text(text: str) -> str:
    """
    Detect language from text: 'ja' for Japanese, 'en' for English.
    Returns 'ja' if Japanese characters (Hiragana/Katakana/Kanji) are found,
    otherwise returns 'en'.
    """
    # Count CJK unified ideographs (Kanji) and Hiragana/Katakana
    cjk_count = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))
    
    # If more than 10% of characters are CJK, consider it Japanese
    if text and (cjk_count / len(text) > 0.1):
        return "ja"
    return "en"


def display_search_results_table(search_results: list, language: str = "ja") -> None:
    """
    Display search results in a formatted table.
    
    Args:
        search_results: List of search result dicts with title, url, snippet, date, relevance_score, credibility_score
        language: Language for headers ('ja' or 'en')
    """
    if not search_results:
        return
    
    # Try to use tabulate if available, otherwise manual formatting
    try:
        from tabulate import tabulate
        use_tabulate = True
    except ImportError:
        use_tabulate = False
    
    # Prepare headers
    if language == "ja":
        headers = ["#", "タイトル", "URL", "スニペット", "日付", "関連性", "信頼性"]
    else:
        headers = ["#", "Title", "URL", "Snippet", "Date", "Relevance", "Credibility"]
    
    # Prepare table data
    table_data = []
    for idx, result in enumerate(search_results, 1):
        title = result.get("title", "N/A")
        title_display = title[:50] + "..." if len(title) > 50 else title
        
        url = result.get("url", "")
        url_display = url[:40] + "..." if len(url) > 40 else url
        
        snippet = result.get("snippet", "")
        snippet_display = snippet[:100] + "..." if len(snippet) > 100 else snippet
        
        date = result.get("date", "N/A")
        if date and date != "N/A":
            # Format date to YYYY-MM-DD if ISO format
            try:
                date_display = date.split("T")[0]
            except:
                date_display = str(date)[:10]
        else:
            date_display = "N/A"
        
        relevance = result.get("relevance_score", 0.0)
        credibility = result.get("credibility_score", 0.0)
        
        table_data.append([
            idx,
            title_display,
            url_display,
            snippet_display,
            date_display,
            f"{relevance:.2f}",
            f"{credibility:.2f}"
        ])
    
    # Display table
    if use_tabulate:
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        # Manual formatting
        col_widths = [3, 50, 40, 100, 10, 8, 8]
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        separator = "-+-".join("-" * w for w in col_widths)
        
        print(header_line)
        print(separator)
        for row in table_data:
            row_line = " | ".join(str(cell).ljust(w) for cell, w in zip(row, col_widths))
            print(row_line)


def main():
    parser = argparse.ArgumentParser(description="OllamaローカルLLM CLIチャット")
    parser.add_argument("--model", default=None, help="使用するモデル名 (デフォルト: 環境変数OLLAMA_MODELまたは設定ファイル)")
    parser.add_argument("--stream", action="store_true", help="ストリーミングモードで応答")
    parser.add_argument("--no-stream", action="store_true", help="ストリーミングモードを無効化（出力を一度に返す）")
    parser.add_argument(
        "--searxng-url",
        dest="searxng_url",
        help="SearXNGサーバーのURL (デフォルト: 環境変数SEARXNG_URLまたはhttp://localhost:8888)",
        default=None,
    )
    parser.add_argument(
        "--auto-search",
        action="store_true",
        help="QueryAgent による自動検索判断を有効化する",
    )
    parser.add_argument(
        "--auto-search-default",
        action="store_true",
        help="自動検索をデフォルトで有効化（Perplexity UX再現）。無効化するには --no-auto-search を使用",
    )
    parser.add_argument(
        "--no-auto-search",
        action="store_true",
        help="自動検索を無効化（--auto-search-default 使用時）",
    )
    parser.add_argument(
        "--embedding-model", help="埋め込みモデル名 (デフォルト: nomic-embed-text)", default=None
    )
    parser.add_argument(
        "--relevance-threshold",
        type=float,
        help="埋め込み再ランクの関連性閾値 (デフォルト: 0.5)",
        default=None,
    )
    parser.add_argument(
        "--agent-language",
        choices=["ja", "en"],
        help="QueryAgent の言語 (デフォルト: ja、環境変数: AGENT_LANGUAGE)",
        default=None,
    )
    parser.add_argument(
        "--mcp-config",
        help="MCPサーバー設定（JSON文字列またはファイルパス）",
        default=None,
    )
    parser.add_argument(
        "--enable-mcp",
        action="store_true",
        help="MCP機能を有効化（デフォルト設定を使用）",
    )
    parser.add_argument(
        "--enable-self-eval",
        action="store_true",
        help="LLM自己評価と自動再検索を有効化（品質向上ループ）",
    )
    parser.add_argument(
        "--evaluation-model",
        type=str,
        default=None,
        help="評価専用のOllamaモデル名（例: llama3.2:3b）。未指定時は回答生成と同じモデルを使用",
    )
    args = parser.parse_args()

    # モデル名の解決（CLI引数 > 環境変数 > 設定ファイル）
    if args.model is None:
        from researcher.config import load_settings
        settings = load_settings()
        args.model = os.environ.get("OLLAMA_MODEL") or settings.get("response_model")

    # ===========================================================================
    # サービスの自動起動と初期化
    # ===========================================================================
    
    print("🚀 サービスを初期化中...")
    
    # Ollamaの自動起動
    print("  🤖 Ollamaの起動確認中...", end=" ", flush=True)
    if ensure_ollama_running():
        print("✓")
    else:
        print("✗")
        print("[ERROR] Ollamaサーバーを起動できません。")
        print("  手動起動: ollama serve")
        sys.exit(1)
    
    # SearXNGの自動起動
    print("  🔍 SearXNGの起動確認中...", end=" ", flush=True)
    if ensure_searxng_running():
        print("✓")
    else:
        print("✗")
        print("[WARN] SearXNGを起動できません。検索機能なしで続行します。")
    
    print()

    client = OllamaClient(model=args.model)
    try:
        ok = client.test_connection()
        if not ok:
            print("[ERROR] Ollamaの応答が無効または不完全です。サーバーが起動しているか、モデル名が正しいか確認してください。")
            print("ヒント: `ollama serve` を実行し、必要なら `ollama pull` でモデルを取得してください。")
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Ollamaサーバーに接続できません: {e}")
        print("Ollamaサーバーを起動してください: `ollama serve`。モデル名も確認してください。")
        sys.exit(1)

    searxng_client = None
    searxng_url = get_searxng_url(args.searxng_url)
    try:
        candidate = SearXNGClient(searxng_url)
        try:
            ok_search = candidate.test_connection()
            if ok_search:
                searxng_client = candidate
            else:
                print("[WARN] SearXNGの応答が無効または不完全です。検索機能は無効化されています。")
        except Exception as exc:
            print(f"[WARN] SearXNG接続テスト中にエラー: {exc}")
    except Exception as exc:
        print(f"[WARN] SearXNG検索エンジンに接続できません: {exc}")
    embedding_model = get_embedding_model(args.embedding_model)
    threshold = get_relevance_threshold(args.relevance_threshold)
    reranker = EmbeddingReranker(client, model=embedding_model, threshold=threshold)
    
    # 言語設定: CLI引数 > 環境変数 > デフォルト(ja) > 最初の入力から自動判定
    agent_language = args.agent_language
    language_explicitly_set = agent_language is not None  # Track if user explicitly set language
    if agent_language is None:
        agent_language = os.environ.get("AGENT_LANGUAGE")
        if agent_language is None:
            agent_language = "ja"  # Will be auto-detected from first user input
    # 不正な値のフォールバック
    if agent_language not in ("ja", "en"):
        agent_language = "ja"
    
    # 自動検索設定: CLI引数 > 環境変数 > デフォルト
    auto_default = args.auto_search_default or get_auto_search_default()
    auto_search_enabled = (args.auto_search or auto_default) and not args.no_auto_search
    if auto_search_enabled and searxng_client is None:
        print("[WARN] SearXNGが利用できないため、自動検索モードを無効化します。")
        auto_search_enabled = False
    
    # Agent作成: auto_search_enabledから分離。SearXNGが利用可能なら常に作成
    # これにより、manual /search コマンドでも retry ロジックが使用可能になる
    agent = QueryAgent(client, language=agent_language) if searxng_client else None

    mcp_client = None
    if args.enable_mcp or args.mcp_config:
        servers_config = get_mcp_servers_config(args.mcp_config)
        try:
            from researcher.mcp_client import MCPClient

            candidate_mcp = MCPClient(servers_config)
            connection_status = candidate_mcp.connect_servers()
            if any(connection_status.values()):
                mcp_client = candidate_mcp
                print(f"[INFO] MCP接続成功: {[k for k, v in connection_status.items() if v]}")
            else:
                print("[WARN] すべてのMCPサーバーへの接続に失敗しました")
        except ImportError:
            print("[WARN] mcp パッケージがインストールされていません。MCP機能は無効化されています。")
        except Exception as exc:
            print(f"[WARN] MCP初期化エラー: {exc}")

    citation_manager = CitationManager()
    
    # Initialize web crawler for RAG layer
    web_crawler = WebCrawler() if searxng_client else None

    chat = ChatManager(
        client,
        searxng_client=searxng_client,
        agent=agent,
        reranker=reranker,
        mcp_client=mcp_client,
        citation_manager=citation_manager,
        web_crawler=web_crawler,
        language=agent_language,
        enable_self_evaluation=args.enable_self_eval,
        evaluation_model=get_evaluation_model(args.evaluation_model),
    )
    chat.add_system_message("You are a helpful assistant.")
    
    # Initialize SessionManager for persisting evaluation scores
    session_manager = SessionManager()
    current_session_id = None
    
    # Try to load the most recent session on startup
    sessions = session_manager.list_sessions()
    if sessions:
        # Load the most recent session
        most_recent = sessions[0]
        session_data = session_manager.load_session(most_recent["id"])
        if session_data:
            current_session_id = most_recent["id"]
            chat.messages = session_data["history"]
            # Restore evaluation score if available
            if "last_evaluation_score" in session_data and session_data["last_evaluation_score"]:
                chat.last_evaluation_score = session_data["last_evaluation_score"]
            print(f"[セッション復元] ID: {current_session_id}, メッセージ数: {len(session_data['history'])}")
    
    # Create a new session if none exist or for tracking new interaction
    if current_session_id is None:
        try:
            from datetime import datetime
            session_name = f"CLI Session {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        except:
            session_name = "CLI Session"
        current_session_id = session_manager.create_session(session_name)
        if current_session_id:
            print(f"[新規セッション作成] ID: {current_session_id}")

    print("researcher CLI (Ollama)")
    print("/exit で終了, /clear で履歴クリア, /history で履歴表示, /search <query> でSearXNG検索")
    print("/blacklist [show|add|clear] でドメインブラックリスト管理")
    print("/status でOllama/SearXNG接続確認")
    if auto_search_enabled:
        print("自動検索モード: 有効（最新情報が必要な質問を自動検知）")
    if mcp_client:
        print("/mcp <tool_name> [args_json] でMCPツール実行, /mcp-tools でツール一覧表示")
    try:
        try:
            first_input = True
            while True:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                
                # Auto-detect language from first user input if not explicitly set
                if first_input and not language_explicitly_set and os.environ.get("AGENT_LANGUAGE") is None:
                    detected_language = detect_language_from_text(user_input)
                    if detected_language != agent_language and agent is not None:
                        agent_language = detected_language
                        # Update agent with new language
                        agent = QueryAgent(client, language=agent_language)
                        chat.agent = agent
                first_input = False
                
                if user_input == "/exit":
                    print("Bye!")
                    break
                elif user_input == "/clear":
                    chat.clear_history()
                    print("[履歴クリア]")
                    continue
                elif user_input == "/history":
                    for m in chat.get_history():
                        print(f"[{m['role']}] {m['content']}")
                    continue
                elif user_input == "/status" or user_input == "/sync-status":
                    # Handle /sync-status as deprecated alias for backward compatibility
                    if user_input == "/sync-status":
                        # Deprecated: /sync-status is an alias for /status (Ollama/SearXNG only)
                        pass
                    
                    print("[接続ステータス確認]")
                    # Ollama connection check
                    try:
                        ollama_ok = client.test_connection()
                        print(f"  Ollama: {'✓ 接続OK' if ollama_ok else '✗ 接続失敗'}")
                    except Exception:
                        print("  Ollama: ✗ 接続失敗")
                    
                    # SearXNG connection check
                    if searxng_client:
                        try:
                            searxng_ok = searxng_client.test_connection()
                            print(f"  SearXNG: {'✓ 接続OK' if searxng_ok else '✗ 接続失敗'}")
                        except Exception:
                            print("  SearXNG: ✗ 接続失敗")
                    else:
                        print("  SearXNG: - 未設定")
                    
                    continue
                elif user_input.startswith("/search"):
                    query = user_input[len("/search"):].strip()
                    if not query:
                        print("使用法: /search <query>")
                        continue
                    
                    def search_progress_callback(event: str, data: Dict[str, Any]) -> None:
                        """検索リトライの進行状況を表示"""
                        if event == "retry_start":
                            print(f"[検索失敗] 試行 {data['retry_count']}/{data['max_retries']}: {data.get('error', '')[:100]}")
                        elif event == "query_generated":
                            print(f"[代替クエリ生成] 試行 {data['retry_count']}: {data['new_query']}")
                        elif event == "retry_attempt":
                            print(f"[再試行中] 試行 {data['retry_count']}: {data['query'][:100]}")
                        elif event == "all_retries_failed":
                            print(f"[検索失敗] すべてのリトライが失敗しました（最大{data['max_retries']}回）")
                    
                    try:
                        search_result = chat.search(query, progress_callback=search_progress_callback)
                        print(search_result["formatted"])
                        
                        # Display detailed search results table
                        all_search_results = search_result.get("all_search_results", [])
                        if all_search_results:
                            print("\n[検索結果詳細]")
                            display_search_results_table(all_search_results, language=agent_language)
                    except RuntimeError as exc:
                        print(f"[ERROR] 検索に失敗しました: {exc}")
                        print("[ヒント] SearXNGサーバーの状態を確認してください: /status")
                    continue
                elif user_input.startswith("/blacklist"):
                    if not web_crawler:
                        print("[ERROR] WebCrawler機能が有効化されていません")
                        continue
                    
                    parts = user_input.split(maxsplit=2)
                    subcommand = parts[1] if len(parts) > 1 else "show"
                    
                    if subcommand in ("show", "list"):
                        if web_crawler.blacklist_domains:
                            print("[ブラックリストドメイン]")
                            for domain in sorted(web_crawler.blacklist_domains):
                                print(f"  - {domain}")
                        else:
                            print("[ブラックリストは空です]")
                    
                    elif subcommand == "add":
                        if len(parts) < 3:
                            print("使用法: /blacklist add <domain>")
                            continue
                        target = parts[2].strip()
                        if not target:
                            print("ドメイン名を指定してください")
                            continue
                        
                        # Normalize domain from URL or domain string
                        from urllib.parse import urlparse
                        from researcher.web_crawler import normalize_domain
                        if "://" in target or "/" in target:
                            # Parse as URL
                            parsed = urlparse(target if "://" in target else f"http://{target}")
                            normalized_domain = normalize_domain(parsed.netloc)
                        else:
                            normalized_domain = normalize_domain(target)
                        
                        if not normalized_domain:
                            print("ドメイン名を指定してください")
                            continue
                        
                        web_crawler.add_to_blacklist(normalized_domain)
                        print(f"[ブラックリストに追加: {normalized_domain}]")
                    
                    elif subcommand == "clear":
                        confirm = input("ブラックリストをクリアしますか？ (yes/no): ").strip().lower()
                        if confirm in ("yes", "y"):
                            web_crawler.blacklist_domains.clear()
                            from researcher.config import save_blacklist_domains
                            save_blacklist_domains(web_crawler.blacklist_domains)
                            print("[ブラックリストをクリアしました]")
                        else:
                            print("[キャンセルしました]")
                    
                    else:
                        print("使用法: /blacklist [show|add <domain>|clear]")
                    
                    continue
                elif user_input.startswith("/feedback"):
                    parts = user_input.split(maxsplit=1)
                    subcommand = parts[1].strip() if len(parts) > 1 else "help"
                    
                    if subcommand in ("thumbs_up", "up"):
                        if chat.messages and any(m.get("role") == "assistant" for m in chat.messages):
                            # Get last user query and assistant response
                            user_msg = ""
                            assistant_msg = ""
                            for msg in reversed(chat.messages):
                                if msg.get("role") == "assistant" and not assistant_msg:
                                    assistant_msg = msg.get("content", "")
                                elif msg.get("role") == "user" and not user_msg:
                                    user_msg = msg.get("content", "")
                                if user_msg and assistant_msg:
                                    break
                            
                            model = chat.get_current_model()
                            success = save_feedback(user_msg, assistant_msg, "up", model)
                            if success:
                                print("[👍 フィードバックを保存しました (thumbs_up)]")
                            else:
                                print("[ERROR] フィードバック保存に失敗しました")
                        else:
                            print("[ERROR] 回答がまだありません")
                    
                    elif subcommand in ("thumbs_down", "down"):
                        if chat.messages and any(m.get("role") == "assistant" for m in chat.messages):
                            # Get last user query and assistant response
                            user_msg = ""
                            assistant_msg = ""
                            for msg in reversed(chat.messages):
                                if msg.get("role") == "assistant" and not assistant_msg:
                                    assistant_msg = msg.get("content", "")
                                elif msg.get("role") == "user" and not user_msg:
                                    user_msg = msg.get("content", "")
                                if user_msg and assistant_msg:
                                    break
                            
                            model = chat.get_current_model()
                            success = save_feedback(user_msg, assistant_msg, "down", model)
                            if success:
                                print("[👎 フィードバックを保存しました (thumbs_down)]")
                            else:
                                print("[ERROR] フィードバック保存に失敗しました")
                        else:
                            print("[ERROR] 回答がまだありません")
                    
                    elif subcommand.startswith("stats"):
                        stats_parts = subcommand.split()
                        model_filter = stats_parts[1] if len(stats_parts) > 1 else None
                        
                        stats = get_feedback_stats(model_filter=model_filter)
                        print("\n[フィードバック統計]")
                        if model_filter:
                            print(f"  モデル: {model_filter}")
                            print(f"  👎率: {stats.get('thumbs_down_rate', 0):.2%}")
                            print(f"  👎数: {stats.get('thumbs_down_count', 0)}/{stats.get('total_count', 0)}")
                        else:
                            print(f"  全体 👎率: {stats.get('thumbs_down_rate', 0):.2%}")
                            print(f"  👎数: {stats.get('thumbs_down_count', 0)}/{stats.get('total_count', 0)}")
                            
                            if stats.get('by_model'):
                                print("\n  モデル別統計:")
                                for model_name, model_stats in stats.get('by_model', {}).items():
                                    print(f"    {model_name}: 👎率 {model_stats.get('thumbs_down_rate', 0):.2%} ({model_stats.get('thumbs_down_count', 0)}/{model_stats.get('total_count', 0)})")
                    
                    else:
                        print("使用法: /feedback [thumbs_up|thumbs_down|stats [model_name]]")
                        print("  thumbs_up      最後の回答が良かったらフィードバック")
                        print("  thumbs_down    最後の回答が悪かったらフィードバック")
                        print("  stats          全体の統計を表示")
                        print("  stats <model>  特定モデルの統計を表示")
                    
                    continue
                elif user_input == "/last_eval":
                    # Display last evaluation score
                    eval_score = chat.get_last_evaluation_score()
                    if eval_score:
                        print("\n[最後の自己評価スコア]")
                        print(f"  正確性スコア: {eval_score.get('accuracy_score', 0):.2f}")
                        print(f"  最新性スコア: {eval_score.get('freshness_score', 0):.2f}")
                        print(f"  総合スコア:   {eval_score.get('overall_score', 0):.2f}")
                        print(f"  理由: {eval_score.get('reasoning', 'N/A')}")
                    else:
                        print("[最後の自己評価スコア]")
                        print("  評価がまだ実行されていません")
                    continue
                elif user_input == "/mcp-tools":
                    if not mcp_client:
                        print("[ERROR] MCP機能が有効化されていません")
                        continue
                    try:
                        tools = mcp_client.list_tools()
                        print("[利用可能なMCPツール]")
                        for tool in tools:
                            print(f"  - {tool['server']}.{tool['name']}: {tool.get('description', '')}")
                    except Exception as exc:
                        print(f"[ERROR] ツールリスト取得失敗: {exc}")
                    continue
                elif user_input.startswith("/mcp"):
                    parts = user_input.split(maxsplit=2)
                    if len(parts) < 2:
                        print("使用法: /mcp <tool_name> [arguments_json]")
                        print("例: /mcp filesystem.read_file '{\"path\": \"/tmp/test.txt\"}'")
                        continue
                    tool_name = parts[1]
                    arguments = {}
                    if len(parts) == 3:
                        try:
                            arguments = json.loads(parts[2])
                        except json.JSONDecodeError:
                            print("[ERROR] 引数は有効なJSON形式である必要があります")
                            continue
                    try:
                        result = chat.execute_mcp_tool(tool_name, arguments)
                        print(result["formatted"])
                    except RuntimeError as exc:
                        print(f"[ERROR] MCPツール実行失敗: {exc}")
                    continue
                if auto_search_enabled:
                    def search_progress_callback(event: str, data: Dict[str, Any]) -> None:
                        """検索リトライの進行状況を表示"""
                        if event == "retry_start":
                            print(f"[検索失敗] 試行 {data['retry_count']}/{data['max_retries']}: {data.get('error', '')[:100]}")
                        elif event == "query_generated":
                            print(f"[代替クエリ生成] 試行 {data['retry_count']}: {data['new_query']}")
                        elif event == "retry_attempt":
                            print(f"[再試行中] 試行 {data['retry_count']}: {data['query'][:100]}")
                        elif event == "all_retries_failed":
                            print(f"[検索失敗] すべてのリトライが失敗しました（最大{data['max_retries']}回）")
                    
                    try:
                        auto_result = chat.auto_search(user_input, progress_callback=search_progress_callback)
                        chat.pending_search_results = auto_result.get("all_search_results", [])
                        if auto_result.get("searched"):
                            print(auto_result["formatted"])
                            
                            # Display detailed search results table
                            all_search_results = auto_result.get("all_search_results", [])
                            if all_search_results:
                                print("\n[検索結果詳細]")
                                display_search_results_table(all_search_results, language=agent_language)
                    except RuntimeError as exc:
                        print(f"[ERROR] 自動検索に失敗しました: {exc}")
                        print("[ヒント] SearXNGサーバーの状態を確認してください: /status")
                    except Exception as exc:
                        print(f"[WARN] 自動検索中に想定外のエラー: {exc}")
                chat.add_user_message(user_input)
                if args.stream and not args.no_stream:
                    for chunk in chat.get_response_stream():
                        print(chunk, end="", flush=True)
                    print()
                else:
                    response = chat.get_response()
                    print(response)
                
                # Save exchange incrementally after each response
                if current_session_id is not None:
                    history = chat.get_history()
                    
                    # Extract last user and assistant messages (incremental save for V2 schema)
                    if len(history) >= 2:
                        last_user = None
                        last_assistant = None
                        search_results = None
                        
                        # Find last user and assistant messages
                        for msg in reversed(history):
                            if msg.get("role") == "assistant" and last_assistant is None:
                                last_assistant = msg.get("content", "")
                                search_results = msg.get("search_results")
                            elif msg.get("role") == "user" and last_user is None:
                                last_user = msg.get("content", "")
                            
                            if last_user and last_assistant:
                                break
                        
                        # Save exchange if both messages found
                        if last_user and last_assistant:
                            eval_score = chat.get_last_evaluation_score()
                            try:
                                session_manager.save_exchange(
                                    session_id=current_session_id,
                                    user_message=last_user,
                                    assistant_message=last_assistant,
                                    model=args.model,
                                    language=agent_language,
                                    search_results=search_results,
                                    evaluation_score=eval_score
                                )
                            except Exception as e:
                                print(f"\n[警告] Exchange保存に失敗しました: {e}")
                            
                            # Display search results used in this exchange
                            if search_results:
                                print("\n[この応答で使用された検索結果]")
                                display_search_results_table(search_results, language=agent_language)
        except KeyboardInterrupt:
            print("\n[終了]")
    finally:
        if mcp_client:
            mcp_client.cleanup()
