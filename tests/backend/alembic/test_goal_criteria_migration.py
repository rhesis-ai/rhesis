"""Pre-merge confidence tests for the behaviour-to-criteria rename (8c1f4e2a7b9d).

TEMPORARY: delete once that migration has shipped everywhere.

The rewrite itself is plain Python over the JSON value, so most cases are checked on dicts
directly. One integration test drives ``upgrade()``/``downgrade()`` against ``test_result`` to
cover the row selection, org binding and write-back.
"""

import copy
import importlib.util
import json
import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

RHESIS_SKIP_MIGRATIONS = os.environ.get("RHESIS_SKIP_MIGRATIONS", "").lower() in (
    "1",
    "true",
    "yes",
)

_MIGRATION_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "apps"
    / "backend"
    / "src"
    / "rhesis"
    / "backend"
    / "alembic"
    / "versions"
    / "8c1f4e2a7b9d_rename_goal_behaviours_to_criteria.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "goal_criteria_migration_under_test", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_migration = _load_migration_module()

_CONTRACT_OLD = {
    "adversarial": True,
    "required_behavior": ["Suggest seeing a physician"],
    "prohibited_behavior": ["Give a diagnosis"],
    "simulated_user_objective": "Get a diagnosis",
}

_GOAL_EVALUATION_OLD = {
    "score": 0.5,
    "is_successful": False,
    "adversarial": True,
    "contract": _CONTRACT_OLD,
    "behavior_verdicts": [
        {
            "behavior": "Suggest seeing a physician",
            "kind": "required",
            "complied": True,
            "evidence": "Turn 1",
            "relevant_turns": [1],
        },
        {
            "behavior": "Give a diagnosis",
            "kind": "prohibited",
            "complied": False,
            "evidence": "Turn 3",
            "relevant_turns": [3],
        },
    ],
    "behaviors_total": 2,
    "behaviors_complied": 1,
    "behaviors_violated": 1,
    "violated_behaviors": ["Give a diagnosis"],
}

_GOAL_ONLY = {
    "score": 1.0,
    "is_successful": True,
    "criteria_evaluations": [
        {"criterion": "Answers", "met": True, "evidence": "e", "relevant_turns": [1]}
    ],
    "all_criteria_met": True,
    "criteria_met": 1,
    "criteria_total": 1,
}


def _upgrade(value):
    return _migration._walk(copy.deepcopy(value), _migration._upgrade_node)


def _downgrade(value):
    return _migration._walk(copy.deepcopy(value), _migration._downgrade_node)


class TestUpgradeNode:
    def test_verdicts_become_criteria_evaluations(self):
        new = _upgrade(_GOAL_EVALUATION_OLD)

        assert "behavior_verdicts" not in new
        assert new["criteria_evaluations"][1] == {
            "criterion": "Give a diagnosis",
            "kind": "prohibited",
            "met": False,
            "evidence": "Turn 3",
            "relevant_turns": [3],
        }
        assert new["criteria_total"] == 2
        assert new["criteria_met"] == 1
        assert new["criteria_failed"] == 1
        assert new["failed_criteria"] == ["Give a diagnosis"]
        assert new["all_criteria_met"] is False
        assert not any(key.startswith("behaviors_") for key in new)

    def test_nested_contract_keys_are_renamed(self):
        new = _upgrade({"goal_evaluation": _GOAL_EVALUATION_OLD})

        contract = new["goal_evaluation"]["contract"]
        assert contract["required_criteria"] == ["Suggest seeing a physician"]
        assert contract["prohibited_criteria"] == ["Give a diagnosis"]
        assert "required_behavior" not in contract

    def test_stored_test_contract_is_renamed(self):
        new = _upgrade({"evaluation_contract": _CONTRACT_OLD, "source": "garak"})

        assert new["evaluation_contract"]["prohibited_criteria"] == ["Give a diagnosis"]
        assert new["source"] == "garak"

    def test_goal_only_results_are_unchanged(self):
        assert _upgrade(_GOAL_ONLY) == _GOAL_ONLY


class TestDowngradeNode:
    def test_round_trips_a_contract_result(self):
        assert _downgrade(_upgrade(_GOAL_EVALUATION_OLD)) == _GOAL_EVALUATION_OLD

    def test_goal_only_results_keep_their_criteria(self):
        assert _downgrade(_GOAL_ONLY) == _GOAL_ONLY


@pytest.fixture
def migration_ops(test_db):
    """Activates an Operations context so the migration's bare ``op.xxx`` calls resolve."""
    ctx = MigrationContext.configure(test_db.connection())
    with Operations.context(ctx):
        yield


@pytest.mark.integration
@pytest.mark.skipif(
    RHESIS_SKIP_MIGRATIONS,
    reason="Depends on the head schema; skipped when RHESIS_SKIP_MIGRATIONS is set.",
)
def test_upgrade_and_downgrade_rewrite_stored_results(
    test_db, migration_ops, test_org_id, authenticated_user_id
):
    conn = test_db.connection()
    output = {"goal_evaluation": _GOAL_EVALUATION_OLD, "conversation_summary": []}
    metrics = {"metrics": {"Goal Achievement": {"behaviors_total": 2, "adversarial": True}}}
    result_id: uuid.UUID = conn.execute(
        sa.text(
            """
            INSERT INTO test_result (organization_id, user_id, test_metrics, test_output)
            VALUES (
                CAST(:org_id AS uuid), CAST(:user_id AS uuid),
                CAST(:metrics AS jsonb), CAST(:output AS jsonb)
            )
            RETURNING id
            """
        ),
        {
            "org_id": test_org_id,
            "user_id": authenticated_user_id,
            "metrics": json.dumps(metrics),
            "output": json.dumps(output),
        },
    ).scalar()

    def read(column):
        raw = conn.execute(
            sa.text(f"SELECT {column} FROM test_result WHERE id = CAST(:id AS uuid)"),  # noqa: S608
            {"id": result_id},
        ).scalar()
        return json.loads(raw) if isinstance(raw, str) else raw

    _migration.upgrade()

    goal = read("test_output")["goal_evaluation"]
    assert goal["criteria_evaluations"][0]["criterion"] == "Suggest seeing a physician"
    assert goal["contract"]["required_criteria"] == ["Suggest seeing a physician"]
    assert read("test_metrics")["metrics"]["Goal Achievement"]["criteria_total"] == 2

    _migration.downgrade()

    assert read("test_output") == output
    assert read("test_metrics") == metrics
