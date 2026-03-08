"""SearXNG integration tests.

These tests require a running SearXNG instance with JSON API enabled.
They are automatically skipped when SearXNG is not available.

To run:
    1. Start SearXNG: ./scripts/searxng-start.sh
    2. Run tests: pytest tests/test_searxng_integration.py -v
"""

import pytest
import requests


@pytest.mark.searxng
class TestSearxngConnection:
    def test_html_endpoint_reachable(self, searxng_url):
        resp = requests.get(f"{searxng_url}/", timeout=5)
        assert resp.status_code == 200

    def test_json_search_returns_valid_response(self, searxng_json_url):
        resp = requests.get(
            f"{searxng_json_url}/search",
            params={"q": "python", "format": "json"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert data["query"] == "python"

    def test_json_search_has_results_key(self, searxng_json_url):
        resp = requests.get(
            f"{searxng_json_url}/search",
            params={"q": "test", "format": "json"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_json_format_not_403(self, searxng_url):
        resp = requests.get(
            f"{searxng_url}/search",
            params={"q": "test", "format": "json"},
            timeout=10,
        )
        assert resp.status_code != 403, (
            "JSON API returned 403 Forbidden. "
            "Ensure searxng_settings.yml has search.formats: [html, json] "
            "and restart with scripts/searxng-start.sh --force"
        )


@pytest.mark.searxng
class TestEnsureSearxngRunning:
    def test_returns_true_when_available(self, searxng_json_url):
        from unittest.mock import patch

        with patch(
            "researcher.config.get_searxng_url",
            return_value=searxng_json_url,
        ):
            from researcher.config import ensure_searxng_running

            assert ensure_searxng_running() is True

    def test_returns_false_when_unreachable(self):
        from unittest.mock import patch

        with patch(
            "researcher.config.get_searxng_url",
            return_value="http://localhost:19999",
        ):
            from researcher.config import ensure_searxng_running

            assert ensure_searxng_running() is False
