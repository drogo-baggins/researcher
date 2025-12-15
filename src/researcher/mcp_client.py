import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, Tuple

from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(self, servers_config: Dict[str, Any]):
        self.servers_config = servers_config
        self.sessions: Dict[str, Any] = {}
        self.exit_stack = AsyncExitStack()
        self._tools_cache: Dict[str, List[Dict[str, Any]]] = {}

    def test_connection(self) -> bool:
        statuses = self.connect_servers()
        return any(statuses.values())

    def connect_servers(self) -> Dict[str, bool]:
        return self._run_async(self._async_connect_servers())

    def list_tools(self, server_name: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._run_async(self._async_list_tools(server_name))

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_async(self._async_call_tool(tool_name, arguments))

    def cleanup(self) -> None:
        self._run_async(self._async_cleanup())

    def _run_async(self, coro):
        try:
            return asyncio.run(coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

    async def _async_connect_servers(self) -> Dict[str, bool]:
        statuses: Dict[str, bool] = {}
        for server_name, cfg in self.servers_config.items():
            if not cfg.get("enabled"):
                statuses[server_name] = False
                continue
            command = cfg.get("command")
            args = cfg.get("args", [])
            if not command:
                logging.warning("%s には command が設定されていません", server_name)
                statuses[server_name] = False
                continue
            try:
                session = await stdio_client(command, *args)
                await self.exit_stack.enter_async_context(session)
                self.sessions[server_name] = session
                self._tools_cache.pop(server_name, None)
                statuses[server_name] = True
            except Exception as exc:
                logging.warning("MCP %s サーバーへの接続に失敗しました: %s", server_name, exc)
                statuses[server_name] = False
        return statuses

    async def _async_list_tools(self, server_name: Optional[str]) -> List[Dict[str, Any]]:
        targets = [server_name] if server_name else list(self.sessions.keys())
        tools: List[Dict[str, Any]] = []
        for name in targets:
            if not name:
                continue
            session = self.sessions.get(name)
            if not session:
                continue
            cached = await self._ensure_tools(name, session)
            for tool in cached:
                entry = {**tool, "server": name}
                tools.append(entry)
        return tools

    async def _async_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        server_name, short_name = await self._resolve_tool(tool_name)
        session = self.sessions.get(server_name)
        if not session:
            raise RuntimeError(f"{server_name} へのセッションがありません。MCP 接続を確認してください。")
        try:
            if not hasattr(session, "call_tool"):
                raise RuntimeError("使用中の MCP セッションは call_tool を公開していません")
            result = await session.call_tool(short_name, arguments)
        except Exception as exc:
            logging.warning("MCP %s.%s の実行に失敗しました: %s", server_name, short_name, exc)
            raise RuntimeError(f"MCP ツール {server_name}.{short_name} の実行中にエラー: {exc}") from exc
        if not isinstance(result, dict):
            return {"content": [], "isError": True, "server": server_name}
        result.setdefault("server", server_name)
        result.setdefault("isError", False)
        return result

    async def _ensure_tools(self, server_name: str, session: Any) -> List[Dict[str, Any]]:
        if server_name in self._tools_cache:
            return self._tools_cache[server_name]
        if not hasattr(session, "list_tools"):
            raise RuntimeError("セッションは list_tools メソッドを提供していません")
        tools = await session.list_tools()
        self._tools_cache[server_name] = tools
        return tools

    async def _resolve_tool(self, tool_name: str) -> Tuple[str, str]:
        if "." in tool_name:
            server_name, short = tool_name.split(".", 1)
            return server_name, short
        for server_name, session in self.sessions.items():
            tools = await self._ensure_tools(server_name, session)
            for tool in tools:
                if tool.get("name") == tool_name:
                    return server_name, tool_name
        raise RuntimeError(f"ツール {tool_name} が登録されていません。")

    async def _async_cleanup(self) -> None:
        await self.exit_stack.aclose()
        self.sessions.clear()
        self._tools_cache.clear()
