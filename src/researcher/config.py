import json
import logging
import os
import subprocess
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_SEARXNG_URL = "http://localhost:8888"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text-v2-moe"
DEFAULT_RELEVANCE_THRESHOLD = 0.5  # デフォルト値: run.sh と一致。より高い精度の検索結果を優先
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


def get_relevance_threshold(cli_arg: Optional[float] = None) -> float:
    """Resolve relevance threshold: CLI > env > default.
    
    デフォルトは 0.0（すべての結果を返す）です。
    高いしきい値を設定するとEmbedding検索が成功した場合に結果がフィルタリングされます。
    """
    if cli_arg is not None:
        return cli_arg
    env_value = os.environ.get("RELEVANCE_THRESHOLD")
    if env_value:
        try:
            return float(env_value)
        except ValueError:
            logging.warning("RELEVANCE_THRESHOLD must be a float, falling back to default")
    return DEFAULT_RELEVANCE_THRESHOLD


def get_auto_search_default() -> bool:
    """環境変数AUTO_SEARCH_DEFAULTからデフォルト自動検索設定を取得"""
    env_value = os.environ.get("AUTO_SEARCH_DEFAULT", "").lower()
    if env_value in ("true", "1", "yes"):
        return True
    return DEFAULT_AUTO_SEARCH


def _parse_mcp_config_source(source_name: str, raw_value: str) -> Optional[Dict[str, Any]]:
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
                logging.warning("%s (%s): ファイル内容が辞書形式ではありません", source_name, path)
            except Exception as exc:
                logging.warning("%s (%s)の読み込みに失敗しました: %s", source_name, path, exc)
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
    
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
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
                start_new_session=True
            )
            
            # 起動待機
            for _ in range(30):
                try:
                    response = requests.get("http://localhost:11434/api/tags", timeout=1)
                    if response.status_code == 200:
                        return True
                except Exception:
                    time.sleep(1)
    except Exception as e:
        logging.debug(f"Ollamaの自動起動に失敗: {e}")
    
    return False


def ensure_searxng_running() -> bool:
    """SearXNGコンテナが起動していることを確認し、起動していなければ起動"""
    import requests
    
    try:
        # まずHTMLページで接続確認（403でもコンテナは起動している）
        response = requests.get(
            "http://localhost:8888/",
            timeout=2
        )
        if response.status_code in (200, 403):
            # 403は JSONフォーマット無効でもOK、コンテナは起動している
            return True
    except Exception:
        pass
    
    # SearXNGが起動していない場合、起動を試みる
    try:
        # Dockerが利用可能か確認
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            timeout=2
        )
        
        if result.returncode == 0:
            # Dockerが利用可能
            # 既存コンテナを確認
            result = subprocess.run(
                ["docker", "ps", "-a"],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if "searxng" in result.stdout:
                # コンテナが存在するが起動していない場合は起動
                subprocess.run(
                    ["docker", "start", "searxng"],
                    capture_output=True,
                    timeout=5
                )
            else:
                # コンテナが存在しない場合は作成・起動
                # カスタム設定ファイルをマウント（JSON形式有効化のため）
                settings_file = Path(__file__).parent.parent.parent / "searxng_settings.yml"
                
                docker_cmd = [
                    "docker", "run", "-d",
                    "--name", "searxng",
                    "-p", "8888:8080",
                ]
                
                # 設定ファイルが存在すればマウント
                if settings_file.exists():
                    docker_cmd.extend([
                        "-v", f"{settings_file}:/etc/searxng/settings.yml"
                    ])
                
                docker_cmd.append("searxng/searxng")
                
                subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    timeout=30
                )
            
            # 起動待機
            for _ in range(30):
                try:
                    response = requests.get(
                        "http://localhost:8888/",
                        timeout=1
                    )
                    if response.status_code in (200, 403):
                        return True
                except Exception:
                    time.sleep(1)
    except Exception as e:
        logging.debug(f"SearXNGの自動起動に失敗: {e}")
    
    return False

