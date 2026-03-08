import json
import logging
import os
import subprocess
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_SEARXNG_URL = "http://localhost:8888"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text-v2-moe"
DEFAULT_RELEVANCE_THRESHOLD = (
    0.5  # デフォルト値: run.sh と一致。より高い精度の検索結果を優先
)
DEFAULT_AUTO_SEARCH = False  # デフォルトはOFF、--auto-search-default で有効化
DEFAULT_MCP_SERVERS: Dict[str, Dict[str, Any]] = {
    "filesystem": {
        "command": "node",
        "args": ["/path/to/server-filesystem/build/index.js", "/Users/username"],
        "enabled": False,
    },
    "notes": {
        "command": "node",
        "args": ["/path/to/mcp-apple-notes/build/index.js"],
        "enabled": False,
    },
    "calendar": {
        "command": "node",
        "args": ["/path/to/mcp-ical/index.js"],
        "enabled": False,
    },
}


def get_ollama_base_url(settings: Optional[Dict[str, Any]] = None) -> str:
    """Resolve Ollama base URL in priority: settings > env > default."""
    if settings is not None:
        val = settings.get("ollama_base_url", "").strip()
        if val:
            return val
    env_value = os.environ.get("OLLAMA_URL", "").strip()
    if env_value:
        return env_value
    return DEFAULT_OLLAMA_BASE_URL


def get_searxng_url(cli_arg: Optional[str] = None) -> str:
    """Resolve the SearXNG URL in priority: CLI > env > default."""
    if cli_arg:
        return cli_arg
    env_value = os.environ.get("SEARXNG_URL")
    if env_value:
        return env_value
    return DEFAULT_SEARXNG_URL


def get_embedding_model(cli_arg: Optional[str] = None) -> str:
    """Resolve embedding model name: CLI > env > default."""
    if cli_arg:
        return cli_arg
    env_value = os.environ.get("EMBEDDING_MODEL")
    if env_value:
        return env_value
    return DEFAULT_EMBEDDING_MODEL


def get_evaluation_model(cli_arg: Optional[str] = None) -> Optional[str]:
    """Resolve evaluation model name: CLI > env > None (use response model).

    Returns None to use the same model as response generation.
    Recommended: lightweight accurate model for faster evaluation.
    """
    if cli_arg:
        return cli_arg
    env_value = os.environ.get("EVALUATION_MODEL")
    if env_value:
        return env_value
    return None  # Use response generation model by default


def get_relevance_threshold(cli_arg: Optional[float] = None) -> float:
    """Resolve relevance threshold: CLI > env > default (0.5).

    The default is 0.5, which provides a balanced filtering of embedding search results.
    When set to 0.0, all results are returned without filtering.
    Higher values (e.g., 0.8) provide stricter relevance filtering.
    """
    if cli_arg is not None:
        return cli_arg
    env_value = os.environ.get("RELEVANCE_THRESHOLD")
    if env_value:
        try:
            return float(env_value)
        except ValueError:
            logging.warning(
                "RELEVANCE_THRESHOLD must be a float, falling back to default"
            )
    return DEFAULT_RELEVANCE_THRESHOLD


def get_auto_search_default() -> bool:
    """環境変数AUTO_SEARCH_DEFAULTからデフォルト自動検索設定を取得"""
    env_value = os.environ.get("AUTO_SEARCH_DEFAULT", "").lower()
    if env_value in ("true", "1", "yes"):
        return True
    return DEFAULT_AUTO_SEARCH


def _parse_mcp_config_source(
    source_name: str, raw_value: str
) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, dict):
            return parsed
        logging.warning("%s: 期待された辞書形式ではありません", source_name)
    except json.JSONDecodeError:
        path = Path(raw_value).expanduser()
        if path.is_file():
            try:
                file_content = path.read_text()
                parsed = json.loads(file_content)
                if isinstance(parsed, dict):
                    return parsed
                logging.warning(
                    "%s (%s): ファイル内容が辞書形式ではありません", source_name, path
                )
            except Exception as exc:
                logging.warning(
                    "%s (%s)の読み込みに失敗しました: %s", source_name, path, exc
                )
        else:
            logging.warning("%s: JSON もファイルも解釈できませんでした", source_name)
    except Exception as exc:
        logging.warning("%s の処理中にエラーが発生しました: %s", source_name, exc)
    return None


def get_mcp_servers_config(cli_arg: Optional[str] = None) -> Dict[str, Any]:
    """Resolve MCP サーバー設定: CLI > MCP_SERVERS_CONFIG > デフォルト."""
    if cli_arg:
        config = _parse_mcp_config_source("CLI", cli_arg)
        if config is not None:
            return config
    env_value = os.environ.get("MCP_SERVERS_CONFIG")
    if env_value:
        config = _parse_mcp_config_source("MCP_SERVERS_CONFIG", env_value)
        if config is not None:
            return config
    return deepcopy(DEFAULT_MCP_SERVERS)


# ==============================================================================
# サービス自動起動ヘルパー
# ==============================================================================


def ensure_ollama_running() -> bool:
    """Ollamaサーバーが起動していることを確認し、起動していなければ起動"""
    import requests

    ollama_url = get_ollama_base_url()

    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=2)
        if response.status_code == 200:
            return True
    except Exception:
        pass

    # Ollamaが起動していない場合、起動を試みる
    try:
        import platform

        if platform.system() == "Darwin":  # macOS
            # バックグラウンドで起動
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            # 起動待機
            for _ in range(30):
                try:
                    response = requests.get(f"{ollama_url}/api/tags", timeout=1)
                    if response.status_code == 200:
                        return True
                except Exception:
                    time.sleep(1)
    except Exception as e:
        logging.debug(f"Ollamaの自動起動に失敗: {e}")

    return False


def ensure_searxng_running() -> bool:
    """SearXNGへの接続を確認する。

    コンテナの起動は行わず、接続確認のみ。
    JSON API (?format=json) が有効であることも検証する。
    接続不可の場合は scripts/searxng-start.sh の実行を案内する。

    Returns:
        True: SearXNGが起動中かつJSON APIが利用可能
        False: 接続不可またはJSON APIが無効
    """
    import requests

    searxng_url = get_searxng_url().rstrip("/")

    try:
        response = requests.get(f"{searxng_url}/", timeout=3)
        if response.status_code not in (200, 403):
            logging.warning(
                "SearXNG が異常なステータスを返しました: %d", response.status_code
            )
            return False
    except Exception:
        logging.warning(
            "SearXNG に接続できません (%s)。"
            "scripts/searxng-start.sh を実行してコンテナを起動してください。",
            searxng_url,
        )
        return False

    try:
        response = requests.get(
            f"{searxng_url}/search",
            params={"q": "test", "format": "json"},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            if "results" in data or "query" in data:
                return True
            logging.warning("SearXNG JSON API が予期しないレスポンスを返しました")
            return False
        elif response.status_code == 403:
            logging.warning(
                "SearXNG JSON API が 403 Forbidden を返しました。"
                "searxng_settings.yml の search.formats に json が含まれているか確認し、"
                "scripts/searxng-start.sh --force でコンテナを再作成してください。"
            )
            return False
        else:
            logging.warning(
                "SearXNG JSON API がステータス %d を返しました", response.status_code
            )
            return False
    except requests.exceptions.JSONDecodeError:
        logging.warning("SearXNG のレスポンスが有効な JSON ではありません")
        return False
    except Exception as e:
        logging.warning("SearXNG JSON API の確認に失敗: %s", e)
        return False


# Settings persistence configuration
SETTINGS_FILE_PATH = Path.home() / ".researcher" / "settings.json"

DEFAULT_SETTINGS = {
    "ollama_base_url": "",  # 空文字の場合は DEFAULT_OLLAMA_BASE_URL を使用
    "search_model": "",
    "response_model": "",
    "eval_model": "",
    "embedding_model": "nomic-embed-text-v2-moe",
    "searxng_engine": "general",
    "searxng_lang": "ja",
    "searxng_safesearch": "off",
    "ui_text_size": "medium",  # small/medium/large
    # List of OpenAI-compatible provider configurations.
    # Each entry is a dict:
    #   {
    #     "name": str,       # Display name, used as the provider prefix in model keys
    #     "base_url": str,   # API endpoint, e.g. "https://api.venice.ai/api/v1"
    #     "api_key": str,    # Bearer token (stored in plain text locally)
    #     "models": [str],   # Manually configured list of model IDs
    #   }
    "llm_providers": [],
}


def load_settings() -> Dict[str, Any]:
    """Load user settings from JSON file.

    Returns:
        Settings dictionary merged with defaults (missing keys filled from DEFAULT_SETTINGS)
    """
    if not SETTINGS_FILE_PATH.exists():
        return deepcopy(DEFAULT_SETTINGS)

    try:
        with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
            loaded_settings = json.load(f)

            # Merge with defaults (fill missing keys)
            settings = deepcopy(DEFAULT_SETTINGS)
            if isinstance(loaded_settings, dict):
                settings.update(loaded_settings)
            else:
                logging.warning(
                    "設定ファイルの形式が不正です。デフォルト設定を使用します"
                )

            return settings
    except json.JSONDecodeError as e:
        logging.warning(
            f"設定ファイルのJSON解析エラー: {e}。デフォルト設定を使用します"
        )
        return deepcopy(DEFAULT_SETTINGS)
    except Exception as e:
        logging.warning(f"設定ファイル読み込みエラー: {e}。デフォルト設定を使用します")
        return deepcopy(DEFAULT_SETTINGS)


def save_settings(settings: Dict[str, Any]) -> bool:
    """Save user settings to JSON file with atomic write.

    Args:
        settings: Settings dictionary to save

    Returns:
        True if save successful, False otherwise
    """
    try:
        SETTINGS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write using temporary file and os.replace
        temp_fd, temp_path = tempfile.mkstemp(
            prefix=".settings_tmp_",
            suffix=".json",
            dir=SETTINGS_FILE_PATH.parent,
            text=True,
        )

        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)

            # Atomic replace: os.replace is atomic on all platforms
            os.replace(temp_path, SETTINGS_FILE_PATH)
            return True
        except Exception as e:
            # Clean up temp file if something goes wrong
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise e

    except Exception as exc:
        logging.warning(f"設定保存エラー: {exc}")
        return False


# Blacklist persistence configuration
BLACKLIST_FILE_PATH = Path.home() / ".researcher" / "blacklist.json"


def load_blacklist_domains() -> set:
    """Load blacklist domains from JSON file, filtering to string-only entries."""
    if not BLACKLIST_FILE_PATH.exists():
        return set()
    try:
        with open(BLACKLIST_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                domains = set()
                has_invalid_items = False
                for item in data:
                    if isinstance(item, str):
                        cleaned = item.strip()
                        if cleaned:
                            domains.add(cleaned)
                    else:
                        has_invalid_items = True
                if has_invalid_items:
                    logging.warning(
                        "ブラックリスト JSON に無効な型が含まれています。文字列のみを使用します"
                    )
                return domains
    except Exception as exc:
        logging.warning("ブラックリスト読み込みエラー: %s", exc)
    return set()


def save_blacklist_domains(domains: set) -> None:
    """Save blacklist domains to JSON file."""
    try:
        BLACKLIST_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BLACKLIST_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(list(domains)), f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logging.warning("ブラックリスト保存エラー: %s", exc)


# Feedback persistence configuration
FEEDBACK_FILE_PATH = Path.home() / ".researcher" / "feedback.json"


def save_feedback(
    query: str, response: str, rating: str, model: str, session_id: Optional[int] = None
) -> bool:
    """Save feedback record to JSON file with validation and atomic writes.

    Args:
        query: User query
        response: LLM response
        rating: "up" or "down" (must be one of these values)
        model: Model name (must be non-empty)
        session_id: Optional session ID

    Returns:
        True if save successful, False otherwise
    """
    # Input validation
    if rating not in ("up", "down"):
        logging.warning(f"Invalid rating value: {rating}. Must be 'up' or 'down'.")
        return False

    if not model or not model.strip():
        logging.warning("Model name cannot be empty")
        return False

    try:
        FEEDBACK_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Load existing feedback with retry on lock/read failures
        feedback_list = []
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if FEEDBACK_FILE_PATH.exists():
                    with open(FEEDBACK_FILE_PATH, "r", encoding="utf-8") as f:
                        feedback_list = json.load(f)
                break
            except (json.JSONDecodeError, IOError) as e:
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                logging.warning(
                    f"Failed to read feedback file after {max_retries} attempts: {e}"
                )
                feedback_list = []
                break

        # Add new feedback record
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "query": query,
            "response": response,
            "rating": rating,
            "model": model.strip(),
            "session_id": session_id,
        }
        feedback_list.append(record)

        # Sort by timestamp descending
        feedback_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Atomic write using temporary file and os.replace
        import tempfile

        temp_fd, temp_path = tempfile.mkstemp(
            prefix=".feedback_tmp_",
            suffix=".json",
            dir=FEEDBACK_FILE_PATH.parent,
            text=True,
        )

        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(feedback_list, f, indent=2, ensure_ascii=False)

            # Atomic replace: os.replace is atomic on all platforms
            os.replace(temp_path, FEEDBACK_FILE_PATH)
            return True
        except Exception as e:
            # Clean up temp file if something goes wrong
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise e

    except Exception as exc:
        logging.warning(f"フィードバック保存エラー: {exc}")
        return False


def load_feedback_history() -> list:
    """Load feedback history from JSON file with model field compatibility.

    For records missing 'model' field, sets it to 'unknown' for compatibility.
    """
    if not FEEDBACK_FILE_PATH.exists():
        return []
    try:
        with open(FEEDBACK_FILE_PATH, "r", encoding="utf-8") as f:
            feedback_list = json.load(f)
            # Ensure all records have 'model' field for compatibility
            for record in feedback_list:
                if "model" not in record:
                    record["model"] = "unknown"
            return feedback_list
    except Exception as exc:
        logging.warning("フィードバック読み込みエラー: %s", exc)
    return []


def get_feedback_stats(model_filter: Optional[str] = None) -> Dict[str, Any]:
    """Get feedback statistics, optionally filtered by model.

    Args:
        model_filter: Optional model name to filter by

    Returns:
        Dict with statistics:
        {
            "total_count": int,
            "thumbs_down_count": int,
            "thumbs_down_rate": float,
            "by_model": {
                "model_name": {
                    "thumbs_down_rate": float,
                    "total_count": int,
                    "thumbs_down_count": int
                },
                ...
            }
        }
    """
    feedback_list = load_feedback_history()

    if not feedback_list:
        return {
            "total_count": 0,
            "thumbs_down_count": 0,
            "thumbs_down_rate": 0.0,
            "by_model": {},
        }

    # Calculate overall stats
    total_count = len(feedback_list)
    thumbs_down_count = sum(1 for r in feedback_list if r.get("rating") == "down")
    thumbs_down_rate = thumbs_down_count / total_count if total_count > 0 else 0.0

    # Calculate per-model stats
    by_model = {}
    for record in feedback_list:
        model = record.get("model", "unknown")
        if model not in by_model:
            by_model[model] = {
                "total_count": 0,
                "thumbs_down_count": 0,
                "thumbs_down_rate": 0.0,
            }
        by_model[model]["total_count"] += 1
        if record.get("rating") == "down":
            by_model[model]["thumbs_down_count"] += 1

    # Calculate thumbs_down_rate for each model
    for model_stats in by_model.values():
        if model_stats["total_count"] > 0:
            model_stats["thumbs_down_rate"] = (
                model_stats["thumbs_down_count"] / model_stats["total_count"]
            )

    # Apply model filter if specified
    if model_filter:
        filtered_feedback = [r for r in feedback_list if r.get("model") == model_filter]
        if filtered_feedback:
            model_total = len(filtered_feedback)
            model_thumbs_down = sum(
                1 for r in filtered_feedback if r.get("rating") == "down"
            )
            model_thumbs_down_rate = (
                model_thumbs_down / model_total if model_total > 0 else 0.0
            )

            return {
                "total_count": model_total,
                "thumbs_down_count": model_thumbs_down,
                "thumbs_down_rate": model_thumbs_down_rate,
                "by_model": by_model,
                "model_filter": model_filter,
            }

    return {
        "total_count": total_count,
        "thumbs_down_count": thumbs_down_count,
        "thumbs_down_rate": thumbs_down_rate,
        "by_model": by_model,
    }


# ==============================================================================
# LLMクライアント・ファクトリ
# ==============================================================================

#: セパレータ。モデルキーの形式: ``"providerName::model_id"``
MODEL_KEY_SEPARATOR = "::"


def parse_model_key(model_key: str):
    """モデルキーをプロバイダ名とモデルIDに分解する。

    Returns:
        Tuple (provider_name_or_none, model_id)

    Examples::

        parse_model_key("llama3")           → (None, "llama3")
        parse_model_key("ollama::llama3")   → ("ollama", "llama3")
        parse_model_key("VeniceAI::llama-3.3-70b") → ("VeniceAI", "llama-3.3-70b")
    """
    if MODEL_KEY_SEPARATOR in model_key:
        provider_name, model_id = model_key.split(MODEL_KEY_SEPARATOR, 1)
        return provider_name.strip(), model_id.strip()
    return None, model_key.strip()


def build_llm_client(
    model_key: Optional[str], settings: Optional[Dict[str, Any]] = None
):
    """モデルキーから適切なLLMクライアントを生成するファクトリ。

    モデルキーの形式:
    - ``"model_name"`` or ``"ollama::model_name"`` → :class:`OllamaClient`
    - ``"ProviderName::model_id"`` → :class:`OpenAICompatClient`
      (settings の ``llm_providers`` から該当プロバイダを検索)

    Args:
        model_key: モデルキー文字列 (``None`` または空文字の場合は OllamaClient を返す)
        settings: 設定辞書。``None`` の場合は :func:`load_settings` で読み込む。

    Returns:
        OllamaClient または OpenAICompatClient インスタンス。
    """
    from researcher.ollama_client import OllamaClient
    from researcher.openai_compat_client import OpenAICompatClient

    if not model_key:
        return OllamaClient(model=None, base_url=get_ollama_base_url(settings))

    if settings is None:
        settings = load_settings()

    provider_name, model_id = parse_model_key(model_key)

    # Plain model name or explicit "ollama::" prefix → Ollama
    if provider_name is None or provider_name.lower() == "ollama":
        return OllamaClient(model=model_id, base_url=get_ollama_base_url(settings))

    # Look up named provider in config
    providers: list = settings.get("llm_providers", [])
    for provider in providers:
        if provider.get("name") == provider_name:
            return OpenAICompatClient(
                model=model_id,
                base_url=provider.get("base_url", ""),
                api_key=provider.get("api_key", ""),
            )

    logging.warning(
        "プロバイダ '%s' が設定に見つかりません。OllamaClientにフォールバックします。",
        provider_name,
    )
    return OllamaClient(model=model_id, base_url=get_ollama_base_url(settings))
