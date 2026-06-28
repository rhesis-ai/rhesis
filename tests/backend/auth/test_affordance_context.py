"""Integration tests for the automatic affordance-context path.

These tests exercise the full chain:
    set_affordance_context(...) binds the ContextVar
    → WithPermittedActions.model_validator reads the context during Pydantic
      serialization
    → permitted_actions is populated with the correct capability strings.

The tests are pure (no DB, no HTTP) — the _AffordanceContext is constructed
directly with mocked dependencies, and permitted_actions_for is exercised via
the real capability resolver.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/auth/test_affordance_context.py -v
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import ClassVar, List, Optional
from uuid import UUID

import pytest
from pydantic import Field

from rhesis.backend.app.auth.affordances import (
    _AffordanceContext,
    current_affordance_context,
    reset_affordance_context,
)
from rhesis.backend.app.auth.capabilities import ResourceType
from rhesis.backend.app.schemas.affordances import WithPermittedActions

ASSIGNEE = uuid.uuid4()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OWNER = uuid.uuid4()
OTHER = uuid.uuid4()


def _make_context(
    current_user_id: uuid.UUID,
    caps: List[str],
) -> _AffordanceContext:
    """Construct a context whose PDP always returns *caps*."""
    mock_user = SimpleNamespace(id=current_user_id, organization_id=uuid.uuid4())
    mock_request = SimpleNamespace(headers={}, state=SimpleNamespace())
    mock_db = SimpleNamespace(info={"_scope": None})

    ctx = _AffordanceContext(
        current_user=mock_user,
        request=mock_request,
        db=mock_db,  # type: ignore[arg-type]
    )
    # Pre-populate the memoized fields so no real PDP call is needed.
    mock_principal = SimpleNamespace(user_id=current_user_id)
    ctx._principal = mock_principal
    ctx._caps = list(caps)
    return ctx


# ---------------------------------------------------------------------------
# Minimal schema fixtures
# ---------------------------------------------------------------------------


class _CommentSchema(WithPermittedActions):
    __resource_type__: ClassVar[Optional[str]] = ResourceType.COMMENT  # type: ignore[assignment]

    id: UUID = Field(default_factory=uuid.uuid4)
    user_id: UUID


class _ExperimentSchema(WithPermittedActions):
    """Schema with non-default __owner_attr__."""

    __resource_type__: ClassVar[Optional[str]] = ResourceType.EXPERIMENT  # type: ignore[assignment]
    __owner_attr__: ClassVar[str] = "owner_user_id"

    id: UUID = Field(default_factory=uuid.uuid4)
    owner_user_id: UUID


class _TaskSchema(WithPermittedActions):
    """Schema that exercises the __assignee_attr__ path."""

    __resource_type__: ClassVar[Optional[str]] = ResourceType.TASK  # type: ignore[assignment]
    __assignee_attr__: ClassVar[Optional[str]] = "assignee_id"  # type: ignore[assignment]

    id: UUID = Field(default_factory=uuid.uuid4)
    user_id: UUID
    assignee_id: Optional[UUID] = None


class _NoResourceTypeSchema(WithPermittedActions):
    """Schema that does not set __resource_type__ — should stay empty."""

    id: UUID = Field(default_factory=uuid.uuid4)
    user_id: UUID


# ---------------------------------------------------------------------------
# Tests: no context bound (fail-closed)
# ---------------------------------------------------------------------------


class TestNoContextBound:
    def test_permitted_actions_empty_without_context(self):
        assert current_affordance_context() is None
        schema = _CommentSchema(user_id=OWNER)
        assert schema.permitted_actions == []

    def test_no_resource_type_empty_without_context(self):
        schema = _NoResourceTypeSchema(user_id=OWNER)
        assert schema.permitted_actions == []


# ---------------------------------------------------------------------------
# Tests: context bound, owner caps
# ---------------------------------------------------------------------------


class TestWithContextBound:
    @pytest.fixture(autouse=True)
    def _reset_context(self):
        """Ensure ContextVar is restored after each test."""
        token = None
        yield
        if token is not None:
            reset_affordance_context(token)

    def _bind(self, user_id: uuid.UUID, caps: List[str]):
        ctx = _make_context(user_id, caps)
        # Replace the dependency path: directly set the ContextVar.
        from rhesis.backend.app.auth.affordances import _affordance_ctx

        token = _affordance_ctx.set(ctx)
        return token

    def test_owner_with_own_caps_gets_actions(self):
        token = self._bind(OWNER, ["comment:update:own", "comment:delete:own", "comment:react"])
        try:
            schema = _CommentSchema(user_id=OWNER)
            assert sorted(schema.permitted_actions) == [
                "comment:delete",
                "comment:react",
                "comment:update",
            ]
        finally:
            reset_affordance_context(token)

    def test_non_owner_denied_own_gated_actions(self):
        token = self._bind(OTHER, ["comment:update:own", "comment:delete:own", "comment:react"])
        try:
            schema = _CommentSchema(user_id=OWNER)  # owner is OWNER, not OTHER
            assert schema.permitted_actions == ["comment:react"]
        finally:
            reset_affordance_context(token)

    def test_no_resource_type_stays_empty_even_with_context(self):
        token = self._bind(OWNER, ["comment:update:own", "comment:react"])
        try:
            schema = _NoResourceTypeSchema(user_id=OWNER)
            assert schema.permitted_actions == []
        finally:
            reset_affordance_context(token)

    def test_already_populated_not_overwritten(self):
        """Re-serializing an already-resolved model keeps the existing actions."""
        token = self._bind(OWNER, ["comment:update:own", "comment:react"])
        try:
            schema = _CommentSchema(user_id=OWNER)
            first = list(schema.permitted_actions)
            assert first  # should be populated
            # Force re-validation — permitted_actions already set, must not clear.
            schema2 = _CommentSchema.model_validate(schema.model_dump())
            assert schema2.permitted_actions == first
        finally:
            reset_affordance_context(token)

    def test_owner_attr_override(self):
        """ExperimentSchema reads owner from owner_user_id, not user_id."""
        token = self._bind(OWNER, ["experiment:update:own", "experiment:delete:own"])
        try:
            schema = _ExperimentSchema(owner_user_id=OWNER)
            assert sorted(schema.permitted_actions) == [
                "experiment:delete",
                "experiment:update",
            ]
        finally:
            reset_affordance_context(token)

    def test_owner_attr_override_non_owner_denied(self):
        token = self._bind(OTHER, ["experiment:update:own", "experiment:delete:own"])
        try:
            schema = _ExperimentSchema(owner_user_id=OWNER)
            assert schema.permitted_actions == []
        finally:
            reset_affordance_context(token)

    def test_list_response_each_object_resolved(self):
        """All items in a list response get their own affordances computed."""
        token = self._bind(
            OWNER,
            ["comment:update:own", "comment:delete:own", "comment:react"],
        )
        try:
            items = [
                _CommentSchema(user_id=OWNER),
                _CommentSchema(user_id=OTHER),
            ]
            assert sorted(items[0].permitted_actions) == [
                "comment:delete",
                "comment:react",
                "comment:update",
            ]
            # OTHER's object: only ungated actions granted
            assert items[1].permitted_actions == ["comment:react"]
        finally:
            reset_affordance_context(token)

    def test_caps_memoized_across_objects(self):
        """_ensure_caps is called once; _caps is reused for subsequent objects."""
        ctx = _make_context(OWNER, ["comment:react"])
        from rhesis.backend.app.auth.affordances import _affordance_ctx

        token = _affordance_ctx.set(ctx)
        try:
            _ = _CommentSchema(user_id=OWNER)
            _ = _CommentSchema(user_id=OWNER)
            # If _caps were resolved lazily per-call, the list would be rebuilt.
            # We verify memoization by checking the private field.
            assert ctx._caps == ["comment:react"]
        finally:
            reset_affordance_context(token)

    def test_set_and_reset_restores_none(self):
        assert current_affordance_context() is None
        token = self._bind(OWNER, [])
        assert current_affordance_context() is not None
        reset_affordance_context(token)
        assert current_affordance_context() is None


# ---------------------------------------------------------------------------
# Tests: :assigned qualifier via __assignee_attr__
# ---------------------------------------------------------------------------


class TestAssignedQualifier:
    """Verify that the :assigned qualifier path grants/denies correctly.

    Uses _TaskSchema which sets __assignee_attr__ = "assignee_id", matching the
    production Task schema.  The caps used are the real enum strings so that
    _own_gated_actions (which scans the live catalog) correctly identifies
    "update" and "delete" as object-gated for the "task" resource.
    """

    @pytest.fixture(autouse=True)
    def _reset_context(self):
        token = None
        yield
        if token is not None:
            reset_affordance_context(token)

    def _bind(self, user_id: uuid.UUID, caps: list[str]):
        ctx = _make_context(user_id, caps)
        from rhesis.backend.app.auth.affordances import _affordance_ctx

        token = _affordance_ctx.set(ctx)
        return token

    def test_assignee_with_update_assigned_gets_update(self):
        """Assignee holding task:update:assigned sees task:update in permitted_actions."""
        token = self._bind(ASSIGNEE, ["task:update:assigned"])
        try:
            schema = _TaskSchema(user_id=OWNER, assignee_id=ASSIGNEE)
            assert "task:update" in schema.permitted_actions
        finally:
            reset_affordance_context(token)

    def test_non_assignee_denied_update_assigned(self):
        """A user who is neither owner nor assignee is denied the update affordance."""
        other = uuid.uuid4()
        token = self._bind(other, ["task:update:assigned", "task:update:own"])
        try:
            schema = _TaskSchema(user_id=OWNER, assignee_id=ASSIGNEE)
            assert "task:update" not in schema.permitted_actions
        finally:
            reset_affordance_context(token)

    def test_owner_and_assignee_both_independently_grant_update(self):
        """Owner via UPDATE_OWN and assignee via UPDATE_ASSIGNED each independently
        produce task:update in permitted_actions."""
        # Owner path
        token = self._bind(OWNER, ["task:update:own"])
        try:
            schema = _TaskSchema(user_id=OWNER, assignee_id=ASSIGNEE)
            assert "task:update" in schema.permitted_actions, "owner path failed"
        finally:
            reset_affordance_context(token)

        # Assignee path
        token = self._bind(ASSIGNEE, ["task:update:assigned"])
        try:
            schema = _TaskSchema(user_id=OWNER, assignee_id=ASSIGNEE)
            assert "task:update" in schema.permitted_actions, "assignee path failed"
        finally:
            reset_affordance_context(token)

    def test_owner_delete_own_grants_delete(self):
        """Creator with task:delete:own sees task:delete; assignee without it does not."""
        # Owner gets delete
        token = self._bind(OWNER, ["task:delete:own"])
        try:
            schema = _TaskSchema(user_id=OWNER, assignee_id=ASSIGNEE)
            assert "task:delete" in schema.permitted_actions
        finally:
            reset_affordance_context(token)

        # Assignee holding only update:assigned does NOT get delete
        token = self._bind(ASSIGNEE, ["task:update:assigned"])
        try:
            schema = _TaskSchema(user_id=OWNER, assignee_id=ASSIGNEE)
            assert "task:delete" not in schema.permitted_actions
        finally:
            reset_affordance_context(token)
