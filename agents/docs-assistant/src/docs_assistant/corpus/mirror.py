"""A local copy of the docs site's LLM views, for checking what happens when the site goes down.

    uv run python -m docs_assistant.corpus mirror --port 8765
    DOCS_BASE_URL=http://localhost:8765 DOCS_CACHE_TTL=10 uv run python -m docs_assistant

Fetches llms.txt and llms-full.txt once, then serves them and /api/md/<path> until stopped.
Stop it, wait past the TTL, and the assistant answers from its snapshot with the stale note.
"""

from __future__ import annotations

import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_PAGE_START = re.compile(r"^---\nurl: (\S+)", re.MULTILINE)


def page_blocks(llms_full: str) -> dict[str, str]:
    """Each page of llms-full.txt, with its front matter, keyed by path."""
    starts = [m.start() for m in _PAGE_START.finditer(llms_full)]
    blocks = {}
    for i, start in enumerate(starts):
        block = llms_full[start : starts[i + 1] if i + 1 < len(starts) else len(llms_full)]
        url = _PAGE_START.match(block).group(1)
        blocks[re.sub(r"^https?://[^/]+/", "", url).strip("/")] = block
    return blocks


def serve(llms_txt: str, llms_full: str, port: int) -> None:
    files = {"/llms.txt": llms_txt, "/llms-full.txt": llms_full}
    files |= {f"/api/md/{path}": block for path, block in page_blocks(llms_full).items()}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (http.server's naming)
            body = files.get(self.path.split("?", 1)[0].rstrip("/"))
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.end_headers()
            self.wfile.write((body or "# 404").encode())

        def log_message(self, *args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Serving {len(files)} files on http://localhost:{port} (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
