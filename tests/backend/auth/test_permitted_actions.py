"""Tests for the server-driven affordances resolver — ``permitted_actions_for``.

The resolver projects a caller's already-computed effective capability set onto a
single object, resolving ``:own`` against ``obj.user_id`` and emitting the **full
capability strings** the caller may exercise on the object (the same vocabulary as
``GET /me/permissions``). It is pure (no DB), so these tests pass capability lists
directly.

Key guarantees:

- Owner with ``:own`` caps gets the base caps; a non-owner does not.
- Unconditional (non-``:own``) caps grant the capability regardless of ownership.
- The ``:own`` qualifier is collapsed to the base capability for the owner.
- Collection-scoped ``create`` and the implied ``read`` are excluded.
- Capabilities for other resources are ignored.
- Missing/None ``user_id`` denies all ``:own`` caps but keeps unconditional ones.

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


def _obj(user_id=OWNER) -> object:
    return SimpleNamespace(user_id=user_id)


def test_owner_gets_own_caps_collapsed_to_base():
    caps = ["comment:read", "comment:update:own", "comment:delete:own", "comment:react"]
    assert permitted_actions_for(caps, _obj(), ResourceType.COMMENT, current_user_id=OWNER) == [
        "comment:delete",
        "comment:react",
        "comment:update",
    ]


def test_non_owner_denied_own_caps():
    caps = ["comment:update:own", "comment:delete:own", "comment:react"]
    # react is unconditional; update/delete are :own and the caller is not the owner.
    assert permitted_actions_for(caps, _obj(), ResourceType.COMMENT, current_user_id=OTHER) == [
        "comment:react",
    ]


def test_unconditional_caps_ignore_ownership():
    caps = ["comment:update", "comment:delete"]
    assert permitted_actions_for(caps, _obj(), ResourceType.COMMENT, current_user_id=OTHER) == [
        "comment:delete",
        "comment:update",
    ]


def test_create_and_read_excluded():
    caps = ["comment:create", "comment:read", "comment:update"]
    assert permitted_actions_for(caps, _obj(), ResourceType.COMMENT, current_user_id=OWNER) == [
        "comment:update",
    ]


def test_other_resources_ignored():
    caps = ["test:create", "test:update", "experiment:delete", "comment:update:own"]
    assert permitted_actions_for(caps, _obj(), ResourceType.COMMENT, current_user_id=OWNER) == [
        "comment:update",
    ]


def test_empty_caps():
    assert permitted_actions_for([], _obj(), ResourceType.COMMENT, current_user_id=OWNER) == []


def test_missing_user_id_denies_own_but_keeps_unconditional():
    caps = ["comment:update:own", "comment:react"]
    obj = SimpleNamespace()  # no user_id attribute
    assert permitted_actions_for(caps, obj, ResourceType.COMMENT, current_user_id=OWNER) == [
        "comment:react",
    ]


def test_none_owner_denies_own():
    caps = ["comment:update:own"]
    assert (
        permitted_actions_for(caps, _obj(user_id=None), ResourceType.COMMENT, current_user_id=None)
        == []
    )


def test_generic_across_resource_types():
    # The resolver is resource-agnostic: same logic for a future :own resource.
    caps = ["experiment:update:own", "experiment:delete"]
    assert permitted_actions_for(caps, _obj(), ResourceType.EXPERIMENT, current_user_id=OWNER) == [
        "experiment:delete",
        "experiment:update",
    ]
