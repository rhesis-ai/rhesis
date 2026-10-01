import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

from docs_assistant.corpus import mirror
from tests.conftest import LLMS_FULL, LLMS_TXT


def test_page_blocks_split_the_full_corpus_by_path():
    blocks = mirror.page_blocks(LLMS_FULL)
    assert "docs/metrics/metric-scope" in blocks
    assert blocks["sdk/installation"].startswith(
        "---\nurl: https://docs.rhesis.ai/sdk/installation"
    )
    assert len(blocks) == 8


def test_the_mirror_serves_the_llm_views(monkeypatch):
    servers = []
    real = ThreadingHTTPServer

    class Recording(real):
        def __init__(self, address, handler):
            super().__init__(("127.0.0.1", 0), handler)
            servers.append(self)

    monkeypatch.setattr(mirror, "ThreadingHTTPServer", Recording)
    thread = threading.Thread(target=mirror.serve, args=(LLMS_TXT, LLMS_FULL, 0), daemon=True)
    thread.start()
    while not servers:
        time.sleep(0.01)
    base = f"http://127.0.0.1:{servers[0].server_address[1]}"
    try:
        assert urllib.request.urlopen(f"{base}/llms.txt").read().decode() == LLMS_TXT
        page = urllib.request.urlopen(f"{base}/api/md/sdk/metrics").read().decode()
        assert page.startswith("---\nurl: https://docs.rhesis.ai/sdk/metrics")
    finally:
        servers[0].shutdown()
