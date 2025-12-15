import os
from unittest.mock import patch
import tempfile
from pathlib import Path

from researcher.config import (
    DEFAULT_RELEVANCE_THRESHOLD,
    DEFAULT_SEARXNG_URL,
    DEFAULT_EMBEDDING_MODEL,
    get_embedding_model,
    get_relevance_threshold,
    get_searxng_url,
    load_blacklist_domains,
    save_blacklist_domains,
    BLACKLIST_FILE_PATH,
)


def test_get_searxng_url_default():
    with patch.dict(os.environ, {}, clear=True):
        assert get_searxng_url() == DEFAULT_SEARXNG_URL


def test_get_searxng_url_from_env():
    with patch.dict(os.environ, {"SEARXNG_URL": "http://env:8888"}, clear=True):
        assert get_searxng_url() == "http://env:8888"


def test_get_searxng_url_from_cli():
    with patch.dict(os.environ, {"SEARXNG_URL": "http://env:8888"}, clear=True):
        assert get_searxng_url("http://cli:8888") == "http://cli:8888"


def test_get_searxng_url_priority():
    with patch.dict(os.environ, {"SEARXNG_URL": "http://env:8888"}, clear=True):
        assert get_searxng_url() == "http://env:8888"
    with patch.dict(os.environ, {}, clear=True):
        assert get_searxng_url() == DEFAULT_SEARXNG_URL


def test_get_embedding_model_resolution():
    with patch.dict(os.environ, {}, clear=True):
        assert get_embedding_model() == DEFAULT_EMBEDDING_MODEL
    with patch.dict(os.environ, {"EMBEDDING_MODEL": "env-model"}, clear=True):
        assert get_embedding_model() == "env-model"
    with patch.dict(os.environ, {"EMBEDDING_MODEL": "env-model"}, clear=True):
        assert get_embedding_model("cli-model") == "cli-model"


def test_get_relevance_threshold_resolution():
    with patch.dict(os.environ, {}, clear=True):
        assert get_relevance_threshold() == DEFAULT_RELEVANCE_THRESHOLD
    with patch.dict(os.environ, {"RELEVANCE_THRESHOLD": "0.8"}, clear=True):
        assert get_relevance_threshold() == 0.8
    assert get_relevance_threshold(0.9) == 0.9


def test_get_relevance_threshold_default_value():
    """Test that default relevance_threshold is 0.5, not 0.0."""
    with patch.dict(os.environ, {}, clear=True):
        threshold = get_relevance_threshold()
        # Verify default is 0.5 (meaning: return results with 50% relevance or higher)
        # 0.0 would mean "return all results" but that's not the intended behavior
        assert threshold == 0.5
        assert threshold == DEFAULT_RELEVANCE_THRESHOLD


def test_load_blacklist_domains_empty():
    """Test loading blacklist when file doesn't exist."""
    with patch("researcher.config.BLACKLIST_FILE_PATH", Path("/nonexistent/path/blacklist.json")):
        result = load_blacklist_domains()
        assert result == set()


def test_load_blacklist_domains_valid():
    """Test loading valid blacklist JSON file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json
        json.dump(["wsj.com", "nytimes.com", "paywall.com"], f)
        temp_path = f.name
    
    try:
        with patch("researcher.config.BLACKLIST_FILE_PATH", Path(temp_path)):
            result = load_blacklist_domains()
            assert result == {"wsj.com", "nytimes.com", "paywall.com"}
    finally:
        Path(temp_path).unlink()


def test_save_blacklist_domains():
    """Test saving blacklist domains to JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "blacklist.json"
        with patch("researcher.config.BLACKLIST_FILE_PATH", temp_path):
            domains = {"example.com", "test.com"}
            save_blacklist_domains(domains)
            
            # Verify file was created and contains correct data
            assert temp_path.exists()
            import json
            with open(temp_path, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                assert set(saved_data) == domains


def test_save_blacklist_domains_creates_directory():
    """Test that save_blacklist_domains creates parent directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir) / "subdir" / "nested" / "blacklist.json"
        with patch("researcher.config.BLACKLIST_FILE_PATH", temp_path):
            domains = {"example.com"}
            save_blacklist_domains(domains)
            
            # Verify directory structure was created
            assert temp_path.parent.exists()
            assert temp_path.exists()


def test_load_blacklist_domains_with_mixed_types():
    """Test that load_blacklist_domains filters out non-string items."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json
        json.dump(["wsj.com", 123, "example.com", None, "test.com"], f)
        temp_path = f.name
    
    try:
        with patch("researcher.config.BLACKLIST_FILE_PATH", Path(temp_path)):
            result = load_blacklist_domains()
            # Only string entries should be loaded
            assert result == {"wsj.com", "example.com", "test.com"}
            assert 123 not in result
            assert None not in result
    finally:
        Path(temp_path).unlink()


def test_load_blacklist_domains_strips_whitespace():
    """Test that load_blacklist_domains strips whitespace from entries."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        import json
        json.dump(["  example.com  ", "test.com", "  "], f)
        temp_path = f.name
    
    try:
        with patch("researcher.config.BLACKLIST_FILE_PATH", Path(temp_path)):
            result = load_blacklist_domains()
            # Whitespace should be stripped, empty entries ignored
            assert result == {"example.com", "test.com"}
    finally:
        Path(temp_path).unlink()