import os
from unittest.mock import patch

from researcher.config import (
    DEFAULT_RELEVANCE_THRESHOLD,
    DEFAULT_SEARXNG_URL,
    DEFAULT_EMBEDDING_MODEL,
    get_embedding_model,
    get_relevance_threshold,
    get_searxng_url,
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