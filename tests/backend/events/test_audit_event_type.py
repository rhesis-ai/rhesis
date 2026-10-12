"""``AuditRecorded`` and ``FieldChange``: the typed shape of an audit entry."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rhesis.backend.events.types import AuditRecorded, ChangeSummary, FieldChange


def _event(**overrides) -> AuditRecorded:
    fields = {
        "occurred_at": datetime.now(timezone.utc),
        "organization_id": uuid4(),
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "source": "test",
        "action": "endpoint.updated",
        "outcome": "success",
        "actor_type": "user",
        "channel": "web",
    }
    fields.update(overrides)
    return AuditRecorded(**fields)


class TestAuditRecorded:
    def test_builds_with_changes(self):
        event = _event(
            changes=(
                FieldChange(field="name", kind="value", before="a", after="b"),
                FieldChange(field="auth_token", kind="secret"),
            )
        )
        assert event.event_type == "audit.recorded"
        assert [c.field for c in event.changes] == ["name", "auth_token"]

    @pytest.mark.parametrize("action", ["Endpoint.updated", "endpoint:update", "endpoint", ""])
    def test_rejects_malformed_action(self, action):
        with pytest.raises(ValidationError):
            _event(action=action)

    def test_rejects_unknown_outcome_and_channel(self):
        with pytest.raises(ValidationError):
            _event(outcome="ok")
        with pytest.raises(ValidationError):
            _event(channel="ci")

    def test_entity_type_must_match_action_resource(self):
        assert _event(entity_type="endpoint").entity_type == "endpoint"
        with pytest.raises(ValidationError, match="does not match"):
            _event(entity_type="metric")

    def test_changes_and_summary_are_exclusive(self):
        _event(action="test.created", summary=ChangeSummary(count=2, ids=(uuid4(), uuid4())))
        with pytest.raises(ValidationError, match="not both"):
            _event(
                changes=(FieldChange(field="name", kind="value", after="x"),),
                summary=ChangeSummary(count=1),
            )

    @pytest.mark.parametrize("placeholder", ["testclient", "unknown", ""])
    def test_placeholder_ip_becomes_none(self, placeholder):
        assert _event(ip=placeholder).ip is None

    def test_real_ip_is_kept(self):
        assert str(_event(ip="203.0.113.7").ip) == "203.0.113.7"
        assert str(_event(ip="2001:db8::1").ip) == "2001:db8::1"


class TestFieldChange:
    def test_secret_never_carries_values(self):
        with pytest.raises(ValidationError, match="must not carry values"):
            FieldChange(field="api_key", kind="secret", after="sk-live")

    def test_json_values_are_allowed(self):
        change = FieldChange(field="config", kind="value", before={"a": 1}, after=[1, "x", None])
        assert change.before == {"a": 1}

    def test_is_frozen(self):
        change = FieldChange(field="name", kind="value")
        with pytest.raises(ValidationError):
            change.field = "other"

    def test_summary_count_is_positive(self):
        with pytest.raises(ValidationError):
            ChangeSummary(count=0)
