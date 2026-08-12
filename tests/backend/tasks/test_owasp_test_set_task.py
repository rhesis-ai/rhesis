"""Unit tests for generate_and_save_owasp_test_set.

Regression coverage for a missing `tests_generated` keyword argument on the
`_build_task_result(...)` call inside this task: `_build_task_result` requires
it with no default, so every invocation raised `TypeError` -- but only after
`_save_test_set_to_database` had already committed a new test set row. The
generic `except Exception` handler re-raised it as a plain `Exception`, which
Celery's `autoretry_for = (Exception,)` retried up to 3 more times, each
retry creating another orphaned test set before failing again the same way.

These tests call the task body directly (`.run(...)`) with everything past
the task boundary mocked, so a regression that reintroduces an arity mismatch
in the `_build_task_result` call -- or any other exception raised after the
save step -- fails the test instead of silently multiplying test sets.
"""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.tasks.test_set import generate_and_save_owasp_test_set

_EXPECTED_RESULT_KEYS = {
    "test_set_id",
    "test_set_name",
    "description",
    "short_description",
    "num_tests_generated",
    "num_tests_requested",
    "synthesizer_class",
    "synthesizer_params",
    "batch_size",
    "metadata",
    "organization_id",
    "user_id",
    "save_successful",
}


def _fake_db_test_set():
    row = MagicMock()
    row.id = "ts-owasp-1"
    row.name = "OWASP Test Set"
    row.description = "desc"
    row.short_description = "short"
    row.attributes = {"metadata": {}}
    return row


def _run_task(*, num_tests_requested, tests_actually_generated, **kwargs):
    """Run the real task body with generation/persistence mocked out."""
    fake_sdk_test_set = MagicMock()
    fake_sdk_test_set.tests = [MagicMock() for _ in range(tests_actually_generated)]

    mock_synthesizer = MagicMock()
    mock_synthesizer.generate.return_value = fake_sdk_test_set

    with (
        patch.object(
            generate_and_save_owasp_test_set,
            "get_tenant_context",
            return_value=("org-1", "user-1", "proj-1"),
        ),
        patch.object(generate_and_save_owasp_test_set, "update_state"),
        patch(
            "rhesis.backend.tasks.test_set._resolve_generation_model",
            return_value="fake-model",
        ),
        patch(
            "rhesis.sdk.synthesizers.OWASPSynthesizer",
            return_value=mock_synthesizer,
        ),
        patch(
            "rhesis.backend.tasks.test_set._save_test_set_to_database",
            return_value=_fake_db_test_set(),
        ),
    ):
        return generate_and_save_owasp_test_set.run(
            framework="llm",
            purpose="customer service chatbot for a bank",
            categories=["llm01"],
            num_tests=num_tests_requested,
            **kwargs,
        )


@pytest.mark.unit
class TestGenerateAndSaveOwaspTestSet:
    def test_completes_without_raising_and_returns_expected_keys(self):
        result = _run_task(num_tests_requested=5, tests_actually_generated=5)

        assert set(result.keys()) == _EXPECTED_RESULT_KEYS
        assert result["save_successful"] is True
        assert result["test_set_id"] == "ts-owasp-1"

    def test_reports_actual_tests_generated_not_requested_count(self):
        """`tests_generated` must come from the SDK test set's own tests
        list, not from echoing back `num_tests` requested -- generation can
        legitimately produce fewer (or more) tests than asked for."""
        result = _run_task(num_tests_requested=10, tests_actually_generated=3)

        assert result["num_tests_generated"] == 3
        assert result["num_tests_requested"] == 10
