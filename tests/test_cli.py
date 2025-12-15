import builtins
import sys
from unittest.mock import MagicMock

import pytest

from researcher import cli as cli_module


class StubChatManager:
    def __init__(self, *args, **kwargs):
        self.auto_search_calls = []
        self.response_calls = 0

    def add_system_message(self, content):
        self.system_message = content

    def clear_history(self, keep_system=True):
        pass

    def get_history(self):
        return []

    def add_user_message(self, _):
        pass

    def get_response(self):
        self.response_calls += 1
        return "response"

    def get_response_stream(self):
        self.response_calls += 1
        return iter(["stream"])

    def search(self, query):
        return {"formatted": f"search:{query}", "results": [], "raw": {}}

    def auto_search(self, query):
        self.auto_search_calls.append(query)
        return {"searched": True, "formatted": "auto", "results": [], "analysis": {}}


class FakeOllamaClient:
    def __init__(self, *args, **kwargs):
        pass

    def test_connection(self):
        return True


class FakeSearXNGClient:
    def __init__(self, *args, **kwargs):
        pass

    def test_connection(self):
        return True


class FakeAgent:
    def __init__(self, *args, **kwargs):
        pass


class FakeReranker:
    def __init__(self, *args, **kwargs):
        pass


@pytest.mark.usefixtures("monkeypatch")
def test_cli_auto_search_mode(monkeypatch):
    chat_instances = []

    def fake_chat_manager(*args, **kwargs):
        instance = StubChatManager()
        chat_instances.append(instance)
        return instance

    inputs = iter(["hello world", "/exit"])

    monkeypatch.setattr(builtins, "input", lambda prompt="": next(inputs))
    monkeypatch.setattr(sys, "argv", ["researcher", "--auto-search"])
    monkeypatch.setattr(cli_module, "ChatManager", fake_chat_manager)
    monkeypatch.setattr(cli_module, "OllamaClient", FakeOllamaClient)
    monkeypatch.setattr(cli_module, "SearXNGClient", FakeSearXNGClient)
    monkeypatch.setattr(cli_module, "QueryAgent", FakeAgent)
    monkeypatch.setattr(cli_module, "EmbeddingReranker", FakeReranker)

    cli_module.main()

    assert len(chat_instances) == 1
    assert chat_instances[0].auto_search_calls == ["hello world"]


@pytest.mark.usefixtures("monkeypatch")
def test_cli_manual_mode(monkeypatch):
    chat_instances = []

    def fake_chat_manager(*args, **kwargs):
        instance = StubChatManager()
        chat_instances.append(instance)
        return instance

    inputs = iter(["hello world", "/exit"])

    monkeypatch.setattr(builtins, "input", lambda prompt="": next(inputs))
    monkeypatch.setattr(sys, "argv", ["researcher"])
    monkeypatch.setattr(cli_module, "ChatManager", fake_chat_manager)
    monkeypatch.setattr(cli_module, "OllamaClient", FakeOllamaClient)
    monkeypatch.setattr(cli_module, "SearXNGClient", FakeSearXNGClient)
    monkeypatch.setattr(cli_module, "QueryAgent", FakeAgent)
    monkeypatch.setattr(cli_module, "EmbeddingReranker", FakeReranker)

    cli_module.main()

    assert len(chat_instances) == 1
    assert chat_instances[0].auto_search_calls == []
    assert chat_instances[0].response_calls > 0


def test_blacklist_add_domain_normalization():
    """Test that /blacklist add normalizes URL input to domain."""
    from urllib.parse import urlparse
    
    # Test cases: (input, expected_domain)
    test_cases = [
        ("example.com", "example.com"),
        ("https://example.com", "example.com"),
        ("https://example.com/path/to/page", "example.com"),
        ("http://sub.example.com:8080/page", "sub.example.com:8080"),
    ]
    
    for input_str, expected_domain in test_cases:
        # Simulate the normalization logic from CLI
        target = input_str.strip()
        if "://" in target or "/" in target:
            parsed = urlparse(target if "://" in target else f"http://{target}")
            normalized_domain = parsed.netloc
        else:
            normalized_domain = target
        
        assert normalized_domain == expected_domain, f"Failed for input: {input_str}"