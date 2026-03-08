import pytest
from unittest.mock import MagicMock, patch
import requests

from researcher.searxng_client import SearXNGClient


def _make_response(payload, status_code=200, text=None):
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    response.text = text or "<article>test</article>"  # Default HTML content for test_connection
    return response


@patch("researcher.searxng_client.requests.get")
def test_test_connection_success(mock_get):
    payload = {"object": "search", "results": ["a"]}
    mock_get.return_value = _make_response(payload, text="<article>test result</article>")

    client = SearXNGClient("http://localhost:8888")
    assert client.test_connection() is True
    mock_get.assert_called_once()


@patch("researcher.searxng_client.requests.get")
def test_test_connection_failure(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("no route")

    client = SearXNGClient("http://localhost:8888")
    assert client.test_connection() is False


@patch("researcher.searxng_client.requests.get")
def test_search_success(mock_get):
    payload = {
        "object": "search",
        "results": [
            {
                "title": "Example",
                "url": "https://example.com",
                "snippet": "Test snippet",
                "published_date": "2025-01-01",
            }
        ],
    }
    mock_get.return_value = _make_response(payload)

    client = SearXNGClient("http://localhost:8888")
    result = client.search("python")

    assert result["raw"] == payload
    assert result["results"] == [
        {
            "title": "Example",
            "url": "https://example.com",
            "snippet": "Test snippet",
            "published_date": "2025-01-01",
            "score": 0.5,
        }
    ]


@patch("researcher.searxng_client.requests.get")
def test_search_with_options(mock_get):
    payload = {"object": "search", "results": []}
    mock_get.return_value = _make_response(payload)

    client = SearXNGClient("http://localhost:8888")
    client.search(
        "query",
        categories="general",
        engines="google",
        language="en",
        pageno=2,
        time_range="week",
        safesearch=1,
    )

    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    params = kwargs["params"]
    assert params["categories"] == "general"
    assert params["engines"] == "google"
    assert params["language"] == "en"
    assert params["pageno"] == 2
    assert params["time_range"] == "week"
    assert params["safesearch"] == 1


@pytest.mark.parametrize("label,expected", [("off", 0), ("moderate", 1), ("strict", 2)])
@patch("researcher.searxng_client.requests.get")
def test_search_safesearch_string_to_int(mock_get, label, expected):
    """safesearch に文字列が渡された場合、SearXNG API 用の整数に変換されること"""
    mock_get.return_value = _make_response({"results": []})
    client = SearXNGClient("http://localhost:8888")
    client.search("query", safesearch=label)

    _, kwargs = mock_get.call_args
    assert kwargs["params"]["safesearch"] == expected


def test_search_invalid_parameter():
    client = SearXNGClient("http://localhost:8888")
    with pytest.raises(ValueError) as exc:
        client.search("query", foo="bar")
    assert "未サポートの検索パラメータ" in str(exc.value)


@patch("researcher.searxng_client.requests.get")
def test_search_http_error(mock_get):
    response = _make_response({"results": []})
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("bad")
    mock_get.return_value = response

    client = SearXNGClient("http://localhost:8888")
    with pytest.raises(RuntimeError) as exc:
        client.search("python")
    assert "検索エラー" in str(exc.value)


def test_parse_results():
    client = SearXNGClient("http://localhost:8888")
    payload = {
        "results": [
            {"title": "Example", "url": "https://example.com", "snippet": "snip", "published_date": "2025-01-02"}
        ]
    }
    parsed = client._parse_results(payload)
    assert parsed == [
        {"title": "Example", "url": "https://example.com", "snippet": "snip", "published_date": "2025-01-02", "score": 0.5}
    ]


@pytest.mark.integration
def test_integration_with_searxng():
    client = SearXNGClient("http://localhost:8888")
    try:
        assert client.test_connection() is True
    except RuntimeError:
        pytest.skip("SearXNGサーバーが起動していないためスキップ")
