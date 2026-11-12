"""Size bounds on requests that fan out into server work.

- ``/services/mcp/query`` runs one LLM call plus one tool call per iteration inside the
  request, so ``max_iterations`` has a ceiling.
- Bulk lists are handled in one transaction, so they carry at most MAX_BULK_ITEMS items.
- Import sessions hold the uploaded file in memory; one organization may only hold a few,
  and an .xlsx may not expand past a fixed size.
- The server refuses WebSocket frames over the app's message limit before buffering them.
"""

from __future__ import annotations

import io
import re
import uuid
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from rhesis.backend.app.constants import WS_MAX_MESSAGE_SIZE, WS_MAX_QUEUE
from rhesis.backend.app.schemas.base import MAX_BULK_ITEMS
from rhesis.backend.app.schemas.services import QueryMCPRequest


class TestMcpQueryIterations:
    def test_ceiling_on_max_iterations(self):
        with pytest.raises(ValidationError):
            QueryMCPRequest(query="q", tool_id="t", max_iterations=10_000)
        with pytest.raises(ValidationError):
            QueryMCPRequest(query="q", tool_id="t", max_iterations=0)
        assert QueryMCPRequest(query="q", tool_id="t").max_iterations == 10

    def test_route_rejects_an_oversized_value(self, authenticated_client):
        response = authenticated_client.post(
            "/services/mcp/query",
            json={"query": "q", "tool_id": str(uuid.uuid4()), "max_iterations": 10_000},
        )
        assert response.status_code == 422, response.text


def _ids(n):
    return [str(uuid.uuid4()) for _ in range(n)]


class TestBulkListCap:
    @pytest.mark.parametrize(
        "method,path,field",
        [
            ("DELETE", "/tests/bulk", "test_ids"),
            ("DELETE", "/endpoints/bulk", "endpoint_ids"),
            ("DELETE", "/test_sets/bulk", "test_set_ids"),
        ],
    )
    def test_oversized_id_list_is_rejected(self, authenticated_client, method, path, field):
        response = authenticated_client.request(
            method, path, json={field: _ids(MAX_BULK_ITEMS + 1)}
        )
        assert response.status_code == 422, response.text

    def test_oversized_bulk_test_set_is_rejected(self, authenticated_client):
        test = {"prompt": {"content": "x"}, "behavior": "b", "category": "c", "topic": "t"}
        response = authenticated_client.post(
            "/test_sets/bulk",
            json={
                "name": "too big",
                "test_set_type": "Single-Turn",
                "tests": [test] * (MAX_BULK_ITEMS + 1),
            },
        )
        assert response.status_code == 422, response.text

    def test_other_request_id_lists_are_capped(self):
        from rhesis.backend.app.schemas.notification import NotificationMarkReadRequest
        from rhesis.backend.app.schemas.preflight import PreflightCheckRequest

        with pytest.raises(ValidationError):
            NotificationMarkReadRequest(notification_ids=_ids(MAX_BULK_ITEMS + 1))
        with pytest.raises(ValidationError):
            PreflightCheckRequest(test_set_ids=_ids(MAX_BULK_ITEMS + 1), endpoint_id=uuid.uuid4())

    def test_oversized_restore_is_rejected(self, authenticated_client):
        response = authenticated_client.post(
            "/recycle/bulk-restore/test", json=_ids(MAX_BULK_ITEMS + 1)
        )
        assert response.status_code == 422, response.text


class TestImportSessionCaps:
    def test_one_org_cannot_take_the_whole_pool(self, monkeypatch):
        from rhesis.backend.app.services.file_import import storage
        from rhesis.backend.app.services.file_import.storage import ImportSessionStore

        monkeypatch.setattr(ImportSessionStore, "_sessions", {})
        monkeypatch.setattr(ImportSessionStore, "_persist_to_disk", classmethod(lambda c, s: None))

        for _ in range(storage.MAX_SESSIONS_PER_ORG):
            ImportSessionStore.create_session(b"a", "f.csv", "csv", "u1", "org-a")
        with pytest.raises(ValueError):
            ImportSessionStore.create_session(b"a", "f.csv", "csv", "u1", "org-a")

        # Another organization still gets a session.
        ImportSessionStore.create_session(b"a", "f.csv", "csv", "u2", "org-b")

    def test_xlsx_that_expands_too_far_is_refused(self, monkeypatch):
        from rhesis.backend.app.services.file_import import parsers

        monkeypatch.setattr(parsers, "MAX_XLSX_UNCOMPRESSED_BYTES", 1024)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/worksheets/sheet1.xml", b"0" * 10_000)

        with pytest.raises(ValueError, match="expands"):
            parsers._parse_xlsx(buf.getvalue())


class TestWebSocketServerLimits:
    def test_gunicorn_worker_applies_the_app_limits(self):
        from rhesis.backend.app.uvicorn_worker import RhesisUvicornWorker

        assert RhesisUvicornWorker.CONFIG_KWARGS["ws_max_size"] == WS_MAX_MESSAGE_SIZE
        assert RhesisUvicornWorker.CONFIG_KWARGS["ws_max_queue"] == WS_MAX_QUEUE
        assert WS_MAX_MESSAGE_SIZE * WS_MAX_QUEUE <= 64 * 1024 * 1024

    def test_start_script_matches_the_constants(self):
        start = (Path(__file__).parents[3] / "apps/backend/start.sh").read_text()

        assert "rhesis.backend.app.uvicorn_worker.RhesisUvicornWorker" in start
        assert re.search(rf"--ws-max-size {WS_MAX_MESSAGE_SIZE}\b", start)
        assert re.search(rf"--ws-max-queue {WS_MAX_QUEUE}\b", start)
