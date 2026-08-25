"""Unit tests for generate_and_save_owasp_test_set.

Regression coverage for a missing `tests_generated` keyword argument on the
`_build_task_result(...)` call inside this task: `_build_task_result` requires
it with no default, so every invocation raised `TypeError` -- but only after
`_save_test_set_to_database` had already committed a new test set row. The
generic `except Exception` handler re-raised it as a plain `Exception`, which
Celery's `autoretry_for = (Exception,)` retried up to 3 more times, each
retry creating another orphaned test set before failing again the same way.

That fix closed the *trigger* (the specific missing kwarg), not the
*mechanism*: any exception raised after the save -- in result-building or
logging -- was still caught by the same outer `except Exception` and still
retried. `TestPostSaveFailureIsolation` below covers the mechanism fix: the
post-save section runs in its own try/except that returns a minimal result
instead of re-raising, so a failure there can no longer cause a duplicate
save.

These tests call the task body directly (`.run(...)`) with everything past
the task boundary mocked, so a regression that reintroduces an arity mismatch
in the `_build_task_result` call -- or any other exception raised after the
save step -- fails the test instead of silently multiplying test sets.
"""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.jobs.test_set import generate_and_save_owasp_test_set

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
            "rhesis.backend.jobs.test_set._resolve_generation_model",
            return_value="fake-model",
        ),
        patch(
            "rhesis.sdk.synthesizers.OWASPSynthesizer",
            return_value=mock_synthesizer,
        ),
        patch(
            "rhesis.backend.jobs.test_set._save_test_set_to_database",
            return_value=_fake_db_test_set(),
        ),
        # dispatch_accrual is fire-and-forget (queues a Celery message), but
        # these tests keep everything past the task boundary mocked -- see
        # module docstring -- so it's stubbed out here too rather than
        # actually touching the broker.
        patch("rhesis.backend.jobs.test_set.dispatch_accrual"),
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


@pytest.mark.unit
class TestOwaspTestSetDispatchesAccrual:
    """OWASP-generated tests must count against the org's test-generation
    quota, same as every other generation path -- see the sibling
    `generate_and_save_test_set` task's `dispatch_accrual(...)` call near its
    own save step. Previously this task never called it at all, so OWASP
    generation was unmetered.
    """

    def test_dispatch_accrual_called_with_actual_tests_generated(self):
        fake_sdk_test_set = MagicMock()
        fake_sdk_test_set.tests = [MagicMock() for _ in range(3)]

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
                "rhesis.backend.jobs.test_set._resolve_generation_model",
                return_value="fake-model",
            ),
            patch(
                "rhesis.sdk.synthesizers.OWASPSynthesizer",
                return_value=mock_synthesizer,
            ),
            patch(
                "rhesis.backend.jobs.test_set._save_test_set_to_database",
                return_value=_fake_db_test_set(),
            ),
            patch("rhesis.backend.jobs.test_set.dispatch_accrual") as mock_dispatch,
        ):
            result = generate_and_save_owasp_test_set.run(
                framework="llm",
                purpose="customer service chatbot for a bank",
                categories=["llm01"],
                num_tests=10,
            )

        # Amount accrued must be the actual generated count (3), not the
        # requested count (10) -- same distinction as
        # test_reports_actual_tests_generated_not_requested_count above.
        mock_dispatch.assert_called_once_with("org-1", QuotaResource.TEST_GENERATION, 3)
        assert result["num_tests_generated"] == 3


@pytest.mark.unit
class TestPostSaveFailureIsolation:
    """Mechanism-level regression coverage (see module docstring).

    Once `_save_test_set_to_database` has succeeded, nothing downstream may
    propagate into the task's outer `except Exception` handler: that handler
    is what Celery's `autoretry_for = (Exception,)` (tasks/base.py) retries,
    and a retry here would re-run generation *and* re-save, producing a
    second test set for a save that already completed.
    """

    def test_build_task_result_failure_does_not_raise_and_keeps_saved_id(self):
        fake_sdk_test_set = MagicMock()
        fake_sdk_test_set.tests = [MagicMock() for _ in range(4)]

        mock_synthesizer = MagicMock()
        mock_synthesizer.generate.return_value = fake_sdk_test_set

        db_test_set = _fake_db_test_set()

        with (
            patch.object(
                generate_and_save_owasp_test_set,
                "get_tenant_context",
                return_value=("org-1", "user-1", "proj-1"),
            ),
            patch.object(generate_and_save_owasp_test_set, "update_state"),
            patch(
                "rhesis.backend.jobs.test_set._resolve_generation_model",
                return_value="fake-model",
            ),
            patch(
                "rhesis.sdk.synthesizers.OWASPSynthesizer",
                return_value=mock_synthesizer,
            ),
            patch(
                "rhesis.backend.jobs.test_set._save_test_set_to_database",
                return_value=db_test_set,
            ),
            patch(
                "rhesis.backend.jobs.test_set._build_task_result",
                side_effect=RuntimeError("boom: result building blew up"),
            ),
            patch("rhesis.backend.jobs.test_set.dispatch_accrual") as mock_dispatch,
        ):
            # (a) Must return normally. If the fix regressed and this
            # exception reached the outer handler, `.run()` would raise here
            # and fail the test -- exactly the condition that used to send
            # Celery's autoretry_for back through generation + save.
            result = generate_and_save_owasp_test_set.run(
                framework="llm",
                purpose="customer service chatbot for a bank",
                categories=["llm01"],
                num_tests=5,
            )

        # (b) The fallback result still reflects the test set that was
        # actually saved before result-building blew up.
        assert result["test_set_id"] == db_test_set.id
        assert result["save_successful"] is True
        assert result["num_tests_generated"] == 4
        assert "result_build_error" in result

        # _build_task_result raises before the guarded section reaches
        # dispatch_accrual, so accrual must not fire for a task that is
        # reporting a (contained) failure.
        mock_dispatch.assert_not_called()
