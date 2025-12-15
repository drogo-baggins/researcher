import asyncio
import sys
from unittest.mock import AsyncMock, patch

import pytest

from researcher.mcp_client import MCPClient


@pytest.fixture
def sync_run():
    def run_sync(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with patch("researcher.mcp_client.asyncio.run", side_effect=run_sync) as runner:
        yield runner


@pytest.fixture
def patch_stdio_client():
    with patch("researcher.mcp_client.stdio_client", new_callable=AsyncMock) as mock_stdio:
        yield mock_stdio


def _build_session(tool_name: str = "read_file") -> AsyncMock:
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    session.list_tools = AsyncMock(return_value=[
        {"name": tool_name, "description": "desc", "inputSchema": {}},
    ])
    session.call_tool = AsyncMock(return_value={"content": ["ok"], "isError": False})
    return session


def test_init_stores_config():
    config = {"filesystem": {"command": "node", "args": ["server.js"], "enabled": False}}
    client = MCPClient(config)
    assert client.servers_config is config
    assert client.sessions == {}
    assert client._tools_cache == {}


def test_connect_servers_success(sync_run, patch_stdio_client):
    session = _build_session()
    patch_stdio_client.return_value = session
    client = MCPClient(
        {"filesystem": {"command": "node", "args": ["server.js"], "enabled": True}}
    )
    statuses = client.connect_servers()
    assert statuses.get("filesystem")
    assert "filesystem" in client.sessions


def test_connect_servers_failure(sync_run, patch_stdio_client):
    patch_stdio_client.side_effect = RuntimeError("failed")
    client = MCPClient(
        {"filesystem": {"command": "node", "args": ["server.js"], "enabled": True}}
    )
    statuses = client.connect_servers()
    assert statuses.get("filesystem") is False


def test_list_tools_returns_server_field(sync_run):
    client = MCPClient({})
    session = _build_session()
    client.sessions["filesystem"] = session
    tools = client.list_tools()
    assert tools[0]["server"] == "filesystem"
    session.list_tools.assert_awaited_once()


def test_list_tools_caches_results(sync_run):
    client = MCPClient({})
    session = _build_session()
    client.sessions["filesystem"] = session
    client.list_tools()
    client.list_tools("filesystem")
    assert session.list_tools.await_count == 1


def test_call_tool_success(sync_run):
    client = MCPClient({})
    session = _build_session()
    client.sessions["filesystem"] = session
    result = client.call_tool("read_file", {"path": "/tmp"})
    assert result["server"] == "filesystem"
    session.call_tool.assert_awaited_once_with("read_file", {"path": "/tmp"})


def test_call_tool_with_server_prefix(sync_run):
    client = MCPClient({})
    session = _build_session()
    client.sessions["filesystem"] = session
    client.call_tool("filesystem.read_file", {"path": "/tmp"})
    session.call_tool.assert_awaited_once()
    session.list_tools.assert_not_awaited()


def test_call_tool_missing_tool(sync_run):
    client = MCPClient({})
    session = _build_session(tool_name="different")
    client.sessions["filesystem"] = session
    with pytest.raises(RuntimeError):
        client.call_tool("missing", {})


def test_cleanup_closes_exit_stack(sync_run):
    client = MCPClient({})
    aclose = AsyncMock()
    client.exit_stack.aclose = aclose
    client.cleanup()
    aclose.assert_awaited_once()


@pytest.mark.integration
def test_real_filesystem_server():
    pytest.skip("Integration requires manual MCP filesystem server setup")


@pytest.mark.integration
def test_real_notes_server():
    if sys.platform != "darwin":
        pytest.skip("Apple Notes MCP server は macOS 専用です")
    pytest.skip("Integration requires manual MCP Apple Notes server setup")


@pytest.mark.integration
def test_real_calendar_server():
    if sys.platform != "darwin":
        pytest.skip("Calendar MCP server は macOS 専用です")
    pytest.skip("Integration requires manual MCP Calendar server setup")
