import pytest
import requests


def _searxng_available() -> bool:
    """Check if SearXNG is reachable and JSON API is enabled."""
    try:
        resp = requests.get("http://localhost:8888/", timeout=2)
        return resp.status_code in (200, 403)
    except Exception:
        return False


def _searxng_json_available() -> bool:
    """Check if SearXNG JSON API returns valid JSON."""
    try:
        resp = requests.get(
            "http://localhost:8888/search",
            params={"q": "test", "format": "json"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            return "results" in data or "query" in data
        return False
    except Exception:
        return False


@pytest.fixture
def searxng_url():
    """Provide SearXNG base URL, skip if not reachable."""
    if not _searxng_available():
        pytest.skip("SearXNG is not running on localhost:8888")
    return "http://localhost:8888"


@pytest.fixture
def searxng_json_url():
    """Provide SearXNG base URL, skip if JSON API is not available."""
    if not _searxng_json_available():
        pytest.skip(
            "SearXNG JSON API is not available (run scripts/searxng-start.sh to start)"
        )
    return "http://localhost:8888"
