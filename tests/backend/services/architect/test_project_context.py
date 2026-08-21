"""Why the Architect has to be told which project it is in.

``_resolve_project_context`` exists because the agent cannot work the project
out for itself. These tests pin the two facts that make it necessary, so the
lookup does not get "simplified" away later on the assumption that
``list_projects`` self-filters.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from rhesis.backend.app import models
from rhesis.backend.app.services.architect.runner import _resolve_project_context


@pytest.mark.unit
class TestProjectIsNotProjectScoped:
    def test_project_table_has_no_project_id_column(self):
        """No ``project_id`` column means no scoping.

        ``scope_events.auto_filter`` only injects a project filter when the
        entity has a ``project_id`` column, and the ``project_isolation`` RLS
        policy is created per-table off the same column. So ``list_projects``
        returns every project in the organization, with nothing marking the
        one the session is scoped to.
        """
        columns = {c.name for c in models.Project.__table__.columns}
        assert "project_id" not in columns
        assert "organization_id" in columns, "projects are still org-scoped"


@pytest.mark.unit
class TestResolveProjectContext:
    def _db_returning(self, project):
        db = MagicMock()
        return db, project

    def test_returns_none_without_a_project_id(self):
        assert _resolve_project_context(MagicMock(), None, "org-1") is None
        assert _resolve_project_context(MagicMock(), "", "org-1") is None

    def test_returns_name_and_id(self, monkeypatch):
        project_id = uuid4()
        # ``name`` is reserved by Mock's constructor — set it after building.
        project = MagicMock(id=project_id, description="Booking bot")
        project.name = "Travel Agent"
        monkeypatch.setattr(
            "rhesis.backend.app.crud.project.get_project",
            lambda *a, **k: project,
        )
        ctx = _resolve_project_context(MagicMock(), str(project_id), "org-1")
        assert ctx == {
            "project_id": str(project_id),
            "name": "Travel Agent",
            "description": "Booking bot",
        }

    def test_missing_project_degrades_to_none(self, monkeypatch):
        """A deleted project must not break the turn — the block is just omitted."""
        monkeypatch.setattr(
            "rhesis.backend.app.crud.project.get_project",
            lambda *a, **k: None,
        )
        assert _resolve_project_context(MagicMock(), str(uuid4()), "org-1") is None

    def test_lookup_failure_degrades_to_none(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("db gone")

        monkeypatch.setattr("rhesis.backend.app.crud.project.get_project", boom)
        assert _resolve_project_context(MagicMock(), str(uuid4()), "org-1") is None

    def test_invalid_uuid_degrades_to_none(self):
        """A malformed session project_id must not raise mid-turn."""
        assert _resolve_project_context(MagicMock(), "not-a-uuid", "org-1") is None
