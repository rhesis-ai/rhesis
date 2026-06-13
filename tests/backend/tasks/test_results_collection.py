"""
Unit tests for trigger_results_collection in tasks/execution/shared.py.

Covers the task dispatch boundary: verifies that all tenant context fields
(including project_id) are forwarded to the collect_results chord callback
via Celery task headers.
"""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from rhesis.backend.tasks.execution.shared import trigger_results_collection

_ORG_ID = UUID("aaaaaaaa-0000-0000-0000-000000000001")
_USER_ID = UUID("bbbbbbbb-0000-0000-0000-000000000002")
_PROJECT_ID = UUID("cccccccc-0000-0000-0000-000000000003")
_TEST_RUN_ID = "dddddddd-0000-0000-0000-000000000004"


def _make_test_config(**overrides):
    cfg = MagicMock()
    cfg.organization_id = _ORG_ID
    cfg.user_id = _USER_ID
    cfg.project_id = _PROJECT_ID
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _capture_headers(test_config, results=None):
    """Call trigger_results_collection and return the headers dict passed to .set()."""
    with patch("rhesis.backend.tasks.execution.shared.collect_results") as mock_cr:
        mock_sig = MagicMock()
        mock_cr.s.return_value = mock_sig
        mock_sig.set.return_value = mock_sig

        trigger_results_collection(test_config, _TEST_RUN_ID, results or [])

        mock_sig.set.assert_called_once()
        return mock_sig.set.call_args.kwargs["headers"]


class TestTriggerResultsCollectionHeaders:
    """Headers passed to collect_results must include all three tenant fields."""

    def test_organization_id_in_headers(self):
        headers = _capture_headers(_make_test_config())
        assert headers["organization_id"] == str(_ORG_ID)

    def test_user_id_in_headers(self):
        headers = _capture_headers(_make_test_config())
        assert headers["user_id"] == str(_USER_ID)

    def test_project_id_in_headers(self):
        headers = _capture_headers(_make_test_config())
        assert headers["project_id"] == str(_PROJECT_ID)

    def test_test_run_id_in_headers(self):
        headers = _capture_headers(_make_test_config())
        assert headers["test_run_id"] == _TEST_RUN_ID

    def test_none_project_id_becomes_none_in_headers(self):
        cfg = _make_test_config(project_id=None)
        headers = _capture_headers(cfg)
        assert headers["project_id"] is None

    def test_none_organization_id_becomes_none_in_headers(self):
        cfg = _make_test_config(organization_id=None)
        headers = _capture_headers(cfg)
        assert headers["organization_id"] is None

    def test_none_user_id_becomes_none_in_headers(self):
        cfg = _make_test_config(user_id=None)
        headers = _capture_headers(cfg)
        assert headers["user_id"] is None

    def test_results_forwarded_to_signature(self):
        results = [{"test_id": "t1", "status": "passed"}]
        with patch("rhesis.backend.tasks.execution.shared.collect_results") as mock_cr:
            mock_sig = MagicMock()
            mock_cr.s.return_value = mock_sig
            mock_sig.set.return_value = mock_sig

            trigger_results_collection(_make_test_config(), _TEST_RUN_ID, results)

            mock_cr.s.assert_called_once_with(results)
