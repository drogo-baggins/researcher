import argparse
import json
import os
import sys
import re
from researcher.agent import QueryAgent
from researcher.chat_manager import ChatManager
from researcher.citation_manager import CitationManager
from researcher.config import (
    ensure_ollama_running,
    ensure_searxng_running,
    get_auto_search_default,
    get_embedding_model,
    get_mcp_servers_config,
    get_relevance_threshold,
    get_searxng_url,
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


def main():
    parser = argparse.ArgumentParser(description="OllamaローカルLLM CLIチャット")
    parser.add_argument("--model", default=None, help="使用するモデル名 (デフォルト: 環境変数OLLAMA_MODELまたはgpt-oss:20b)")
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
    args = parser.parse_args()

    # モデル名の解決（CLI引数 > 環境変数 > デフォルト）
    if args.model is None:
        args.model = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")

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
        client, searxng_client=searxng_client, agent=agent, reranker=reranker, mcp_client=mcp_client, citation_manager=citation_manager, web_crawler=web_crawler, language=agent_language
    )
    chat.add_system_message("You are a helpful assistant.")

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
                    try:
                        search_result = chat.search(query)
                        print(search_result["formatted"])
                    except RuntimeError as exc:
                        print(f"[ERROR] 検索に失敗しました: {exc}")
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
                    try:
                        auto_result = chat.auto_search(user_input)
                        if auto_result.get("searched"):
                            print(auto_result["formatted"])
                    except RuntimeError as exc:
                        print(f"[WARN] 自動検索に失敗しました: {exc}")
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
        except KeyboardInterrupt:
            print("\n[終了]")
    finally:
        if mcp_client:
            mcp_client.cleanup()
