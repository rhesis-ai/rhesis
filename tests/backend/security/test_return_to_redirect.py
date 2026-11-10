"""Post-login ``return_to`` must stay a same-origin relative path.

Browsers read ``\\`` as ``/`` and drop tab/newline characters, so values like
``/\\evil.example`` navigate off-origin even though they start with one slash.
"""

import asyncio
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest

from rhesis.backend.app.auth.url_utils import (
    DEFAULT_RETURN_TO,
    build_redirect_url,
    safe_return_path,
)
from rhesis.backend.app.config.settings import get_frontend_settings

FRONTEND = "http://localhost:3000"

UNSAFE = [
    "//evil.example",
    "///evil.example",
    "/\\evil.example",
    "/\\/evil.example",
    "\\\\evil.example",
    "/\t/evil.example",
    "/\n/evil.example",
    "/\r/evil.example",
    "/\x00/evil.example",
    "/\x7f",
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "data:text/html,x",
    "https://evil.example/path",
    "http:/evil.example",
    "evil.example",
    "",
    None,
    123,
]

SAFE = [
    "/",
    "/architect",
    "/tests/123?tab=runs#top",
    "/%2F%2Fevil.example",
    "/projects/a:b",
]


@pytest.mark.unit
@pytest.mark.parametrize("value", UNSAFE)
def test_safe_return_path_rejects(value):
    assert safe_return_path(value) == DEFAULT_RETURN_TO


@pytest.mark.unit
@pytest.mark.parametrize("value", SAFE)
def test_safe_return_path_accepts(value):
    assert safe_return_path(value) == value


@pytest.fixture
def frontend_settings(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", FRONTEND)
    get_frontend_settings.cache_clear()
    yield
    get_frontend_settings.cache_clear()


def _redirect_for(return_to):
    request = Mock()
    request.session = {"return_to": return_to}
    with patch(
        "rhesis.backend.app.auth.token_utils.get_secret_key",
        return_value="test-secret",
    ):
        return asyncio.run(build_redirect_url(request, "token"))


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        "/\\evil.example",
        "//evil.example",
        "https://evil.example/\\evil.example",
        "https://evil.example//evil.example",
        "https://app.example/x?return_to=/\\evil.example",
        "javascript:alert(1)",
    ],
)
def test_build_redirect_url_falls_back_for_unsafe_return_to(frontend_settings, value):
    url = _redirect_for(value)
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}" == FRONTEND
    assert parse_qs(parts.query)["return_to"] == [DEFAULT_RETURN_TO]


@pytest.mark.unit
def test_build_redirect_url_keeps_safe_return_to_with_query(frontend_settings):
    url = _redirect_for("/tests?tab=runs&page=2")
    query = parse_qs(urlsplit(url).query)
    assert query["return_to"] == ["/tests?tab=runs&page=2"]
    assert len(query["code"]) == 1
