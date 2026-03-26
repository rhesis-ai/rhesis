"""Unit tests for _signal_penelope_conversation_complete in MultiTurnRunner."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.tasks.execution.executors.runners import (
    _signal_penelope_conversation_complete,
)

PROJECT_ID = "project-uuid-1"
ORG_ID = "org-uuid-1"
TRACE_ID = "trace-uuid-abc"
CONVERSATION_ID = "conv-uuid-xyz"


def _penelope_trace_with_conversation_id(conversation_id=CONVERSATION_ID):
    """Build a minimal Penelope trace dict with conversation_summary."""
    return {
        "conversation_summary": [
            {"turn": 1, "conversation_id": None, "penelope_message": "hi"},
            {"turn": 2, "conversation_id": conversation_id, "penelope_message": "ok"},
        ],
    }


@pytest.mark.unit
class TestSignalPenelopeConversationComplete:

    def test_extracts_conversation_id_and_signals(self):
        db = MagicMock()
        trace = _penelope_trace_with_conversation_id()

        with (
            patch(
                "rhesis.backend.app.crud.get_trace_id_for_conversation",
                return_value=TRACE_ID,
            ) as mock_lookup,
            patch(
                "rhesis.backend.app.services.telemetry.trace_metrics_cache."
                "signal_conversation_complete",
            ) as mock_signal,
        ):
            _signal_penelope_conversation_complete(db, trace, PROJECT_ID, ORG_ID)

        mock_lookup.assert_called_once_with(
            db, CONVERSATION_ID, PROJECT_ID, ORG_ID,
        )
        mock_signal.assert_called_once_with(TRACE_ID, PROJECT_ID, ORG_ID)

    def test_uses_first_non_null_conversation_id(self):
        db = MagicMock()
        trace = {
            "conversation_summary": [
                {"turn": 1, "conversation_id": None},
                {"turn": 2, "conversation_id": None},
                {"turn": 3, "conversation_id": "conv-first"},
                {"turn": 4, "conversation_id": "conv-second"},
            ],
        }

        with (
            patch(
                "rhesis.backend.app.crud.get_trace_id_for_conversation",
                return_value=TRACE_ID,
            ) as mock_lookup,
            patch(
                "rhesis.backend.app.services.telemetry.trace_metrics_cache."
                "signal_conversation_complete",
            ),
        ):
            _signal_penelope_conversation_complete(db, trace, PROJECT_ID, ORG_ID)

        mock_lookup.assert_called_once_with(
            db, "conv-first", PROJECT_ID, ORG_ID,
        )

    def test_returns_silently_when_no_conversation_summary(self):
        db = MagicMock()

        with patch(
            "rhesis.backend.app.crud.get_trace_id_for_conversation",
        ) as mock_lookup:
            _signal_penelope_conversation_complete(db, {}, PROJECT_ID, ORG_ID)

        mock_lookup.assert_not_called()

    def test_returns_silently_when_all_conversation_ids_null(self):
        db = MagicMock()
        trace = {
            "conversation_summary": [
                {"turn": 1, "conversation_id": None},
                {"turn": 2},
            ],
        }

        with patch(
            "rhesis.backend.app.crud.get_trace_id_for_conversation",
        ) as mock_lookup:
            _signal_penelope_conversation_complete(db, trace, PROJECT_ID, ORG_ID)

        mock_lookup.assert_not_called()

    def test_returns_silently_when_trace_id_not_found(self):
        db = MagicMock()
        trace = _penelope_trace_with_conversation_id()

        with (
            patch(
                "rhesis.backend.app.crud.get_trace_id_for_conversation",
                return_value=None,
            ),
            patch(
                "rhesis.backend.app.services.telemetry.trace_metrics_cache."
                "signal_conversation_complete",
            ) as mock_signal,
        ):
            _signal_penelope_conversation_complete(db, trace, PROJECT_ID, ORG_ID)

        mock_signal.assert_not_called()

    def test_catches_exceptions_without_propagating(self):
        db = MagicMock()
        trace = _penelope_trace_with_conversation_id()

        with patch(
            "rhesis.backend.app.crud.get_trace_id_for_conversation",
            side_effect=RuntimeError("db exploded"),
        ):
            _signal_penelope_conversation_complete(db, trace, PROJECT_ID, ORG_ID)
