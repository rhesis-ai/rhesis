"""Tests for the server-driven affordances resolver — ``permitted_actions_for``.

The resolver projects a caller's already-computed effective capability set onto a
single object and emits the **full capability strings** the caller may exercise on
it (same vocabulary as ``GET /me/permissions``). Crucially the output must match
what the endpoint enforces:

- **Ownership-gated** actions (those with a ``:own`` variant in the catalog, passed
  as ``own_gated_actions``) mirror the route's ``authorize_object`` check: granted
  only when the caller owns the object AND holds the ``:own`` cap. The plain cap —
  held broadly by community members — does NOT grant them.
- **Ungated** actions (no ``:own`` variant, e.g. ``comment:react``) are granted by
  the plain cap.

Pure (no DB), so these tests pass capability lists + the own-gated set directly.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/auth/test_permitted_actions.py -v
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from rhesis.backend.app.auth.capabilities import ResourceType, permitted_actions_for

OWNER = uuid.uuid4()
OTHER = uuid.uuid4()

# For comments, update + delete have :own variants in the catalog; react does not.
COMMENT_GATED = frozenset({"update", "delete"})


def _obj(user_id=OWNER) -> object:
    return SimpleNamespace(user_id=user_id)


def _comment_actions(caps, current_user_id, obj=None):
    return permitted_actions_for(
        caps,
        obj if obj is not None else _obj(),
        ResourceType.COMMENT,
        current_user_id=current_user_id,
        own_gated_actions=COMMENT_GATED,
    )


def test_owner_with_own_caps_gets_base_caps():
    caps = ["comment:read", "comment:update:own", "comment:delete:own", "comment:react"]
    assert _comment_actions(caps, OWNER) == [
        "comment:delete",
        "comment:react",
        "comment:update",
    ]


def test_non_owner_denied_owner_gated_actions():
    caps = ["comment:update:own", "comment:delete:own", "comment:react"]
    # react is ungated (granted); update/delete are :own and caller is not owner.
    assert _comment_actions(caps, OTHER) == ["comment:react"]


def test_global_cap_does_not_grant_owner_gated_action():
    # Regression (PR #2032 review): a caller holding the plain comment:update/
    # delete who is NOT the owner must NOT be advertised edit/delete — the endpoint
    # enforces ownership via authorize_object. In community every member holds the
    # plain cap, so this is the dangerous case.
    caps = ["comment:update", "comment:delete"]
    assert _comment_actions(caps, OTHER) == []


def test_owner_gated_action_requires_the_own_cap_not_just_ownership():
    # Owner but only holds the plain cap (not the :own cap) → still denied, matching
    # authorize_object which requires the :own capability.
    caps = ["comment:update", "comment:delete"]
    assert _comment_actions(caps, OWNER) == []


def test_ungated_action_granted_by_plain_cap():
    assert _comment_actions(["comment:react"], OTHER) == ["comment:react"]


def test_create_and_read_excluded():
    caps = ["comment:create", "comment:read", "comment:update:own"]
    assert _comment_actions(caps, OWNER) == ["comment:update"]


def test_other_resources_ignored():
    caps = ["test:create", "test:update", "experiment:delete", "comment:update:own"]
    assert _comment_actions(caps, OWNER) == ["comment:update"]


def test_empty_caps():
    assert _comment_actions([], OWNER) == []


def test_missing_user_id_denies_owner_gated_but_keeps_ungated():
    caps = ["comment:update:own", "comment:react"]
    obj = SimpleNamespace()  # no user_id attribute → not owner
    assert _comment_actions(caps, OWNER, obj=obj) == ["comment:react"]


def test_none_owner_denies_owner_gated():
    caps = ["comment:update:own"]
    assert _comment_actions(caps, None, obj=_obj(user_id=None)) == []


def test_mixed_gating_across_resource():
    # Generic: experiment.update is owner-gated (has :own), experiment.delete is not.
    caps = ["experiment:update:own", "experiment:delete"]
    result = permitted_actions_for(
        caps,
        _obj(),
        ResourceType.EXPERIMENT,
        current_user_id=OWNER,
        own_gated_actions=frozenset({"update"}),
    )
    assert result == ["experiment:delete", "experiment:update"]
