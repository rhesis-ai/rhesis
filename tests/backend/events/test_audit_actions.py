"""Audit action names: the verb map against the live capability catalog."""

import re

import pytest

from rhesis.backend.events.audit_actions import (
    AUDIT_ONLY_ACTIONS,
    NOT_ACTIONS,
    PAST_TENSE,
    audit_action,
    capability_verb,
    known_actions,
)
from rhesis.backend.events.types import AUDIT_ACTION_PATTERN


@pytest.fixture
def catalog() -> list[str]:
    from rhesis.backend.app.auth.capabilities import get_all_capabilities, register_capabilities
    from rhesis.backend.app.main import app

    register_capabilities(app)
    capabilities = get_all_capabilities()
    assert capabilities, "capability catalog is empty"
    return capabilities


class TestDriftAgainstCatalog:
    def test_every_catalog_verb_has_a_past_form(self, catalog):
        verbs = {capability_verb(c) for c in catalog} - NOT_ACTIONS
        missing = sorted(verbs - PAST_TENSE.keys())
        assert not missing, (
            f"Capability verbs with no audit name: {missing}. "
            "Add the past tense to PAST_TENSE in events/audit_actions.py."
        )

    def test_every_past_form_is_used_by_the_catalog(self, catalog):
        """The map follows the catalog; it is not a second list to grow."""
        verbs = {capability_verb(c) for c in catalog}
        assert not sorted(PAST_TENSE.keys() - verbs)

    def test_every_known_action_is_well_formed(self, catalog):
        for action in known_actions(catalog):
            assert re.match(AUDIT_ACTION_PATTERN, action), action

    def test_audit_only_actions_do_not_shadow_derived_ones(self, catalog):
        derived = known_actions(catalog) - AUDIT_ONLY_ACTIONS
        assert not AUDIT_ONLY_ACTIONS & derived

    def test_audit_log_capabilities_name_their_own_reads(self, catalog):
        actions = known_actions(catalog)
        assert {"audit_log.viewed", "audit_log.exported", "audit_log.purged"} <= actions


class TestAuditAction:
    @pytest.mark.parametrize(
        ("capability", "action"),
        [
            ("endpoint:update", "endpoint.updated"),
            ("test_set:delete", "test_set.deleted"),
            ("test_set:export", "test_set.exported"),
            ("test_run:execute", "test_run.executed"),
            ("job:cancel", "job.cancelled"),
            ("comment:update:own", "comment.updated"),
            ("task:update:assigned", "task.updated"),
            ("audit_log:read", "audit_log.viewed"),
        ],
    )
    def test_derives_past_tense(self, capability, action):
        assert audit_action(capability) == action

    def test_manage_is_not_an_action(self):
        with pytest.raises(ValueError, match="bundle"):
            audit_action("member:manage")

    def test_unknown_verb_fails_loudly(self):
        with pytest.raises(ValueError, match="PAST_TENSE"):
            audit_action("endpoint:frobnicate")

    @pytest.mark.parametrize("bad", ["endpoint", "endpoint:", ":read", "a:b:c:d"])
    def test_rejects_malformed_capabilities(self, bad):
        with pytest.raises(ValueError):
            audit_action(bad)

    def test_known_actions_expands_bundles_to_row_changes(self):
        assert known_actions(["member:manage", "member:read"]) == (
            {"member.viewed", "member.created", "member.updated", "member.deleted"}
            | AUDIT_ONLY_ACTIONS
        )
