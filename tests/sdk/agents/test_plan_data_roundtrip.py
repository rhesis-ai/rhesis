"""Guards `architect_session.plan_data`'s round trip through `ArchitectPlan`.

The backend stores saved Architect plans as opaque JSONB, keyed by these Pydantic
field names. Renaming the fields without a data backfill fails silently: Pydantic
ignores unknown keys, so a stored payload validates successfully into an EMPTY
plan rather than raising -- and `restore_state`'s blanket `except Exception` means
even a hard failure never surfaces either. `_STORED_PLAN_DATA` below is written by
hand, not generated via `model_dump()`, so it does not rename itself alongside
`plan.py` and keeps guarding the rename after the fact.
"""

import pytest

from rhesis.sdk.agents.architect.plan import ArchitectPlan
from rhesis.sdk.agents.architect.state import ArchitectAgentStateSnapshot
from tests.sdk.agents.test_architect import _make_agent, _mock_model

# Hand-written stored shape -- mirrors ArchitectPlan.model_dump() field-for-field
# so the round-trip assertions can compare directly against it. `completed: True`
# and a non-empty `linked_metrics` exercise the internal progress-tracking fields
# a silent empty-parse would wipe.
_STORED_PLAN_DATA = {
    "project": None,
    "behaviors": [
        {
            "name": "Refuses Harmful Requests",
            "description": "Model declines requests for harmful content",
            "reuse_status": "new",
            "existing_id": None,
            "completed": True,
        }
    ],
    "test_sets": [
        {
            "name": "Guardrails",
            "description": "Safety guardrail tests",
            "short_description": "",
            "num_tests": 15,
            "test_type": "Single-Turn",
            "generation_prompt": "",
            "behaviors": ["Refuses Harmful Requests"],
            "categories": [],
            "topics": [],
            "completed": False,
        }
    ],
    "metrics": [
        {
            "name": "Safety Compliance",
            "description": "Scores refusal quality against the safety rubric",
            "reuse_status": "new",
            "existing_id": None,
            "evaluation_prompt": "",
            "evaluation_steps": "",
            "reasoning": "",
            "explanation": "",
            "threshold": 1.0,
            "threshold_operator": ">=",
            "metric_scope": ["Single-Turn"],
            "completed": False,
        }
    ],
    "behavior_metric_mappings": [
        {
            "behavior": "Refuses Harmful Requests",
            "metrics": ["Safety Compliance"],
            "linked_metrics": ["Safety Compliance"],
            "completed": True,
        }
    ],
}

# What a stored plan_data payload looks like once the rename has happened on the
# model but NOT on the data -- unknown top-level keys, everything else silently
# dropped to defaults.
_MISMATCHED_PAYLOAD = {
    "requirements": [{"name": "Refuses Harmful Requests"}],
    "requirement_metric_mappings": [
        {"requirement": "Refuses Harmful Requests", "metrics": []}
    ],
}


@pytest.mark.unit
class TestStoredPlanDataParsesFully:
    def test_frozen_payload_parses_into_populated_plan(self):
        plan = ArchitectPlan.model_validate(_STORED_PLAN_DATA)

        assert plan.behaviors[0].name == "Refuses Harmful Requests"
        assert plan.test_sets[0].behaviors == ["Refuses Harmful Requests"]
        assert plan.metrics[0].name == "Safety Compliance"
        assert plan.behavior_metric_mappings[0].behavior == "Refuses Harmful Requests"

    def test_completed_and_linked_metrics_survive(self):
        plan = ArchitectPlan.model_validate(_STORED_PLAN_DATA)

        assert plan.behaviors[0].completed is True
        mapping = plan.behavior_metric_mappings[0]
        assert mapping.completed is True
        assert mapping.linked_metrics == ["Safety Compliance"]

    def test_legacy_dict_shaped_mappings_still_coerce(self):
        """`_coerce_mappings` accepts the pre-list dict shape `model_dump` never
        re-emits -- an older stored plan can still have this shape."""
        legacy_payload = {
            **_STORED_PLAN_DATA,
            "behavior_metric_mappings": {"Refuses Harmful Requests": ["Safety Compliance"]},
        }

        plan = ArchitectPlan.model_validate(legacy_payload)

        assert len(plan.behavior_metric_mappings) == 1
        assert plan.behavior_metric_mappings[0].behavior == "Refuses Harmful Requests"
        assert plan.behavior_metric_mappings[0].metrics == ["Safety Compliance"]


@pytest.mark.unit
class TestAgentStateRoundTrip:
    def test_restore_state_sets_agent_plan(self):
        agent = _make_agent(_mock_model())
        snapshot = ArchitectAgentStateSnapshot(mode="planning", plan_data=_STORED_PLAN_DATA)

        agent.restore_state(snapshot)

        assert agent.plan is not None
        assert agent.plan.behaviors[0].name == "Refuses Harmful Requests"

    def test_dump_state_after_restore_is_stable(self):
        agent = _make_agent(_mock_model())
        agent.restore_state(
            ArchitectAgentStateSnapshot(mode="planning", plan_data=_STORED_PLAN_DATA)
        )

        dumped = agent.dump_state()

        assert dumped.plan_data == _STORED_PLAN_DATA


@pytest.mark.unit
class TestMismatchedKeysFailSilentlyNotLoudly:
    """Pydantic ignores unknown top-level keys rather than raising, so a stored
    plan shaped like the payload below -- one that predates any rename, or one
    read by a model that has since been renamed -- parses into a plan with the
    matching fields silently emptied, not a validation error. (A plan far enough
    along to have `test_sets` depending on the now-empty mappings *would* raise,
    caught by `_validate_metric_scope_coverage`; either way `restore_state`'s
    blanket `except Exception` swallows it, so the caller never finds out.) This
    is why the `plan_data` backfill is mandatory, not an optional cleanup step."""

    def test_unrecognized_keys_yield_an_empty_plan_without_raising(self):
        plan = ArchitectPlan.model_validate(_MISMATCHED_PAYLOAD)

        assert plan.behaviors == []
        assert plan.behavior_metric_mappings == []

    def test_restore_state_does_not_raise_on_mismatched_payload(self):
        agent = _make_agent(_mock_model())
        snapshot = ArchitectAgentStateSnapshot(mode="planning", plan_data=_MISMATCHED_PAYLOAD)

        agent.restore_state(snapshot)  # must not raise

        assert agent.plan is not None
        assert agent.plan.behaviors == []

    def test_dump_after_mismatched_restore_persists_an_empty_plan(self):
        """The destructive follow-on: once the empty plan is in memory, the next
        `dump_state` writes it straight back over the row, overwriting whatever
        the pre-rename plan actually contained."""
        agent = _make_agent(_mock_model())
        agent.restore_state(
            ArchitectAgentStateSnapshot(mode="planning", plan_data=_MISMATCHED_PAYLOAD)
        )

        dumped = agent.dump_state()

        assert dumped.plan_data is not None
        assert dumped.plan_data["behaviors"] == []
