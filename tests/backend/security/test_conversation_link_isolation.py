"""Conversation-linking and trace-metrics caches are tenant-scoped.

Two organizations whose endpoints use the same conversation id (or whose spans
carry the same trace id) within the cache TTL must never read, consume or act on
each other's entries. Runs against the testcontainers Redis.
"""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.config.settings import get_redis_settings
from rhesis.backend.app.services.endpoint import off_loop
from rhesis.backend.app.services.invokers.sdk_invoker import SdkEndpointInvoker
from rhesis.backend.app.services.telemetry import conversation_linking as cl
from rhesis.backend.app.services.telemetry.trace_metrics_cache import (
    TraceMetricsDebounceCache,
)

_INPUT_KEY = "rhesis.conversation.input"
_OUTPUT_KEY = "rhesis.conversation.output"


def _id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def redis_cache(monkeypatch):
    """A ConversationLinkingCache connected to the real test Redis."""
    get_redis_settings.cache_clear()
    cache = cl.ConversationLinkingCache()
    cache.initialize()
    if not cache._using_redis:
        pytest.fail("test Redis is not reachable")
    monkeypatch.setattr(cl, "_cache", cache)
    yield cache
    cache.close()
    get_redis_settings.cache_clear()


@pytest.fixture
def orgs():
    """Two tenants, plus one conversation id and trace id they both use."""
    return SimpleNamespace(
        a=SimpleNamespace(org=_id(), project=_id()),
        b=SimpleNamespace(org=_id(), project=_id()),
        conversation_id=f"session-{uuid.uuid4().hex[:8]}",
        trace_id=uuid.uuid4().hex,
    )


def _endpoint(tenant) -> SimpleNamespace:
    return SimpleNamespace(
        id=_id(),
        organization_id=tenant.org,
        project_id=tenant.project,
        request_mapping={"query": "{{ input }}"},
    )


def _root_span(trace_id: str, project_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        trace_id=trace_id,
        span_id=uuid.uuid4().hex[:16],
        parent_span_id=None,
        project_id=project_id,
        attributes={_INPUT_KEY: "hello"},
    )


def _stored_row(trace_id: str, tenant) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        trace_id=trace_id,
        parent_span_id=None,
        organization_id=uuid.UUID(tenant.org),
        project_id=uuid.UUID(tenant.project),
    )


def _sdk_invoker(endpoint, input_data=None) -> SdkEndpointInvoker:
    invoker = SdkEndpointInvoker()
    invoker.context = SimpleNamespace(
        endpoint=endpoint, input_data=input_data or {}, db=None, trace_id=None
    )
    return invoker


@pytest.mark.unit
class TestPendingLinkIsolation:
    def test_other_org_does_not_reuse_parked_trace_id(self, redis_cache, orgs):
        trace_a = uuid.uuid4().hex
        cl.register_pending_conversation_link(
            trace_a, orgs.conversation_id, orgs.a.org, orgs.a.project
        )

        assert (
            cl.get_trace_id_from_pending_links(orgs.conversation_id, orgs.b.org, orgs.b.project)
            is None
        )
        assert (
            cl.get_trace_id_from_pending_links(orgs.conversation_id, orgs.a.org, orgs.a.project)
            == trace_a
        )

    def test_off_loop_lookup_ignores_other_org_link(self, redis_cache, orgs):
        trace_a = uuid.uuid4().hex
        cl.register_pending_conversation_link(
            trace_a, orgs.conversation_id, orgs.a.org, orgs.a.project
        )
        input_data = {"conversation_id": orgs.conversation_id}

        with patch(
            "rhesis.backend.app.crud.telemetry.get_trace_id_for_conversation",
            return_value=None,
        ):
            found_b = off_loop._existing_trace_id(None, _endpoint(orgs.b), input_data, orgs.b.org)
            found_a = off_loop._existing_trace_id(None, _endpoint(orgs.a), input_data, orgs.a.org)

        assert found_b is None
        assert found_a == trace_a

    def test_post_ingest_never_consumes_or_binds_to_other_org_link(self, redis_cache, orgs):
        cl.register_pending_conversation_link(
            orgs.trace_id, orgs.conversation_id, orgs.a.org, orgs.a.project
        )
        db = MagicMock()

        with (
            patch.object(cl, "update_conversation_id_for_trace", return_value=1) as update,
            patch("rhesis.backend.app.database.bind_scope_to_session") as bind,
        ):
            assert (
                cl.apply_pending_conversation_links(db, [_stored_row(orgs.trace_id, orgs.b)]) == 0
            )
            update.assert_not_called()

            # Org A's link is still there for org A's own spans.
            assert (
                cl.apply_pending_conversation_links(db, [_stored_row(orgs.trace_id, orgs.a)]) == 1
            )
            update.assert_called_once_with(db, orgs.trace_id, orgs.conversation_id, orgs.a.org)
            bind.assert_not_called()


@pytest.mark.unit
class TestPendingOutputIsolation:
    def test_other_org_span_does_not_receive_parked_output(self, redis_cache, orgs):
        _sdk_invoker(_endpoint(orgs.a))._park_mapped_output(
            {"trace_id": orgs.trace_id}, {"output": "org A secret answer"}
        )

        span_b = _root_span(orgs.trace_id, orgs.b.project)
        assert cl.inject_pending_output([span_b], orgs.b.org, orgs.b.project) == 0
        assert _OUTPUT_KEY not in span_b.attributes

        span_a = _root_span(orgs.trace_id, orgs.a.project)
        assert cl.inject_pending_output([span_a], orgs.a.org, orgs.a.project) == 1
        assert span_a.attributes[_OUTPUT_KEY] == "org A secret answer"

    def test_same_trace_id_outputs_stay_separate(self, redis_cache, orgs):
        cl.register_pending_output(orgs.trace_id, "from A", orgs.a.org, orgs.a.project)
        cl.register_pending_output(orgs.trace_id, "from B", orgs.b.org, orgs.b.project)

        span_a = _root_span(orgs.trace_id, orgs.a.project)
        span_b = _root_span(orgs.trace_id, orgs.b.project)
        cl.inject_pending_output([span_b], orgs.b.org, orgs.b.project)
        cl.inject_pending_output([span_a], orgs.a.org, orgs.a.project)

        assert span_a.attributes[_OUTPUT_KEY] == "from A"
        assert span_b.attributes[_OUTPUT_KEY] == "from B"


@pytest.mark.unit
class TestPendingFilesIsolation:
    def test_other_org_rows_never_get_parked_files(self, redis_cache, orgs):
        file_id = _id()
        _sdk_invoker(_endpoint(orgs.a), {"files": [{"id": file_id}]})._park_input_files(
            {"trace_id": orgs.trace_id}
        )
        db = MagicMock()
        row_b = _stored_row(orgs.trace_id, orgs.b)
        row_a = _stored_row(orgs.trace_id, orgs.a)

        with (
            patch("rhesis.backend.app.crud.file.link_file_to_entity") as link,
            patch("rhesis.backend.app.database.bind_scope_to_session") as bind,
        ):
            assert cl.apply_pending_files(db, [row_b]) == 0
            link.assert_not_called()

            assert cl.apply_pending_files(db, [row_a]) == 1
            link.assert_called_once_with(
                db, file_id=uuid.UUID(file_id), entity_id=row_a.id, entity_type="Trace"
            )
            bind.assert_not_called()


@pytest.mark.unit
class TestUnscopedLegacyEntries:
    def test_keys_from_older_releases_are_ignored(self, redis_cache, orgs):
        redis_cache._redis.set(f"convlink:reverse:{orgs.conversation_id}", "legacy", ex=60)
        redis_cache._redis.set(f"convlink:output:{orgs.trace_id}", "legacy", ex=60)
        redis_cache._redis.set(
            f"convlink:pending:{orgs.trace_id}",
            json.dumps({"conversation_id": "c", "organization_id": orgs.a.org}),
            ex=60,
        )

        assert (
            cl.get_trace_id_from_pending_links(orgs.conversation_id, orgs.b.org, orgs.b.project)
            is None
        )
        span = _root_span(orgs.trace_id, orgs.b.project)
        assert cl.inject_pending_output([span], orgs.b.org, orgs.b.project) == 0
        with patch.object(cl, "update_conversation_id_for_trace") as update:
            cl.apply_pending_conversation_links(MagicMock(), [_stored_row(orgs.trace_id, orgs.b)])
        update.assert_not_called()


@pytest.mark.unit
class TestTraceMetricsDebounceIsolation:
    @pytest.fixture
    def metrics_cache(self):
        get_redis_settings.cache_clear()
        cache = TraceMetricsDebounceCache()
        cache.initialize()
        if not cache._using_redis:
            pytest.fail("test Redis is not reachable")
        yield cache
        cache.close()

    def test_other_org_cannot_revoke_or_complete(self, metrics_cache, orgs):
        a, b, trace = orgs.a, orgs.b, orgs.trace_id
        assert metrics_cache.register_pending_eval(a.org, a.project, trace, "task-a") is None

        # Org B scheduling the same trace id gets no task id back to revoke.
        assert metrics_cache.register_pending_eval(b.org, b.project, trace, "task-b") is None
        assert metrics_cache.pop_pending_eval(b.org, b.project, trace) == "task-b"

        metrics_cache.mark_complete(b.org, b.project, trace)
        assert metrics_cache.is_complete(a.org, a.project, trace) is False
        assert metrics_cache.pop_pending_eval(a.org, a.project, trace) == "task-a"
