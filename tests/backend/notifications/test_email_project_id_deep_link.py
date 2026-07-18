"""
Unit tests for project_id deep-link rendering in email templates (issue #2133).

These tests verify that the three project-scoped email templates
(TEST_EXECUTION_SUMMARY, TASK_COMPLETION, TASK_ASSIGNMENT) emit
``?project_id=<uuid>`` in their deep links when a project_id is supplied,
and omit the query param entirely when project_id is None/undefined.

The tests render the actual Jinja2 templates via TemplateService, so they
catch regressions in both the template markup and the
``_prepare_context`` plumbing (project_id must NOT be in the required
variables set, otherwise missing values become 'N/A' (truthy) and the
guard fails — see template_service.py).
"""

import uuid
from datetime import datetime, timezone

import pytest

from rhesis.backend.notifications.email.template_service import (
    EmailTemplate,
    TemplateService,
)

# All templates deep-link to ``{frontend_url}`` and require a non-empty
# value — passing a placeholder keeps the assertion focused on the
# project_id query param rather than the URL itself.
_FRONTEND_URL = "https://app.example.test"


def _base_summary_vars(**overrides):
    """Minimum variables for TEST_EXECUTION_SUMMARY to render without N/A noise."""
    base = {
        "recipient_name": "Tester",
        "task_name": "Run #1",
        "task_id": "task-1",
        "status": "success",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total_tests": 10,
        "tests_passed": 8,
        "tests_failed": 2,
        "execution_time": "1m",
        "test_run_id": "tr-1",
        "status_details": "8 passed, 2 failed",
        "test_set_name": "Smoke",
        "endpoint_name": "Prod",
        "endpoint_url": "https://endpoint.example.test",
        "project_name": "Demo",
        "frontend_url": _FRONTEND_URL,
    }
    base.update(overrides)
    return base


def _base_completion_vars(**overrides):
    """Minimum variables for TASK_COMPLETION (test_run_id path) to render."""
    base = {
        "recipient_name": "Tester",
        "task_name": "Run #1",
        "task_id": "task-1",
        "status": "success",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "execution_time": "1m",
        "error_message": "",
        "frontend_url": _FRONTEND_URL,
        "test_run_id": "tr-1",
    }
    base.update(overrides)
    return base


def _base_assignment_vars(**overrides):
    """Minimum variables for TASK_ASSIGNMENT to render."""
    base = {
        "assignee_name": "Alice",
        "assigner_name": "Bob",
        "task_title": "Review",
        "task_description": "Please review",
        "task_id": "task-1",
        "status_name": "In Progress",
        "priority_name": "High",
        "entity_type": "test_run",
        "entity_id": "tr-1",
        "entity_name": "Run #1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_metadata": {},
        "frontend_url": _FRONTEND_URL,
    }
    base.update(overrides)
    return base


@pytest.fixture(scope="module")
def template_service():
    """Module-scoped fixture — TemplateService loads templates from disk once."""
    return TemplateService()


@pytest.mark.unit
class TestTestExecutionSummaryDeepLink:
    """TEST_EXECUTION_SUMMARY deep link includes ?project_id when set."""

    def test_includes_project_id_when_set(self, template_service):
        project_id = str(uuid.uuid4())
        html = template_service.render_template(
            EmailTemplate.TEST_EXECUTION_SUMMARY,
            _base_summary_vars(project_id=project_id),
        )
        # Must include the query param with the exact project_id value.
        assert f"?project_id={project_id}" in html
        # And must NOT include the bare deep link (no query param) — the
        # {% if project_id %} branch must win over the {% else %} branch.
        assert 'href="https://app.example.test/test-runs/tr-1"' not in html

    def test_omits_project_id_when_none(self, template_service):
        # project_id explicitly None (test run without a project) → the
        # {% else %} branch must render the bare deep link with no query param.
        html = template_service.render_template(
            EmailTemplate.TEST_EXECUTION_SUMMARY,
            _base_summary_vars(project_id=None),
        )
        assert "?project_id=" not in html
        assert 'href="https://app.example.test/test-runs/tr-1"' in html

    def test_omits_project_id_when_omitted(self, template_service):
        # Backward compat: when project_id is not in the variables dict at
        # all (legacy caller), _prepare_context leaves it Undefined → the
        # {% else %} branch must render the bare deep link.
        html = template_service.render_template(
            EmailTemplate.TEST_EXECUTION_SUMMARY,
            _base_summary_vars(),  # no project_id key
        )
        assert "?project_id=" not in html
        assert 'href="https://app.example.test/test-runs/tr-1"' in html


@pytest.mark.unit
class TestTaskCompletionDeepLink:
    """TASK_COMPLETION deep link switches between test_run_id and test_set_id."""

    def test_test_run_path_includes_project_id(self, template_service):
        project_id = str(uuid.uuid4())
        html = template_service.render_template(
            EmailTemplate.TASK_COMPLETION,
            _base_completion_vars(project_id=project_id),
        )
        assert f"/test-runs/tr-1?project_id={project_id}" in html

    def test_test_run_path_omits_project_id_when_none(self, template_service):
        html = template_service.render_template(
            EmailTemplate.TASK_COMPLETION,
            _base_completion_vars(project_id=None),
        )
        assert "?project_id=" not in html
        assert 'href="https://app.example.test/test-runs/tr-1"' in html

    def test_test_set_path_includes_project_id(self, template_service):
        # When test_run_id is absent/None but test_set_id is present, the
        # deep link points at /test-sets/<id> — project_id must thread
        # through that branch too.
        project_id = str(uuid.uuid4())
        vars_ = _base_completion_vars(
            project_id=project_id,
            test_run_id=None,
            test_set_id="ts-1",
        )
        html = template_service.render_template(EmailTemplate.TASK_COMPLETION, vars_)
        assert f"/test-sets/ts-1?project_id={project_id}" in html

    def test_test_set_path_omits_project_id_when_none(self, template_service):
        vars_ = _base_completion_vars(
            project_id=None,
            test_run_id=None,
            test_set_id="ts-1",
        )
        html = template_service.render_template(EmailTemplate.TASK_COMPLETION, vars_)
        assert "?project_id=" not in html
        assert 'href="https://app.example.test/test-sets/ts-1"' in html


@pytest.mark.unit
class TestTaskAssignmentDeepLink:
    """TASK_ASSIGNMENT deep link includes ?project_id when set."""

    def test_includes_project_id_when_set(self, template_service):
        project_id = str(uuid.uuid4())
        html = template_service.render_template(
            EmailTemplate.TASK_ASSIGNMENT,
            _base_assignment_vars(project_id=project_id),
        )
        assert f"/tasks/task-1?project_id={project_id}" in html

    def test_omits_project_id_when_none(self, template_service):
        html = template_service.render_template(
            EmailTemplate.TASK_ASSIGNMENT,
            _base_assignment_vars(project_id=None),
        )
        assert "?project_id=" not in html
        assert 'href="https://app.example.test/tasks/task-1"' in html
