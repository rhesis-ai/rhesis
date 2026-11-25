"""POST /telemetry/v1/traces: OTLP/HTTP ingest of OpenTelemetry GenAI-convention traces."""

import uuid
from urllib.parse import urlsplit

import pytest
import requests
from celery.exceptions import Retry
from fastapi import status
from fastapi.testclient import TestClient
from google.rpc import status_pb2
from opentelemetry.exporter.otlp.proto.http import Compression
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse
from opentelemetry.sdk.trace.export import SpanExportResult
from sqlalchemy.exc import DataError

from rhesis.backend.app import models
from rhesis.backend.app.auth import quota_gates
from rhesis.backend.app.features import FeatureRegistry
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.quota.enforcement import QuotaVerdict
from rhesis.backend.app.routers import telemetry_intake
from rhesis.backend.app.services.telemetry import admission
from rhesis.backend.app.services.telemetry import ingest as ingest_service
from rhesis.backend.app.services.telemetry.ingest import (
    IngestJob,
    SpanStorageError,
    UnstorableSpans,
)
from rhesis.backend.ee.otlp import conversation_join
from rhesis.backend.ee.otlp.translate import translate_request
from rhesis.backend.jobs.telemetry import ingest as ingest_jobs
from tests.backend.ee.otlp import fixtures as fx
from tests.backend.fixtures.database import TestingSessionLocal
from tests.backend.fixtures.rls import scope_to_project

URL = "/telemetry/v1/traces"


def post(client: TestClient, body: bytes, content_type=fx.PROTOBUF, encoding=None, **headers):
    headers = {"Content-Type": content_type, **headers}
    if encoding:
        headers["Content-Encoding"] = encoding
    return client.post(URL, content=body, headers=headers)


def export_response(response) -> ExportTraceServiceResponse:
    message = ExportTraceServiceResponse()
    message.ParseFromString(response.content)
    return message


def rpc_status(response) -> status_pb2.Status:
    message = status_pb2.Status()
    message.ParseFromString(response.content)
    return message


def stored(test_db, project_id, trace_id: str):
    scope_to_project(test_db, project_id)
    return test_db.query(models.Trace).filter(models.Trace.trace_id == trace_id).all()


def without_conversation(spans) -> bytes:
    """Spans encoded without ``gen_ai.conversation.id``."""
    request = fx.export_request(spans)
    for resource in request.resource_spans:
        for scope in resource.scope_spans:
            for span in scope.spans:
                kept = [a for a in span.attributes if a.key != "gen_ai.conversation.id"]
                del span.attributes[:]
                span.attributes.extend(kept)
    return request.SerializeToString()


def list_traces(client: TestClient, project_id, **params) -> list:
    response = client.get("/telemetry/traces", params={"project_id": str(project_id), **params})
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["traces"]


@pytest.mark.integration
class TestIngest:
    def test_protobuf_ingest_stores_translated_spans(
        self, authenticated_client, test_db, db_project
    ):
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(authenticated_client, fx.protobuf_body(trace.spans))

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == fx.PROTOBUF
        assert not export_response(response).HasField("partial_success")
        rows = {r.span_id: r for r in stored(test_db, db_project.id, trace.trace_id)}
        assert len(rows) == len(trace.spans)
        root = rows[format(trace.root.context.span_id, "016x")]
        assert root.span_name == "ai.agent.invoke"
        assert root.parent_span_id is None
        assert root.span_type == "agent.invoke"
        assert root.environment == "production"
        assert root.conversation_id == "conv-research-1"
        assert root.attributes["rhesis.conversation.input"].startswith("Plan a weekend")

    def test_json_response_for_json_request(self, authenticated_client, db_project):
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(authenticated_client, fx.json_body(trace.spans), fx.JSON)

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == fx.JSON
        assert response.json() == {}

    def test_gzip_and_json_resend_of_the_same_trace_is_not_stored_twice(
        self, authenticated_client, test_db, db_project
    ):
        trace = fx.research_run(project_id=str(db_project.id))

        for body, content_type, encoding in [
            (fx.gzip_body(trace.spans), fx.PROTOBUF, "gzip"),
            (fx.json_body(trace.spans), fx.JSON, None),
            (fx.protobuf_body(trace.spans), fx.PROTOBUF, None),
        ]:
            response = post(authenticated_client, body, content_type, encoding)
            assert response.status_code == status.HTTP_200_OK

        assert len(stored(test_db, db_project.id, trace.trace_id)) == len(trace.spans)

    def test_partial_success_reports_rejected_spans(
        self, authenticated_client, test_db, db_project
    ):
        trace = fx.research_run(project_id=str(db_project.id))
        request = fx.export_request(trace.spans)
        request.resource_spans[0].scope_spans[0].spans[0].span_id = b"\x01"

        response = post(authenticated_client, request.SerializeToString())

        assert response.status_code == status.HTTP_200_OK
        partial = export_response(response).partial_success
        assert partial.rejected_spans == 1
        assert "span_id" in partial.error_message
        assert len(stored(test_db, db_project.id, trace.trace_id)) == len(trace.spans) - 1


@pytest.mark.integration
class TestTraceList:
    def test_list_fields_for_a_genai_trace(self, authenticated_client, db_project):
        trace = fx.research_run(project_id=str(db_project.id))
        post(authenticated_client, fx.protobuf_body(trace.spans))

        [row] = [
            t
            for t in list_traces(authenticated_client, db_project.id)
            if t["trace_id"] == trace.trace_id
        ]
        assert row["conversation_input"] == "Plan a weekend trip to Lisbon"
        assert row["span_count"] == len(trace.spans)
        assert row["root_operation"] == "ai.agent.invoke"
        assert row["agent_name"] == fx.AGENT
        # Only the two chat spans count (1060 + 900); the agent's aggregate does not.
        assert row["total_tokens"] == 1960

    def test_filter_by_agent(self, authenticated_client, db_project):
        trace = fx.research_run(project_id=str(db_project.id), conversation_id=None)
        post(authenticated_client, fx.protobuf_body(trace.spans))

        assert (
            fx.AGENT
            in authenticated_client.get(
                "/telemetry/agents", params={"project_id": str(db_project.id)}
            ).json()
        )
        # The sub-agent ran in the trace too.
        for agent in (fx.AGENT, "researcher"):
            ids = [
                t["trace_id"] for t in list_traces(authenticated_client, db_project.id, agent=agent)
            ]
            assert trace.trace_id in ids
        assert not list_traces(authenticated_client, db_project.id, agent="nobody")

    def test_span_facets_and_filter_by_agent(self, authenticated_client, db_project):
        trace = fx.research_run(project_id=str(db_project.id), conversation_id=None)
        post(authenticated_client, fx.protobuf_body(trace.spans))
        params = {"project_id": str(db_project.id)}

        facets = authenticated_client.get("/telemetry/spans/facets", params=params).json()
        assert {f["value"] for f in facets["agents"]} >= {fx.AGENT, "researcher"}

        spans = authenticated_client.get(
            "/telemetry/spans", params={**params, "agent": "researcher"}
        ).json()["spans"]
        assert spans and all(s["span_name"] == "ai.agent.invoke" for s in spans)


@pytest.mark.integration
class TestSplitDelivery:
    def test_children_first_root_last(self, authenticated_client, test_db, db_project):
        trace = fx.research_run(project_id=str(db_project.id))
        children = trace.children

        post(authenticated_client, fx.protobuf_body(children[:3]))
        post(authenticated_client, fx.protobuf_body(children[3:]))
        assert not [
            t
            for t in list_traces(authenticated_client, db_project.id)
            if t["trace_id"] == trace.trace_id and t["root_operation"] == "ai.agent.invoke"
        ]
        post(authenticated_client, fx.protobuf_body([trace.root]))

        [row] = [
            t
            for t in list_traces(authenticated_client, db_project.id)
            if t["trace_id"] == trace.trace_id
        ]
        assert row["span_count"] == len(trace.spans)
        assert row["conversation_input"].startswith("Plan a weekend")
        assert row["total_tokens"] == 1960

    def test_second_turn_joins_the_first_turns_trace(
        self, authenticated_client, test_db, db_project
    ):
        project_id = str(db_project.id)
        conversation = f"conv-{uuid.uuid4()}"
        turn_1 = fx.research_run(project_id=project_id, conversation_id=conversation)
        turn_2 = fx.research_run(
            project_id=project_id,
            conversation_id=conversation,
            question="And what about Porto?",
            answer="Porto will be cloudy.",
            history=[("user", "Plan a weekend trip"), ("assistant", "Lisbon will be sunny.")],
        )
        post(authenticated_client, fx.protobuf_body(turn_1.spans))
        # Only the root of turn 2 carries the conversation id, like a minimal exporter.
        post(authenticated_client, without_conversation(turn_2.children))
        post(authenticated_client, fx.protobuf_body([turn_2.root]))
        # A retry of an early turn-2 batch arriving after the join follows it.
        post(authenticated_client, fx.protobuf_body(turn_2.children[:2]))

        assert stored(test_db, project_id, turn_2.trace_id) == []
        rows = stored(test_db, project_id, turn_1.trace_id)
        assert len(rows) == len(turn_1.spans) + len(turn_2.spans)
        moved = [r for r in rows if r.attributes.get("rhesis.otlp.source_trace_id")]
        assert len(moved) == len(turn_2.spans)
        assert {r.conversation_id for r in rows} == {conversation}
        roots = sorted((r for r in rows if r.parent_span_id is None), key=lambda r: r.start_time)
        assert [r.attributes["rhesis.conversation.input"] for r in roots] == [
            "Plan a weekend trip to Lisbon",
            "And what about Porto?",
        ]

        listed = [
            t
            for t in list_traces(authenticated_client, project_id, trace_type="Multi-Turn")
            if t["conversation_id"] == conversation
        ]
        assert [t["trace_id"] for t in listed] == [turn_1.trace_id]
        # Still findable by the id the turn arrived under (as other trace backends show it).
        found = list_traces(authenticated_client, project_id, search=turn_2.trace_id)
        assert [t["trace_id"] for t in found] == [turn_1.trace_id]

    def test_turns_stored_out_of_order_end_on_the_first_turns_trace(
        self, authenticated_client, test_db, db_project
    ):
        """Parallel workers can store turn 2 before turn 1; the conversation still
        ends up under turn 1's id, and later spans of any turn follow it."""
        project_id = str(db_project.id)
        conversation = f"conv-{uuid.uuid4()}"
        turns = [
            fx.research_run(project_id=project_id, conversation_id=conversation, question=q)
            for q in ("first question", "second question", "third question")
        ]

        post(authenticated_client, fx.protobuf_body(turns[1].spans))
        post(authenticated_client, fx.protobuf_body(turns[0].spans))
        post(authenticated_client, fx.protobuf_body(turns[2].spans))
        # A late retry of turn 2, which was the anchor for a moment.
        post(authenticated_client, fx.protobuf_body(turns[1].children[:3]))

        first = turns[0].trace_id
        assert stored(test_db, project_id, turns[1].trace_id) == []
        assert stored(test_db, project_id, turns[2].trace_id) == []
        rows = stored(test_db, project_id, first)
        assert len(rows) == sum(len(t.spans) for t in turns)
        roots = sorted((r for r in rows if r.parent_span_id is None), key=lambda r: r.start_time)
        assert [r.attributes["rhesis.conversation.input"] for r in roots] == [
            "first question",
            "second question",
            "third question",
        ]
        # Every moved span keeps the id it arrived under, even after two moves.
        sources = {r.attributes.get("rhesis.otlp.source_trace_id") for r in rows}
        assert sources == {None, turns[1].trace_id, turns[2].trace_id}

    def test_two_turns_in_one_request_share_the_first_turns_trace(
        self, authenticated_client, test_db, db_project
    ):
        project_id = str(db_project.id)
        conversation = f"conv-{uuid.uuid4()}"
        turn_1, turn_2 = (
            fx.research_run(project_id=project_id, conversation_id=conversation, question=q)
            for q in ("first question", "second question")
        )

        post(authenticated_client, fx.protobuf_body(turn_1.spans + turn_2.spans))

        assert stored(test_db, project_id, turn_2.trace_id) == []
        rows = stored(test_db, project_id, turn_1.trace_id)
        assert len(rows) == len(turn_1.spans) + len(turn_2.spans)
        sources = [r.attributes.get("rhesis.otlp.source_trace_id") for r in rows]
        assert sources.count(turn_2.trace_id) == len(turn_2.spans)

    def test_spans_left_behind_an_alias_follow_the_next_batch(
        self, authenticated_client, test_db, db_project
    ):
        """An alias written by a job that then rolled back: the turn's stored spans
        stayed on its own trace, and its next batch moves them."""
        project_id = str(db_project.id)
        conversation = f"conv-{uuid.uuid4()}"
        turn_1 = fx.research_run(project_id=project_id, conversation_id=conversation)
        turn_2 = fx.research_run(project_id=project_id, conversation_id=conversation)
        post(authenticated_client, fx.protobuf_body(turn_1.spans))
        post(authenticated_client, without_conversation(turn_2.children[:-1]))
        assert len(stored(test_db, project_id, turn_2.trace_id)) == len(turn_2.children) - 1

        conversation_join._aliases.set(
            str(db_project.organization_id), project_id, turn_2.trace_id, turn_1.trace_id
        )
        post(authenticated_client, without_conversation(turn_2.children[-1:]))

        assert stored(test_db, project_id, turn_2.trace_id) == []
        rows = stored(test_db, project_id, turn_1.trace_id)
        assert len(rows) == len(turn_1.spans) + len(turn_2.children)

    def test_traces_without_a_conversation_stay_apart(
        self, authenticated_client, test_db, db_project
    ):
        project_id = str(db_project.id)
        first = fx.research_run(project_id=project_id, conversation_id=None)
        second = fx.research_run(project_id=project_id, conversation_id=None)

        post(authenticated_client, fx.protobuf_body(first.spans))
        post(authenticated_client, fx.protobuf_body(second.spans))

        assert len(stored(test_db, project_id, first.trace_id)) == len(first.spans)
        assert len(stored(test_db, project_id, second.trace_id)) == len(second.spans)


@pytest.mark.integration
class TestErrors:
    def test_unauthenticated(self, client, db_project):
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(client, fx.protobuf_body(trace.spans))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers["content-type"] == fx.PROTOBUF
        assert rpc_status(response).message

    def test_invalid_token(self, client, db_project):
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(
            client, fx.protobuf_body(trace.spans), Authorization="Bearer rh-not-a-real-token"
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers["content-type"] == fx.PROTOBUF
        assert rpc_status(response).code == 16  # UNAUTHENTICATED

    def test_unsupported_content_type(self, authenticated_client, db_project):
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(authenticated_client, fx.protobuf_body(trace.spans), "text/plain")

        assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        assert response.headers["content-type"] == fx.PROTOBUF
        assert rpc_status(response).code == 3  # INVALID_ARGUMENT
        assert "Content-Type" in rpc_status(response).message

    def test_no_project(self, authenticated_client):
        trace = fx.research_run()

        response = post(authenticated_client, fx.json_body(trace.spans), fx.JSON)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "rhesis.project_id" in response.json()["message"]

    def test_project_the_caller_cannot_access(self, authenticated_client):
        trace = fx.research_run(project_id=str(uuid.uuid4()))

        response = post(authenticated_client, fx.protobuf_body(trace.spans))

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert rpc_status(response).code == 7  # PERMISSION_DENIED

    def test_undecodable(self, authenticated_client):
        response = post(authenticated_client, b"\xff\xfe not protobuf")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert rpc_status(response).code == 3  # INVALID_ARGUMENT

    def test_not_licensed_is_not_found(self, authenticated_client, monkeypatch, db_project):
        monkeypatch.setattr(FeatureRegistry, "is_available", classmethod(lambda *_a: False))
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(authenticated_client, fx.protobuf_body(trace.spans))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert rpc_status(response).code == 5  # NOT_FOUND

    def test_backstop_answers_429_with_retry_after(
        self, authenticated_client, monkeypatch, db_project
    ):
        verdict = QuotaVerdict(
            resource=QuotaResource.TRACING_SPANS,
            used=10,
            limit=1,
            allowed=False,
            over_limit=True,
            kind="flow",
            period_end=None,
        )
        monkeypatch.setattr(quota_gates, "check_backstop", lambda *_args: verdict)
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(authenticated_client, fx.json_body(trace.spans), fx.JSON)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.headers["retry-after"] == "30"
        assert response.json()["message"]


def limit(monkeypatch, **changes):
    limits = telemetry_intake.settings().model_copy(update=changes)
    monkeypatch.setattr(telemetry_intake, "settings", lambda: limits)
    return limits


@pytest.mark.integration
class TestLimits:
    def test_body_over_the_limit(self, authenticated_client, test_db, monkeypatch, db_project):
        limit(monkeypatch, max_body_bytes=100)
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(authenticated_client, fx.protobuf_body(trace.spans))

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "retry-after" not in response.headers
        assert stored(test_db, db_project.id, trace.trace_id) == []

    def test_gzip_bomb(self, authenticated_client, monkeypatch, db_project):
        limit(monkeypatch, max_decompressed_bytes=1024)
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(authenticated_client, fx.gzip_body(trace.spans), encoding="gzip")

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    def test_too_many_spans(self, authenticated_client, monkeypatch, db_project):
        limit(monkeypatch, max_spans_per_request=3)
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(authenticated_client, fx.protobuf_body(trace.spans))

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    def test_long_values_are_cut_and_marked(
        self, authenticated_client, test_db, monkeypatch, db_project
    ):
        limit(monkeypatch, max_attribute_chars=1000)
        trace = fx.research_run(project_id=str(db_project.id), answer="y" * 5000)

        post(authenticated_client, fx.protobuf_body(trace.spans))

        root = next(
            r for r in stored(test_db, db_project.id, trace.trace_id) if r.parent_span_id is None
        )
        assert len(root.attributes["rhesis.conversation.output"]) == 1000
        assert "rhesis.conversation.output" in root.attributes["rhesis.truncated_attributes"]
        assert "gen_ai.output.messages" in root.attributes["rhesis.truncated_attributes"]

    def test_process_busy_answers_503(self, authenticated_client, monkeypatch, db_project):
        limit(monkeypatch, max_concurrent_requests=1)
        monkeypatch.setattr(admission.inflight, "requests", 1)
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(authenticated_client, fx.protobuf_body(trace.spans))

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.headers["retry-after"] == "30"

    def test_a_busy_process_refuses_before_authenticating(self, client, monkeypatch):
        """The slot is taken first, so a burst never reaches the database-backed auth."""
        limit(monkeypatch, max_concurrent_requests=1)
        monkeypatch.setattr(admission.inflight, "requests", 1)

        response = post(client, b"", Authorization="Bearer rh-not-a-token")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert rpc_status(response).code == 14  # UNAVAILABLE
        assert admission.inflight.requests == 1

    def test_the_slot_is_released_after_each_request(self, authenticated_client, db_project):
        before = admission.inflight.requests
        trace = fx.research_run(project_id=str(db_project.id))

        post(authenticated_client, fx.protobuf_body(trace.spans))
        post(authenticated_client, b"not protobuf")
        post(authenticated_client, b"", Authorization="Bearer rh-not-a-token")

        assert admission.inflight.requests == before
        assert admission.inflight.bytes == 0

    def test_a_gzip_body_reserves_its_decompressed_allowance(
        self, authenticated_client, monkeypatch, db_project
    ):
        """A small gzip body still counts as the most it may inflate to, until inflated."""
        limit(
            monkeypatch,
            max_inflight_bytes=40 * 1024 * 1024,
            max_decompressed_bytes=32 * 1024 * 1024,
        )
        monkeypatch.setattr(admission.inflight, "bytes", 10 * 1024 * 1024)
        trace = fx.research_run(project_id=str(db_project.id))

        gzip = post(authenticated_client, fx.gzip_body(trace.spans), encoding="gzip")
        plain = post(authenticated_client, fx.protobuf_body(trace.spans))

        assert gzip.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert plain.status_code == status.HTTP_200_OK

    def test_inflight_bytes_count_the_decompressed_body(
        self, authenticated_client, monkeypatch, db_project
    ):
        trace = fx.research_run(project_id=str(db_project.id), answer="y" * 100_000)
        compressed, raw = fx.gzip_body(trace.spans), fx.protobuf_body(trace.spans)
        cap = (len(compressed) + len(raw)) // 2
        assert len(compressed) < cap < len(raw)
        limit(monkeypatch, max_inflight_bytes=cap)

        response = post(authenticated_client, compressed, encoding="gzip")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.headers["retry-after"] == "30"
        assert rpc_status(response).code == 14  # UNAVAILABLE

    def test_org_rate_answers_429(self, authenticated_client, monkeypatch, db_project):
        """Counted in the real (test) Redis, shared by every API process."""
        trace = fx.research_run(project_id=str(db_project.id))
        body = fx.protobuf_body(trace.spans)
        limit(monkeypatch, org_bytes_per_minute=len(body) * 2 - 1)
        monkeypatch.setattr(admission, "_ORG_KEY", f"test-ingest:{uuid.uuid4()}:")

        assert post(authenticated_client, body).status_code == status.HTTP_200_OK
        response = post(authenticated_client, body)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert 1 <= int(response.headers["retry-after"]) <= 60

    def test_deep_queue_answers_503(self, authenticated_client, monkeypatch, db_project):
        limit(monkeypatch, max_queue_depth=5)
        monkeypatch.setattr(admission._queue_depth, "get", lambda: 5)
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(authenticated_client, fx.protobuf_body(trace.spans))

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_broker_down_answers_503(self, authenticated_client, monkeypatch, db_project):
        def broken(*_args):
            raise ConnectionError("redis is down")

        monkeypatch.setattr(ingest_jobs, "enqueue_ingest", broken)
        trace = fx.research_run(project_id=str(db_project.id))

        response = post(authenticated_client, fx.protobuf_body(trace.spans))

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.headers["retry-after"] == "30"

    def test_big_requests_are_split_into_several_messages(
        self, authenticated_client, test_db, inline_trace_ingest, monkeypatch, db_project
    ):
        limit(monkeypatch, max_message_bytes=1024)
        trace = fx.research_run(project_id=str(db_project.id))

        post(authenticated_client, fx.protobuf_body(trace.spans))

        assert len(inline_trace_ingest) > 1
        assert len(stored(test_db, db_project.id, trace.trace_id)) == len(trace.spans)


@pytest.mark.integration
class TestIngestTask:
    """The Celery task that stores a queued message, run in-process."""

    @pytest.fixture
    def message(self, test_db, monkeypatch, db_project):
        def session():
            return TestingSessionLocal(
                bind=test_db.get_bind(), join_transaction_mode="create_savepoint"
            )

        monkeypatch.setattr(ingest_jobs, "SessionLocal", session)
        monkeypatch.setattr(ingest_jobs, "bind_scope_to_session", lambda *_args: None)
        trace = fx.research_run(project_id=str(db_project.id))
        spans = translate_request(fx.export_request(trace.spans)).spans
        job = IngestJob(spans, str(db_project.organization_id), None, str(db_project.id))
        return job.to_message()

    def test_values_the_database_refuses_are_dropped_not_retried(self, monkeypatch, message):
        def refuse(*_args):
            raise DataError("INSERT ...", {}, ValueError("invalid byte sequence"))

        monkeypatch.setattr(ingest_service, "store_spans", refuse)
        monkeypatch.setattr(ingest_jobs.ingest_spans, "retry", self._no_retry)

        result = ingest_jobs.ingest_spans.run(message)

        assert result["stored"] == 0
        assert result["received"] == len(IngestJob.from_message(message).spans)

    def test_other_storage_errors_are_retried(self, monkeypatch, message):
        retried = []

        def fail(*_args):
            raise RuntimeError("connection reset")

        def retry(exc=None, **_kwargs):
            retried.append(exc)
            return Retry()

        monkeypatch.setattr(ingest_service, "store_spans", fail)
        monkeypatch.setattr(ingest_jobs.ingest_spans, "retry", retry)

        with pytest.raises(Retry):
            ingest_jobs.ingest_spans.run(message)

        assert len(retried) == 1
        assert isinstance(retried[0], SpanStorageError)
        assert not isinstance(retried[0], UnstorableSpans)

    @staticmethod
    def _no_retry(*_args, **_kwargs):
        raise AssertionError("must not retry")


class _TestClientAdapter(requests.adapters.BaseAdapter):
    """Hands requests from the real OTLP exporter to the FastAPI test client."""

    def __init__(self, client: TestClient) -> None:
        super().__init__()
        self._client = client

    def send(self, request, **kwargs):
        reply = self._client.request(
            request.method,
            urlsplit(request.url).path,
            content=request.body,
            headers=dict(request.headers),
        )
        response = requests.Response()
        response.status_code = reply.status_code
        response._content = reply.content
        response.headers = requests.structures.CaseInsensitiveDict(reply.headers)
        response.url = request.url
        response.request = request
        return response

    def close(self) -> None:
        pass


@pytest.mark.integration
def test_opentelemetry_sdk_exporter_end_to_end(authenticated_client, test_db, db_project):
    """The stock OTLPSpanExporter (http/protobuf, gzip) as Alloy or a collector would send."""
    session = requests.Session()
    session.mount("http://", _TestClientAdapter(authenticated_client))
    exporter = OTLPSpanExporter(
        endpoint="http://testserver/telemetry/v1/traces",
        session=session,
        compression=Compression.Gzip,
    )
    trace = fx.research_run(project_id=str(db_project.id))

    assert exporter.export(trace.spans) == SpanExportResult.SUCCESS

    rows = stored(test_db, db_project.id, trace.trace_id)
    assert len(rows) == len(trace.spans)
    assert {r.span_name for r in rows} == {"ai.agent.invoke", "ai.llm.invoke", "ai.tool.invoke"}
