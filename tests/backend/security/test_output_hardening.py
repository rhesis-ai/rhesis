"""Exports, downloads and recorded requests carry user data safely.

- CSV exports neutralize cells a spreadsheet would run as a formula.
- Download filenames are escaped into a valid Content-Disposition header.
- A WebSocket endpoint's recorded request never holds the resolved auth token.
- PUT /organizations/{id} changes only the organization's own profile.
"""

from __future__ import annotations

import csv
import io
import json
from unittest.mock import Mock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointAuthType, EndpointConnectionType
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.services.invokers.websocket_invoker import WebSocketEndpointInvoker
from rhesis.backend.app.services.prompt import prompts_to_csv
from rhesis.backend.app.services.test_run import test_run_results_to_csv as run_results_to_csv
from rhesis.backend.app.utils.content_disposition import attachment_disposition
from rhesis.backend.app.utils.csv_safety import neutralize_formula

FORMULAS = ['=HYPERLINK("x")', "+1+1", "-2+3", "@SUM(A1)", "\tx", "\rx"]


def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


@pytest.mark.security
class TestCsvExportsNeutralizeFormulas:
    @pytest.mark.parametrize("cell", FORMULAS)
    def test_formula_cells_are_prefixed(self, cell):
        assert neutralize_formula(cell) == f"'{cell}"

    @pytest.mark.parametrize("cell", ["plain text", "", 42, None, 1.5])
    def test_other_cells_are_kept(self, cell):
        assert neutralize_formula(cell) == cell

    def test_test_set_export(self):
        rows = _rows(prompts_to_csv([{"content": "=1+1", "expected": "ok"}]))
        assert rows[1] == ["'=1+1", "ok"]

    def test_test_run_export(self):
        csv_text = run_results_to_csv(
            [
                {
                    "test_id": "t1",
                    "prompt_content": "@cmd",
                    "response": "+exfil",
                    "created_at": "2026-01-01",
                }
            ]
        )
        assert _rows(csv_text)[1] == ["t1", "'@cmd", "'+exfil", "2026-01-01"]


@pytest.mark.security
class TestDownloadFilenames:
    @pytest.mark.parametrize(
        "name",
        ['report"; filename="evil.html', "отчёт.pdf", "a/b\\c.txt", "plain.txt"],
    )
    def test_header_is_valid_latin1_with_one_quoted_ascii_name(self, name):
        value = attachment_disposition(name)

        value.encode("latin-1")  # a header that is not Latin-1 cannot be sent at all
        ascii_part = value.split(";")[1].strip()
        assert ascii_part.startswith('filename="') and ascii_part.count('"') == 2
        assert "/" not in ascii_part and "\\" not in ascii_part
        assert "filename*=UTF-8''" in value

    def test_unicode_name_survives_in_the_extended_parameter(self):
        assert "filename*=UTF-8''%D0%BE%D1%82" in attachment_disposition("отчёт.pdf")


@pytest.mark.security
class TestWebSocketRecordedRequest:
    @pytest.mark.asyncio
    async def test_failed_call_records_the_message_without_the_token(self):
        token = "ws-secret-token-123"
        endpoint = Endpoint(
            id="ws-endpoint",
            name="WS",
            connection_type=EndpointConnectionType.WEBSOCKET.value,
            url="wss://ws.example.com/chat",
            auth_type=EndpointAuthType.BEARER_TOKEN.value,
            auth_token=token,
            request_mapping='{"query": "{{ input }}", "auth_token": "{{ auth_token }}"}',
            response_mapping={"output": "$.message"},
        )
        invoker = WebSocketEndpointInvoker()

        with patch(
            "rhesis.backend.app.services.invokers.websocket_invoker.guarded_ws_connect",
            side_effect=RuntimeError("connection refused"),
        ):
            result = await invoker._async_invoke(Mock(spec=Session), endpoint, {"input": "hi"})

        recorded = json.dumps(result, default=str)
        assert token not in recorded
        assert "[REDACTED]" in recorded


@pytest.mark.security
class TestOrganizationUpdateIsProfileOnly:
    def test_ownership_limits_and_verification_are_ignored(
        self,
        authenticated_client: TestClient,
        test_db: Session,
        test_org_id: str,
    ):
        before = test_db.query(Organization).filter(Organization.id == test_org_id).one()
        owner_id, max_users = before.owner_id, before.max_users

        response = authenticated_client.put(
            f"/organizations/{test_org_id}",
            json={
                "display_name": "Renamed",
                "owner_id": "00000000-0000-4000-8000-000000000000",
                "user_id": "00000000-0000-4000-8000-000000000000",
                "max_users": 10_000,
                "subscription_ends_at": "2099-01-01T00:00:00Z",
                "is_domain_verified": True,
                "is_active": False,
            },
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["display_name"] == "Renamed"
        assert body["owner_id"] == (str(owner_id) if owner_id else None)
        assert body["max_users"] == max_users
        assert body["is_domain_verified"] is not True or before.is_domain_verified
        assert body["is_active"] is True
