"""
Unit tests for project_id threading through email deep links (issue #2133).

These tests verify that:
1. ``build_summary_data`` carries ``project_id`` into the template context.
2. ``get_test_run_project_id`` converts the TestRun's project_id to a string
   (or None) so Jinja2's truthiness guard works correctly.
3. The TestSet task result builder (``_build_task_result``) threads the test
   set's ``project_id`` so the TASK_COMPLETION email deep link can switch
   projects.

The tests are intentionally DB-free — they exercise pure data-transformation
functions with a MagicMock TestRun/TestSet, so they run in milliseconds and
don't require the testcontainers stack.
"""

# Side-effect import: installs a sys.meta_path finder that stubs out the
# SDK's heavy optional deps (ragas, deepeval, litellm, langchain, ...) so
# the ``rhesis.backend.tasks`` package's eager imports complete without
# pulling in torch/langchain just to run a unit test. See
# _heavy_import_stubs.py for the rationale and the stubbed module list.
#
# MUST run before any ``from rhesis.backend...`` import. We do it via
# ``importlib.import_module`` (rather than a top-level ``import``) so ruff's
# isort doesn't reorder it after the rhesis imports — isort doesn't treat
# runtime ``importlib.import_module`` calls as module-level imports.
import importlib as _importlib

_importlib.import_module("tests.backend.tasks._heavy_import_stubs")

import uuid  # noqa: E402
from datetime import datetime  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402

from rhesis.backend.tasks import test_set as test_set_module  # noqa: E402
from rhesis.backend.tasks.execution.result_processor import (  # noqa: E402
    build_summary_data,
    get_test_run_project_id,
)


def _make_summary_kwargs(**overrides):
    """Build the minimum kwargs build_summary_data accepts, with overrides."""
    base = {
        "test_run_id": "tr-1",
        "email_status": "success",
        "execution_status": "Complete",
        "total_tests": 10,
        "tests_passed": 8,
        "tests_failed": 2,
        "execution_errors": 0,
        "execution_time": "1m 30s",
        "test_set_name": "Smoke",
        "endpoint_name": "Prod",
        "endpoint_url": "https://example.com",
        "project_name": "Demo",
        "completion_time": datetime(2026, 1, 1, 12, 0, 0),
    }
    base.update(overrides)
    return base


@pytest.mark.unit
class TestBuildSummaryDataProjectId:
    """build_summary_data must thread project_id into the returned dict."""

    def test_returns_project_id_when_provided(self):
        project_id = str(uuid.uuid4())
        result = build_summary_data(**_make_summary_kwargs(project_id=project_id))
        assert result["project_id"] == project_id

    def test_defaults_project_id_to_none_when_omitted(self):
        # When the caller doesn't pass project_id at all (e.g. legacy code
        # paths that haven't been updated), it must default to None — NOT
        # be missing from the dict — so the Jinja2 template's
        # `{% if project_id %}` guard evaluates to False rather than
        # raising UndefinedError.
        result = build_summary_data(**_make_summary_kwargs())
        assert result["project_id"] is None

    def test_defaults_project_id_to_none_when_explicitly_none(self):
        # Test runs without a project should pass None explicitly via
        # get_test_run_project_id(); the function must preserve None
        # rather than coercing to a string.
        result = build_summary_data(**_make_summary_kwargs(project_id=None))
        assert result["project_id"] is None

    def test_preserves_all_other_keys(self):
        # Regression guard: adding project_id must not displace any
        # existing key — downstream consumers (email subject line, status
        # details) still need to read them.
        project_id = str(uuid.uuid4())
        result = build_summary_data(**_make_summary_kwargs(project_id=project_id))
        for key in (
            "test_run_id",
            "status",
            "execution_status",
            "total_tests",
            "tests_passed",
            "tests_failed",
            "execution_errors",
            "execution_time",
            "status_details",
            "test_set_name",
            "endpoint_name",
            "endpoint_url",
            "project_name",
            "completed_at",
        ):
            assert key in result, f"project_id addition dropped {key}"


@pytest.mark.unit
class TestGetTestRunProjectId:
    """get_test_run_project_id converts the model's UUID to a string for Jinja2."""

    def test_returns_string_when_project_id_set(self):
        project_id = uuid.uuid4()
        test_run = MagicMock()
        test_run.project_id = project_id
        assert get_test_run_project_id(test_run) == str(project_id)

    def test_returns_none_when_project_id_is_none(self):
        # Test runs without a project (e.g. organization-scoped legacy
        # runs) must yield None, NOT the string "None" — the template's
        # `{% if project_id %}` guard is falsy for None but truthy for
        # "None", which would produce ?project_id=None in the deep link.
        test_run = MagicMock()
        test_run.project_id = None
        assert get_test_run_project_id(test_run) is None

    def test_returns_none_when_project_id_attr_missing(self):
        # Defensive: if a fixture/object forgets to set project_id, we
        # should degrade to None rather than AttributeError. MagicMock
        # auto-creates attributes on access, so use a bare object to
        # exercise the getattr default.
        class _BareObject:
            pass

        assert get_test_run_project_id(_BareObject()) is None


@pytest.mark.unit
class TestBuildTaskResultProjectId:
    """_build_task_result threads the test set's project_id for TASK_COMPLETION."""

    def _make_test_set(self, project_id=None):
        ts = MagicMock()
        ts.id = uuid.uuid4()
        ts.name = "Smoke"
        ts.description = "desc"
        ts.short_description = "short"
        ts.tests = []
        ts.attributes = None
        ts.project_id = project_id
        return ts

    def test_returns_project_id_when_test_set_has_project(self):
        project_id = uuid.uuid4()
        ts = self._make_test_set(project_id=project_id)
        result = test_set_module._build_task_result(
            self=MagicMock(),  # Celery task instance (bound self)
            db_test_set=ts,
            num_tests=5,
            synthesizer=MagicMock(__class__=MagicMock(__name__="FakeSynth")),
            log_kwargs={},
            batch_size=10,
            org_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
        )
        assert result["project_id"] == str(project_id)

    def test_returns_none_when_test_set_has_no_project(self):
        ts = self._make_test_set(project_id=None)
        result = test_set_module._build_task_result(
            self=MagicMock(),  # Celery task instance (bound self)
            db_test_set=ts,
            num_tests=5,
            synthesizer=MagicMock(__class__=MagicMock(__name__="FakeSynth")),
            log_kwargs={},
            batch_size=10,
            org_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
        )
        assert result["project_id"] is None
