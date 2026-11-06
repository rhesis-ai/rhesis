"""Which metrics a project's traces are evaluated with (``_load_project_trace_metrics``)."""

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.jobs.telemetry.evaluate import _load_project_trace_metrics
from tests.backend.routes.fixtures.data_factories import MetricDataFactory


def _metric(db: Session, org_id: str, user_id: str, target: str) -> models.Metric:
    data = MetricDataFactory.orm_data(db, org_id, user_id, config={"target": {"on": target}})
    metric = models.Metric(**data)
    db.add(metric)
    db.flush()
    return metric


@pytest.mark.unit
class TestLoadProjectTraceMetrics:
    @pytest.fixture
    def metrics(self, test_db: Session, test_org_id: str, authenticated_user_id: str):
        return {
            "turn": _metric(test_db, test_org_id, authenticated_user_id, "turn"),
            "conversation": _metric(test_db, test_org_id, authenticated_user_id, "conversation"),
            "tool_call": _metric(test_db, test_org_id, authenticated_user_id, "tool_call"),
            "unassigned": _metric(test_db, test_org_id, authenticated_user_id, "turn"),
        }

    def _load(self, db, org_id, metrics, phase):
        assigned = [str(metrics[k].id) for k in ("turn", "conversation", "tool_call")]
        loaded = _load_project_trace_metrics(db, org_id, {"metric_ids": assigned}, phase=phase)
        return {m.id for m in loaded}

    def test_nothing_assigned_loads_nothing(self, test_db, test_org_id, metrics):
        assert _load_project_trace_metrics(test_db, test_org_id, {}, phase="turn") == []
        assert (
            _load_project_trace_metrics(test_db, test_org_id, {"metric_ids": []}, phase="turn")
            == []
        )

    def test_turn_phase_loads_what_doesnt_judge_the_conversation(
        self, test_db, test_org_id, metrics
    ):
        """A metric judging the conversation never scores a lone turn."""
        ids = self._load(test_db, test_org_id, metrics, "turn")
        assert ids == {metrics["turn"].id, metrics["tool_call"].id}

    def test_conversation_phase_loads_what_judges_the_conversation(
        self, test_db, test_org_id, metrics
    ):
        ids = self._load(test_db, test_org_id, metrics, "conversation")
        assert ids == {metrics["conversation"].id}
