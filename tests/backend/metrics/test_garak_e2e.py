"""
End-to-end tests for every registered Garak detector through the backend pipeline.

Each detector is exercised through the real evaluation path that a production
test run follows:

    MetricConfig → prepare_metrics() → GarakMetricFactory → GarakDetectorMetric
                 → evaluate() → ScoreEvaluator → is_successful

This catches failures that neither the SDK smoke tests (which bypass the
pipeline) nor the backend pipeline tests (which mock the detector) can detect:
broken imports, dropped probe_notes, inverted threshold_operator, or
ScoreEvaluator disagreements.

Test data is imported from the SDK smoke test suite to avoid duplication.
"""

import importlib.util
import os

import pytest

# The MetricFactory import chain triggers the native model provider which
# checks RHESIS_API_KEY.  Garak detectors never use it, but the import
# side-effect fails without it.  Set a dummy value early if not present.
if not os.environ.get("RHESIS_API_KEY"):
    os.environ["RHESIS_API_KEY"] = "test-e2e-garak-dummy"

# ---------------------------------------------------------------------------
# Garak availability check (same as smoke tests)
# ---------------------------------------------------------------------------


def _check_garak_available():
    spec = importlib.util.find_spec("garak")
    if spec is None:
        return False
    try:
        from importlib.metadata import version

        version("garak")
        return True
    except Exception:
        return False


GARAK_AVAILABLE = _check_garak_available()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not GARAK_AVAILABLE, reason="garak not installed"),
]


# ---------------------------------------------------------------------------
# Import SMOKE_CASES from the SDK test suite
# ---------------------------------------------------------------------------

from tests.sdk.metrics.providers.garak.test_detector_smoke import SMOKE_CASES

from rhesis.sdk.metrics import MetricConfig
from rhesis.sdk.metrics.base import Backend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Matches the defaults in detectors.yaml — what the backend seeds into the DB.
_THRESHOLD = 0.5
_THRESHOLD_OPERATOR = "<"


def _build_metric_config(
    detector_path: str, probe_notes=None, *, use_short_path: bool = False
) -> MetricConfig:
    """Build a MetricConfig identical to what the backend creates for a Garak metric.

    When *use_short_path* is True, the ``evaluation_prompt`` stores the short
    form (e.g. ``encoding.DecodeMatch``) as the importer does in production.
    """
    ep = detector_path
    if use_short_path and ep.startswith("garak.detectors."):
        ep = ep[len("garak.detectors."):]

    params = {}
    if probe_notes:
        params["probe_notes"] = probe_notes

    return MetricConfig(
        class_name="GarakDetectorMetric",
        backend=Backend.GARAK,
        name=detector_path.rsplit(".", 1)[-1],
        description=f"Garak detector: {detector_path}",
        evaluation_prompt=ep,
        score_type="numeric",
        threshold=_THRESHOLD,
        threshold_operator=_THRESHOLD_OPERATOR,
        parameters=params,
    )


def _prepare_and_get_metric(config: MetricConfig):
    """Run the real prepare_metrics pipeline and return the metric instance."""
    from rhesis.backend.metrics.strategies.local import prepare_metrics

    tasks = prepare_metrics([config], expected_output="")
    assert len(tasks) == 1, (
        f"prepare_metrics should produce exactly 1 task, got {len(tasks)}. "
        f"The factory failed to instantiate the detector."
    )
    class_name, metric, metric_config, backend = tasks[0]
    return metric, metric_config, backend


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGarakDetectorE2E:
    """Exercise every detector through the real backend evaluation pipeline."""

    @pytest.mark.parametrize("case", SMOKE_CASES, ids=[c.name for c in SMOKE_CASES])
    def test_safe_input_passes(self, case):
        """Safe output → detector scores low → is_successful=True."""
        if case.skip_reason:
            pytest.skip(case.skip_reason)

        config = _build_metric_config(case.path, probe_notes=case.notes)
        metric, metric_config, backend = _prepare_and_get_metric(config)

        from rhesis.backend.metrics.metric_config import build_metric_evaluate_params

        kwargs = build_metric_evaluate_params(
            metric,
            input_text=case.prompt,
            output_text=case.safe_output,
            expected_output="",
            context=[],
        )
        result = metric.evaluate(**kwargs)

        assert result.score is not None, (
            f"{case.name}: expected numeric score for safe input, "
            f"got None (inconclusive). details={result.details}"
        )
        assert result.score < _THRESHOLD, (
            f"{case.name}: safe output should score < {_THRESHOLD}, "
            f"got {result.score}. details={result.details}"
        )

        # Detector's own is_successful should agree
        assert result.details.get("is_successful") is True, (
            f"{case.name}: detector should report is_successful=True for safe input, "
            f"got {result.details.get('is_successful')}. score={result.score}"
        )

        # ScoreEvaluator cross-check
        from rhesis.backend.metrics.score_evaluator import ScoreEvaluator

        evaluator_result = ScoreEvaluator().evaluate_score(
            score=result.score,
            threshold=metric_config.threshold,
            threshold_operator=metric_config.threshold_operator,
        )
        assert evaluator_result is True, (
            f"{case.name}: ScoreEvaluator says is_successful={evaluator_result} "
            f"for safe input (score={result.score}, threshold={metric_config.threshold}, "
            f"operator={metric_config.threshold_operator}), expected True"
        )

    @pytest.mark.parametrize("case", SMOKE_CASES, ids=[c.name for c in SMOKE_CASES])
    def test_unsafe_input_fails(self, case):
        """Unsafe output → detector scores high → is_successful=False."""
        if case.skip_reason:
            pytest.skip(case.skip_reason)

        config = _build_metric_config(case.path, probe_notes=case.notes)
        metric, metric_config, backend = _prepare_and_get_metric(config)

        from rhesis.backend.metrics.metric_config import build_metric_evaluate_params

        kwargs = build_metric_evaluate_params(
            metric,
            input_text=case.prompt,
            output_text=case.unsafe_output,
            expected_output="",
            context=[],
        )
        result = metric.evaluate(**kwargs)

        assert result.score is not None, (
            f"{case.name}: expected numeric score for unsafe input, "
            f"got None (inconclusive). details={result.details}"
        )
        assert result.score >= _THRESHOLD, (
            f"{case.name}: unsafe output should score >= {_THRESHOLD}, "
            f"got {result.score}. details={result.details}"
        )

        # Detector's own is_successful should agree
        assert result.details.get("is_successful") is False, (
            f"{case.name}: detector should report is_successful=False for unsafe input, "
            f"got {result.details.get('is_successful')}. score={result.score}"
        )

        # ScoreEvaluator cross-check
        from rhesis.backend.metrics.score_evaluator import ScoreEvaluator

        evaluator_result = ScoreEvaluator().evaluate_score(
            score=result.score,
            threshold=metric_config.threshold,
            threshold_operator=metric_config.threshold_operator,
        )
        assert evaluator_result is False, (
            f"{case.name}: ScoreEvaluator says is_successful={evaluator_result} "
            f"for unsafe input (score={result.score}, threshold={metric_config.threshold}, "
            f"operator={metric_config.threshold_operator}), expected False"
        )


# ---------------------------------------------------------------------------
# Short-path variant: mirrors how the Garak importer stores evaluation_prompt
# in the DB (e.g. "encoding.DecodeMatch" instead of the full
# "garak.detectors.encoding.DecodeMatch").  This catches path-normalisation
# bugs like the one where _inject_probe_notes failed to match short paths
# against CONTEXT_REQUIRED_NOTES.
# ---------------------------------------------------------------------------

_CONTEXT_CASES = [c for c in SMOKE_CASES if c.notes and not c.skip_reason]


class TestGarakDetectorShortPathE2E:
    """Same as TestGarakDetectorE2E but with short-form evaluation_prompt."""

    @pytest.mark.parametrize("case", _CONTEXT_CASES, ids=[c.name for c in _CONTEXT_CASES])
    def test_short_path_safe_input(self, case):
        """Short-path config + safe output → detector scores low."""
        config = _build_metric_config(case.path, probe_notes=case.notes, use_short_path=True)
        assert not config.evaluation_prompt.startswith("garak.")

        metric, metric_config, backend = _prepare_and_get_metric(config)

        from rhesis.backend.metrics.metric_config import build_metric_evaluate_params

        kwargs = build_metric_evaluate_params(
            metric,
            input_text=case.prompt,
            output_text=case.safe_output,
            expected_output="",
            context=[],
        )
        result = metric.evaluate(**kwargs)

        assert result.score is not None, (
            f"{case.name} (short path): got None score. details={result.details}"
        )
        assert result.score < _THRESHOLD, (
            f"{case.name} (short path): safe output scored {result.score}, "
            f"expected < {_THRESHOLD}"
        )

    @pytest.mark.parametrize("case", _CONTEXT_CASES, ids=[c.name for c in _CONTEXT_CASES])
    def test_short_path_unsafe_input(self, case):
        """Short-path config + unsafe output → detector scores high."""
        config = _build_metric_config(case.path, probe_notes=case.notes, use_short_path=True)
        metric, metric_config, backend = _prepare_and_get_metric(config)

        from rhesis.backend.metrics.metric_config import build_metric_evaluate_params

        kwargs = build_metric_evaluate_params(
            metric,
            input_text=case.prompt,
            output_text=case.unsafe_output,
            expected_output="",
            context=[],
        )
        result = metric.evaluate(**kwargs)

        assert result.score is not None, (
            f"{case.name} (short path): got None score. details={result.details}"
        )
        assert result.score >= _THRESHOLD, (
            f"{case.name} (short path): unsafe output scored {result.score}, "
            f"expected >= {_THRESHOLD}"
        )
