"""Which metrics a project's traces are evaluated with (``load_project_trace_metrics``)."""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.telemetry.evaluation_context import (
    CONVERSATION_PHASE,
    TRACE_PHASE,
    TURN_PHASE,
    judged_in_phase,
    load_project_trace_metrics,
)
from tests.backend.routes.fixtures.data_factories import MetricDataFactory


def _metric(db: Session, org_id: str, user_id: str, target: str) -> models.Metric:
    data = MetricDataFactory.orm_data(db, org_id, user_id, config={"target": {"on": target}})
    metric = models.Metric(**data)
    db.add(metric)
    db.flush()
    return metric


@pytest.mark.unit
class TestJudgedInPhase:
    @pytest.mark.parametrize(
        "target, phases",
        [
            ("turn", {TURN_PHASE, TRACE_PHASE}),
            ("tool_call", {TURN_PHASE, TRACE_PHASE}),
            (None, {TURN_PHASE, TRACE_PHASE}),
            ("run", {TRACE_PHASE, CONVERSATION_PHASE}),
            ("conversation", {CONVERSATION_PHASE}),
        ],
    )
    def test_each_target_is_judged_once_per_trace(self, target, phases):
        """A conversation's turns and its quiet phase never judge the same metric twice."""
        judged = {
            phase
            for phase in (TURN_PHASE, TRACE_PHASE, CONVERSATION_PHASE)
            if judged_in_phase(target, phase)
        }
        assert judged == phases


@pytest.mark.unit
class TestLoadProjectTraceMetrics:
    @pytest.fixture
    def metrics(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        return {
            target: _metric(test_db, test_org_id, authenticated_user_id, target)
            for target in ("turn", "conversation", "tool_call", "run")
        } | {"unassigned": _metric(test_db, test_org_id, authenticated_user_id, "turn")}

    def _load(self, db, org_id, metrics, phase):
        assigned = [str(metrics[k].id) for k in ("turn", "conversation", "tool_call", "run")]
        loaded = load_project_trace_metrics(db, org_id, {"metric_ids": assigned}, phase=phase)
        return {m.id for m in loaded}

    def test_nothing_assigned_loads_nothing(self, test_db, test_org_id, metrics):
        assert load_project_trace_metrics(test_db, test_org_id, {}, phase=TURN_PHASE) == []
        assert (
            load_project_trace_metrics(test_db, test_org_id, {"metric_ids": []}, phase=TURN_PHASE)
            == []
        )

    def test_a_conversations_turn_loads_turn_and_span_targets(self, test_db, test_org_id, metrics):
        """The whole run and the conversation wait until every turn is in."""
        ids = self._load(test_db, test_org_id, metrics, TURN_PHASE)
        assert ids == {metrics["turn"].id, metrics["tool_call"].id}

    def test_a_trace_without_a_conversation_loads_all_but_the_conversation(
        self, test_db, test_org_id, metrics
    ):
        """Its one turn is the whole run; a metric judging the conversation never scores it."""
        ids = self._load(test_db, test_org_id, metrics, TRACE_PHASE)
        assert ids == {metrics["turn"].id, metrics["tool_call"].id, metrics["run"].id}

    def test_a_quiet_conversation_loads_whole_trace_targets(self, test_db, test_org_id, metrics):
        ids = self._load(test_db, test_org_id, metrics, CONVERSATION_PHASE)
        assert ids == {metrics["conversation"].id, metrics["run"].id}
