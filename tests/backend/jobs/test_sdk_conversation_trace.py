"""Multi-turn tests against SDK endpoints keep every turn on one trace (#3024).

SDK endpoints export their own spans, so no DeferredTraceData comes back from a
DB-free invocation. The conversation's trace id and the first-turn link have to
be carried some other way, or every turn starts a fresh trace.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.endpoint.service import EndpointService
from rhesis.backend.app.services.invokers.tracing import (
    DeferredConversationLink,
    persist_deferred_trace,
)
from rhesis.backend.jobs.execution.penelope_target import BackendEndpointTarget

TRACE_ID = "6de8b457a20371d641b02c66828cd0a0"
CONVERSATION_ID = "a9eedd03-9681-466b-8d87-0118d7e200ce"


def _sdk_endpoint() -> Endpoint:
    endpoint = MagicMock(spec=Endpoint)
    endpoint.name = "visit_prep_chat"
    endpoint.connection_type = "SDK"
    endpoint.disable_tracing = False
    endpoint.request_mapping = {"message": "{{ input }}"}
    return endpoint


async def _invoke_sdk(input_data: dict, invoker_result: dict) -> dict:
    service = EndpointService()
    with (
        patch("rhesis.backend.app.services.endpoint.service.create_invoker") as factory,
        patch(
            "rhesis.backend.app.services.endpoint.service.ConversationTracker"
            ".detect_stateless_mode",
            return_value=False,
        ),
    ):
        invoker = AsyncMock()
        invoker.automatic_tracing = True
        invoker.invoke.return_value = invoker_result
        factory.return_value = invoker

        return await service.invoke_endpoint(
            db=None,
            endpoint_id="ep-1",
            input_data=input_data,
            organization_id="org-1",
            endpoint=_sdk_endpoint(),
            deferred_trace=True,
        )


class TestDeferredSdkFirstTurnLink:
    @pytest.mark.asyncio
    async def test_first_turn_returns_conversation_link(self):
        result = await _invoke_sdk(
            {"input": "I have a headache"},
            {"output": "Where?", "conversation_id": CONVERSATION_ID, "trace_id": TRACE_ID},
        )

        link = result["_deferred_trace"]
        assert isinstance(link, DeferredConversationLink)
        assert (link.trace_id, link.conversation_id, link.organization_id) == (
            TRACE_ID,
            CONVERSATION_ID,
            "org-1",
        )

    @pytest.mark.asyncio
    async def test_later_turn_returns_no_link(self):
        result = await _invoke_sdk(
            {"input": "Behind my eyes", "conversation_id": CONVERSATION_ID},
            {"output": "Since when?", "conversation_id": CONVERSATION_ID, "trace_id": TRACE_ID},
        )

        assert "_deferred_trace" not in result

    def test_persist_applies_link(self):
        db = MagicMock()
        link = DeferredConversationLink(TRACE_ID, CONVERSATION_ID, "org-1")

        with patch.object(EndpointService, "_link_first_turn_trace") as link_turn:
            persist_deferred_trace(db, link)

        link_turn.assert_called_once_with(
            db=db,
            trace_id=TRACE_ID,
            conversation_id=CONVERSATION_ID,
            organization_id="org-1",
        )


def _target() -> BackendEndpointTarget:
    target = BackendEndpointTarget.__new__(BackendEndpointTarget)
    target.endpoint_id = "ep-1"
    target.organization_id = "org-1"
    target.user_id = "user-1"
    target.project_id = None
    target.test_execution_context = {"test_id": "test-1"}
    target.params = None
    target.test_parameters = None
    target.reported_version_info = None
    target._endpoint = MagicMock()
    target._current_trace_id = None
    target._deferred_traces = []
    target._invoke_max_attempts = 1
    target._invoke_retry_min_wait = 0.01
    target._invoke_retry_max_wait = 0.01
    target.endpoint_service = MagicMock()
    return target


class TestTargetReusesSdkTraceId:
    @pytest.mark.asyncio
    async def test_later_turns_reuse_first_turn_trace_id(self):
        target = _target()
        link = DeferredConversationLink(TRACE_ID, CONVERSATION_ID, "org-1")
        target.endpoint_service.invoke_endpoint = AsyncMock(
            side_effect=[
                {
                    "output": "Where?",
                    "conversation_id": CONVERSATION_ID,
                    "trace_id": TRACE_ID,
                    "_deferred_trace": link,
                },
                {"output": "Since when?", "conversation_id": CONVERSATION_ID, "trace_id": TRACE_ID},
            ]
        )

        await target.a_send_message("I have a headache")
        await target.a_send_message("Behind my eyes", conversation_id=CONVERSATION_ID)

        calls = target.endpoint_service.invoke_endpoint.await_args_list
        assert calls[0].kwargs["trace_id"] is None
        assert calls[1].kwargs["trace_id"] == TRACE_ID
        assert target._deferred_traces == [link]

    @pytest.mark.asyncio
    async def test_trace_id_taken_from_response_without_deferred_data(self):
        target = _target()
        target.endpoint_service.invoke_endpoint = AsyncMock(
            return_value={"output": "Hi", "trace_id": TRACE_ID}
        )

        await target.a_send_message("Hello")

        assert target._current_trace_id == TRACE_ID
        assert target._deferred_traces == []
