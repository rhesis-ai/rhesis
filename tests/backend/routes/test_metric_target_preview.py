"""POST /metrics/targets/preview: what a target picks in a project's latest traces.

The traces are stored through the ingest route, then the preview is compared with what the
SDK's own ``Target.select`` picks, so the counts are the ones evaluation would see.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.constants import ConversationContext

from rhesis.backend.app.crud.telemetry import RECENT_TRACE_DAYS
from rhesis.backend.app.models.project import Project
from rhesis.backend.app.models.project_membership import ProjectMembership
from rhesis.backend.app.schemas.metric import (
    PREVIEW_TRACES_DEFAULT,
    PREVIEW_TRACES_LIMIT,
    TargetPreviewRequest,
)
from rhesis.backend.app.services.telemetry import target_preview
from rhesis.sdk.metrics.conditions import ConditionOp, SpanStatus, SpecialField
from rhesis.sdk.metrics.targets import Target, TargetKind

PREVIEW = "/metrics/targets/preview"
TRACES = "/telemetry/traces"

# Span names the ingest schema accepts.
ROOT_SPAN = "function.chat"
TOOL_SPAN = "ai.tool.invoke"
MODEL_SPAN = "ai.llm.invoke"
# What a tool span's input and output are read from.
TOOL_ARGUMENTS = "ai.tool.arguments"
TOOL_OUTPUT = AIAttributes.TOOL_OUTPUT_CONTENT
CHANNEL = "app.channel"
CONVERSATION_INPUT = ConversationContext.SpanAttributes.CONVERSATION_INPUT
CONVERSATION_OUTPUT = ConversationContext.SpanAttributes.CONVERSATION_OUTPUT


def _span(
    project_id: str,
    trace_id: str,
    name: str,
    started: datetime,
    attributes: Dict[str, Any],
    parent: Optional[str] = None,
    error: bool = False,
    millis: int = 100,
) -> Dict[str, Any]:
    return {
        "trace_id": trace_id,
        "span_id": uuid.uuid4().hex[:16],
        "parent_span_id": parent,
        "project_id": project_id,
        "environment": "development",
        "span_name": name,
        "span_kind": "INTERNAL",
        "start_time": started.isoformat(),
        "end_time": (started + timedelta(milliseconds=millis)).isoformat(),
        "status_code": "ERROR" if error else "OK",
        "attributes": attributes,
        "events": [],
        "links": [],
        "resource": {},
    }


def _tool(name: str, arguments: str, output: str, **attributes: Any) -> Dict[str, Any]:
    return {
        AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE,
        AIAttributes.TOOL_NAME: name,
        TOOL_ARGUMENTS: arguments,
        TOOL_OUTPUT: output,
        **attributes,
    }


def _store(client: TestClient, project_id: str, started: datetime, children: List[dict]) -> str:
    """A trace: a turn's root and ``children`` under it, as (name, attributes, kwargs)."""
    trace_id = uuid.uuid4().hex
    root = _span(
        project_id,
        trace_id,
        ROOT_SPAN,
        started,
        {CONVERSATION_INPUT: "Refund my order", CONVERSATION_OUTPUT: "Done"},
        millis=1000,
    )
    spans = [root] + [
        _span(
            project_id,
            trace_id,
            name,
            started + timedelta(milliseconds=10 * (i + 1)),
            attributes,
            parent=root["span_id"],
            **kwargs,
        )
        for i, (name, attributes, kwargs) in enumerate(children)
    ]
    response = client.post(TRACES, json={"spans": spans})
    assert response.status_code == status.HTTP_200_OK, response.text
    return trace_id


@pytest.fixture
def traces(authenticated_client: TestClient, db_project):
    """Three traces, newest first: two tool calls, one tool call, no tool call."""
    project_id = str(db_project.id)
    now = datetime.now(timezone.utc)
    refunds = _store(
        authenticated_client,
        project_id,
        now,
        [
            (TOOL_SPAN, _tool("issue_refund", '{"order": 1}', "refunded", **{CHANNEL: "web"}), {}),
            (
                TOOL_SPAN,
                _tool("cancel_order", '{"order": 1}', "x" * 2000, **{CHANNEL: "internal"}),
                {"error": True, "millis": 250},
            ),
        ],
    )
    lookup = _store(
        authenticated_client,
        project_id,
        now - timedelta(minutes=1),
        [(TOOL_SPAN, _tool("lookup_order", '{"order": 2}', "found"), {})],
    )
    chat = _store(
        authenticated_client,
        project_id,
        now - timedelta(minutes=2),
        [(MODEL_SPAN, {AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE}, {})],
    )
    return project_id, [refunds, lookup, chat]


def _preview(client: TestClient, project_id: str, target: Any, **body: Any):
    return client.post(PREVIEW, json={"project_id": project_id, "target": target, **body})


@pytest.mark.integration
class TestTargetPreview:
    def test_a_preset_counts_the_traces_and_units_it_picks(self, authenticated_client, traces):
        project_id, _ = traces

        response = _preview(authenticated_client, project_id, {"on": TargetKind.TOOL_CALL})

        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["traces"] == 3
        assert body["matching_traces"] == 2
        assert body["units"] == 3
        assert body["not_applicable_traces"] == 1

    def test_a_preset_named_by_itself_is_read(self, authenticated_client, traces):
        project_id, _ = traces

        body = _preview(authenticated_client, project_id, TargetKind.TOOL_CALL.value).json()

        assert body["units"] == 3

    def test_a_span_target_counts_only_the_spans_meeting_its_conditions(
        self, authenticated_client, traces
    ):
        project_id, (refunds, _, _) = traces
        target = {
            "on": TargetKind.SPAN,
            "where": [
                {
                    "field": SpecialField.KIND,
                    "op": ConditionOp.EQ,
                    "value": AIAttributes.OPERATION_TOOL_INVOKE,
                },
                {"field": CHANNEL, "op": ConditionOp.NE, "value": "internal"},
            ],
        }

        body = _preview(authenticated_client, project_id, target).json()

        # A span without the channel passes "!=": the lookup counts, the internal cancel doesn't.
        assert (body["matching_traces"], body["units"], body["not_applicable_traces"]) == (2, 2, 1)
        assert [s["name"] for s in body["samples"]] == ["issue_refund", "lookup_order"]
        assert body["samples"][0]["trace_id"] == refunds

    def test_a_target_matching_nothing_makes_every_trace_not_applicable(
        self, authenticated_client, traces
    ):
        project_id, _ = traces

        body = _preview(authenticated_client, project_id, {"on": TargetKind.RETRIEVAL}).json()

        assert body == {
            "traces": 3,
            "partial": False,
            "matching_traces": 0,
            "units": 0,
            "not_applicable_traces": 3,
            "samples": [],
            "target_summary": "each retrieval",
            "target_summary_short": "each retrieval",
        }

    def test_the_draft_target_is_described_as_a_saved_metric_would_be(
        self, authenticated_client, traces
    ):
        project_id, _ = traces
        target = {
            "on": TargetKind.TOOL_CALL,
            "name": "issue_refund",
            "where": [
                {"field": CHANNEL, "op": ConditionOp.NE, "value": "internal"},
                {"field": SpecialField.STATUS, "op": ConditionOp.EQ, "value": SpanStatus.OK},
            ],
        }

        body = _preview(authenticated_client, project_id, target).json()

        described = Target.coerce(target)
        assert body["target_summary"] == described.describe()
        assert body["target_summary_short"] == described.describe(short=True)
        assert body["target_summary"].startswith("each tool call named `issue_refund`")
        assert body["target_summary_short"] != body["target_summary"]

    def test_samples_show_each_unit_with_its_input_and_output_cut_short(
        self, authenticated_client, traces
    ):
        project_id, (refunds, lookup, _) = traces

        body = _preview(
            authenticated_client, project_id, {"on": TargetKind.TOOL_CALL, "name": "cancel_order"}
        ).json()

        [sample] = body["samples"]
        assert sample["trace_id"] == refunds
        assert sample["span_id"]
        assert sample["name"] == "cancel_order"
        assert sample["input"] == '{"order": 1}'
        assert len(sample["output"]) == target_preview.PREVIEW_TEXT_LIMIT
        assert sample["output"].endswith("…")
        assert sample["duration_ms"] == pytest.approx(250)
        assert sample["status"] == SpanStatus.ERROR

    def test_samples_are_capped_and_read_newest_trace_first(
        self, authenticated_client, traces, monkeypatch
    ):
        project_id, (refunds, lookup, _) = traces
        monkeypatch.setattr(target_preview, "PREVIEW_SAMPLES", 2)

        body = _preview(authenticated_client, project_id, {"on": TargetKind.TOOL_CALL}).json()

        assert body["units"] == 3
        assert [s["trace_id"] for s in body["samples"]] == [refunds, refunds]
        assert [s["status"] for s in body["samples"]] == [SpanStatus.OK, SpanStatus.ERROR]

    def test_a_turn_reads_the_turn_input_and_output(self, authenticated_client, traces):
        project_id, _ = traces

        body = _preview(authenticated_client, project_id, {"on": TargetKind.TURN}).json()

        assert (body["matching_traces"], body["units"]) == (3, 3)
        assert body["samples"][0]["input"] == "Refund my order"
        assert body["samples"][0]["output"] == "Done"

    def test_the_whole_run_is_one_unit_per_trace(self, authenticated_client, traces):
        project_id, (refunds, _, _) = traces

        body = _preview(authenticated_client, project_id, {"on": TargetKind.RUN}).json()

        assert (body["matching_traces"], body["units"]) == (3, 3)
        first = body["samples"][0]
        assert first["trace_id"] == refunds
        assert first["name"] == ROOT_SPAN
        assert (first["input"], first["output"]) == ("Refund my order", "Done")

    def test_a_conversation_is_only_a_trace_with_several_turns(self, authenticated_client, traces):
        project_id, _ = traces
        now = datetime.now(timezone.utc) + timedelta(minutes=1)
        trace_id = uuid.uuid4().hex
        turns = [
            _span(
                project_id,
                trace_id,
                ROOT_SPAN,
                now + timedelta(seconds=turn),
                {CONVERSATION_INPUT: f"Turn {turn}", CONVERSATION_OUTPUT: "Ok"},
            )
            for turn in range(2)
        ]
        response = authenticated_client.post(TRACES, json={"spans": turns})
        assert response.status_code == status.HTTP_200_OK, response.text

        body = _preview(authenticated_client, project_id, {"on": TargetKind.CONVERSATION}).json()

        assert body["traces"] == 4
        assert (body["matching_traces"], body["units"]) == (1, 1)
        assert body["not_applicable_traces"] == 3
        assert [sample["trace_id"] for sample in body["samples"]] == [trace_id]

    def test_traces_reads_only_the_latest(self, authenticated_client, traces):
        project_id, _ = traces

        body = _preview(
            authenticated_client, project_id, {"on": TargetKind.TOOL_CALL}, traces=2
        ).json()

        assert (body["traces"], body["matching_traces"], body["units"]) == (2, 2, 3)

    def test_traces_is_capped(self, authenticated_client, traces, monkeypatch):
        project_id, _ = traces
        monkeypatch.setattr(
            "rhesis.backend.app.schemas.metric.PREVIEW_TRACES_LIMIT", 1, raising=True
        )

        body = _preview(
            authenticated_client, project_id, {"on": TargetKind.TOOL_CALL}, traces=500
        ).json()

        assert (body["traces"], body["units"]) == (1, 2)

    def test_an_empty_project_has_nothing_to_preview(self, authenticated_client, db_project):
        body = _preview(authenticated_client, str(db_project.id), {"on": TargetKind.TOOL_CALL})

        assert body.json()["traces"] == 0

    def test_out_of_time_it_answers_with_what_it_read(
        self, authenticated_client, traces, monkeypatch
    ):
        project_id, (refunds, _, _) = traces
        monkeypatch.setattr(target_preview, "PREVIEW_TIME_BUDGET_S", 0.0)

        body = _preview(authenticated_client, project_id, {"on": TargetKind.TOOL_CALL}).json()

        assert body["partial"] is True
        # The newest trace is always read whole.
        assert (body["traces"], body["matching_traces"], body["units"]) == (1, 1, 2)
        assert body["not_applicable_traces"] == 0
        assert {sample["trace_id"] for sample in body["samples"]} == {refunds}

    def test_in_time_it_is_not_partial(self, authenticated_client, traces):
        project_id, _ = traces

        body = _preview(authenticated_client, project_id, {"on": TargetKind.TOOL_CALL}).json()

        assert body["partial"] is False

    def test_a_trace_whose_root_is_an_orphan_counts(self, authenticated_client, db_project):
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        orphan = _span(
            project_id,
            trace_id,
            TOOL_SPAN,
            datetime.now(timezone.utc),
            _tool("lookup_order", "{}", "found"),
            parent=uuid.uuid4().hex[:16],
        )
        response = authenticated_client.post(TRACES, json={"spans": [orphan]})
        assert response.status_code == status.HTTP_200_OK, response.text

        body = _preview(authenticated_client, project_id, {"on": TargetKind.TOOL_CALL}).json()

        assert (body["traces"], body["units"]) == (1, 1)

    def test_traces_older_than_the_window_are_left_out(self, authenticated_client, db_project):
        project_id = str(db_project.id)
        old = datetime.now(timezone.utc) - timedelta(days=RECENT_TRACE_DAYS + 1)
        _store(authenticated_client, project_id, old, [])

        body = _preview(authenticated_client, project_id, {"on": TargetKind.RUN}).json()

        assert body["traces"] == 0


@pytest.mark.integration
class TestTargetPreviewRefusals:
    @pytest.mark.parametrize(
        "target, named",
        [
            ({"on": "trajectory"}, "'trajectory' is not a target"),
            ({"on": TargetKind.SPAN, "where": []}, "A span target needs conditions"),
            (
                {
                    "on": TargetKind.SPAN,
                    "where": [{"field": SpecialField.KIND, "op": "~", "value": "x"}],
                },
                "op must be one of",
            ),
            (
                {
                    "on": TargetKind.SPAN,
                    "where": [
                        {"field": SpecialField.DURATION_MS, "op": ConditionOp.LT, "value": "a"}
                    ],
                },
                "compares with a number",
            ),
            ({"on": TargetKind.RUN, "read": {"input": "x"}}, "read is for a target"),
            ({"on": TargetKind.SPAN, "where": 5}, "where is a list"),
        ],
    )
    def test_a_bad_target_is_refused_naming_the_problem(
        self, authenticated_client, db_project, target, named
    ):
        response = _preview(authenticated_client, str(db_project.id), target)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()["detail"].startswith("Invalid target: ")
        assert named in response.json()["detail"]

    @pytest.mark.parametrize("error", [TypeError, OverflowError, RecursionError])
    def test_any_error_reading_a_target_is_a_422(
        self, authenticated_client, db_project, monkeypatch, error
    ):
        def fails(*_args, **_kwargs):
            raise error("the SDK tripped")

        monkeypatch.setattr("rhesis.sdk.metrics.targets.Target.coerce", fails)

        response = _preview(authenticated_client, str(db_project.id), {"on": TargetKind.RUN})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()["detail"] == "Invalid target: the SDK tripped"

    def test_traces_below_one_is_refused(self, authenticated_client, db_project):
        response = _preview(
            authenticated_client, str(db_project.id), {"on": TargetKind.TOOL_CALL}, traces=0
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.integration
class TestTargetPreviewProjects:
    @pytest.fixture
    def other_project(self, test_db, test_organization, db_user, db_status, authenticated_user_id):
        project = Project(
            name=f"Other {uuid.uuid4().hex[:8]}",
            is_active=True,
            user_id=db_user.id,
            owner_id=db_user.id,
            organization_id=test_organization.id,
            status_id=db_status.id,
        )
        test_db.add(project)
        test_db.flush()
        test_db.add(
            ProjectMembership(
                project_id=project.id,
                user_id=authenticated_user_id,
                organization_id=test_organization.id,
            )
        )
        test_db.flush()
        return project

    def test_only_the_asked_projects_traces_are_read(
        self, authenticated_client, traces, other_project
    ):
        project_id, _ = traces
        other_id = str(other_project.id)
        _store(
            authenticated_client,
            other_id,
            datetime.now(timezone.utc) + timedelta(minutes=1),
            [(TOOL_SPAN, _tool("other_tool", "{}", "ok"), {})],
        )

        mine = _preview(authenticated_client, project_id, {"on": TargetKind.TOOL_CALL}).json()
        theirs = _preview(authenticated_client, other_id, {"on": TargetKind.TOOL_CALL}).json()

        assert (mine["traces"], mine["units"]) == (3, 3)
        assert "other_tool" not in [s["name"] for s in mine["samples"]]
        assert (theirs["traces"], theirs["units"]) == (1, 1)
        assert theirs["samples"][0]["name"] == "other_tool"

    def test_a_project_the_caller_is_not_a_member_of_is_refused(
        self, test_db, client, test_org_id, traces, db_draft_project
    ):
        from tests.backend.fixtures.test_setup import create_test_api_token, create_test_user

        project_id, _ = traces
        # A plain member: the session user manages the org, which reaches every project.
        member = create_test_user(
            test_db,
            uuid.UUID(test_org_id),
            f"preview-member-{uuid.uuid4().hex[:8]}@rhesis-test.com",
            "Preview Member",
        )
        test_db.add(
            ProjectMembership(
                project_id=project_id, user_id=member.id, organization_id=uuid.UUID(test_org_id)
            )
        )
        token = create_test_api_token(test_db, member, name="Preview member token")
        test_db.commit()
        member_client = TestClient(client.app)
        member_client.headers.update({"Authorization": f"Bearer {token.token}"})
        target = {"on": TargetKind.TOOL_CALL}

        refused = _preview(member_client, str(db_draft_project.id), target)
        allowed = _preview(member_client, project_id, target)

        assert refused.status_code == status.HTTP_403_FORBIDDEN
        assert allowed.status_code == status.HTTP_200_OK
        assert allowed.json()["units"] == 3

    def test_without_auth_it_is_refused(self, client, db_project):
        response = _preview(client, str(db_project.id), {"on": TargetKind.TOOL_CALL})

        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.unit
class TestTargetPreviewRequest:
    def test_traces_defaults_and_is_capped(self):
        project_id = uuid.uuid4()

        assert TargetPreviewRequest(project_id=project_id, target="run").traces == (
            PREVIEW_TRACES_DEFAULT
        )
        capped = TargetPreviewRequest(project_id=project_id, target="run", traces=10_000)
        assert capped.traces == PREVIEW_TRACES_LIMIT
