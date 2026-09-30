import httpx
import pytest

from docs_assistant.corpus.fetcher import DocsFetcher, DocsFetchError


def _fetcher(handler, retries=2):
    return DocsFetcher(
        "https://docs.example", retries=retries, transport=httpx.MockTransport(handler)
    )


async def test_fetch_returns_body_on_200():
    fetcher = _fetcher(lambda r: httpx.Response(200, text=f"body of {r.url.path}"))
    assert await fetcher.fetch_index() == "body of /llms.txt"
    assert await fetcher.fetch_full() == "body of /llms-full.txt"


async def test_fetch_page_uses_the_api_md_route():
    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(200, text="md")

    await _fetcher(handler).fetch_page("https://docs.rhesis.ai/sdk/metrics.md#metric-scopes")
    assert seen == ["/api/md/sdk/metrics"]


async def test_server_errors_are_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, text="ok")

    assert await _fetcher(handler).fetch_full() == "ok"
    assert len(calls) == 3


async def test_client_errors_are_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404)

    with pytest.raises(DocsFetchError, match="404"):
        await _fetcher(handler).fetch_index()
    assert len(calls) == 1


async def test_network_errors_raise_after_the_retries():
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(DocsFetchError, match="down"):
        await _fetcher(handler).fetch_full()
    assert len(calls) == 3
