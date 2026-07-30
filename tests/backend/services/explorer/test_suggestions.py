import json
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.explorer import invoke_endpoint_for_suggestions_stream

# Resolved at call time inside EndpointInvoker, so the source modules are the patch targets.
_DB_CTX_PATCH = "rhesis.backend.app.database.get_db_with_tenant_variables"
_SVC_PATCH = "rhesis.backend.app.dependencies.get_endpoint_service"


def _mock_db_context(test_db):
    @contextmanager
    def _ctx(*_args, **_kwargs):
        yield test_db

    return _ctx


class _Suggestion:
    """Stand-in for the Pydantic suggestion objects the router passes in."""

    def __init__(self, input_text):
        self.input = input_text


async def _collect(stream):
    """Drain an NDJSON byte stream into a list of decoded events."""
    events = []
    async for chunk in stream:
        for line in chunk.decode("utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


@pytest.mark.integration
@pytest.mark.service
@pytest.mark.asyncio
class TestInvokeEndpointForSuggestionsStream:
    """Test the NDJSON stream that generates outputs for non-persisted suggestions."""

    async def test_emits_one_item_per_suggestion_then_summary(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Every suggestion gets an item event, followed by a single summary."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "an answer"})
        suggestions = [_Suggestion("first"), _Suggestion("second"), _Suggestion("third")]

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            events = await _collect(
                invoke_endpoint_for_suggestions_stream(
                    db=test_db,
                    endpoint_id=str(uuid.uuid4()),
                    suggestions=suggestions,
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )
            )

        items = [e for e in events if e["type"] == "item"]
        summary = [e for e in events if e["type"] == "summary"]

        assert len(items) == 3
        assert len(summary) == 1
        assert summary[0] == {"type": "summary", "generated": 3, "total": 3}
        assert events[-1]["type"] == "summary"

        # Items arrive in completion order, so identify them by index.
        assert {i["index"] for i in items} == {0, 1, 2}
        by_index = {i["index"]: i for i in items}
        assert by_index[0]["input"] == "first"
        assert by_index[2]["input"] == "third"
        assert all(i["output"] == "an answer" and i["error"] is None for i in items)

    async def test_failures_are_reported_per_item_and_excluded_from_generated(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """A failing invocation yields an item with an error and does not count as generated."""

        async def _invoke(**kwargs):
            if kwargs["input_data"]["input"] == "bad":
                raise RuntimeError("endpoint exploded")
            return {"output": "fine"}

        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(side_effect=_invoke)

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            events = await _collect(
                invoke_endpoint_for_suggestions_stream(
                    db=test_db,
                    endpoint_id=str(uuid.uuid4()),
                    suggestions=[_Suggestion("good"), _Suggestion("bad")],
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )
            )

        by_index = {e["index"]: e for e in events if e["type"] == "item"}
        summary = next(e for e in events if e["type"] == "summary")

        assert by_index[0]["output"] == "fine"
        assert by_index[0]["error"] is None
        assert by_index[1]["output"] == ""
        assert by_index[1]["error"] == "endpoint exploded"
        assert summary == {"type": "summary", "generated": 1, "total": 2}

    async def test_empty_suggestions_emits_only_summary(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """No suggestions means no item events, and a zero summary."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "unused"})

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            events = await _collect(
                invoke_endpoint_for_suggestions_stream(
                    db=test_db,
                    endpoint_id=str(uuid.uuid4()),
                    suggestions=[],
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )
            )

        assert events == [{"type": "summary", "generated": 0, "total": 0}]
        mock_svc.invoke_endpoint.assert_not_awaited()

    async def test_every_invocation_gets_its_own_tenant_scoped_session(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Each suggestion is invoked on a session opened with the caller's tenant identity."""
        calls = []

        @contextmanager
        def _recording_ctx(*args, **kwargs):
            calls.append(args)
            yield test_db

        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "ok"})

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _recording_ctx),
        ):
            await _collect(
                invoke_endpoint_for_suggestions_stream(
                    db=test_db,
                    endpoint_id=str(uuid.uuid4()),
                    suggestions=[_Suggestion("a"), _Suggestion("b")],
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )
            )

        assert len(calls) == 2
        for args in calls:
            assert args == (test_org_id, authenticated_user_id, "")
