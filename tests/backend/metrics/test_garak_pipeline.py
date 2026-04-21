"""
Tests for the garak_notes pipeline: test_metadata → detector.

Verifies that probe-coupled detector context (triggers, repeat_word) flows
correctly from test.test_metadata["garak_notes"] all the way through the
evaluation pipeline to GarakDetectorMetric.evaluate(), covering every link:

  1. _inject_probe_notes correctly merges notes into MetricConfig.parameters
  2. MetricFactory / GarakMetricFactory forwards probe_notes to the constructor
  3. GarakDetectorMetric stores probe_notes and uses them in evaluate()
  4. _evaluate_single_turn_metrics reads garak_notes and threads them end-to-end
"""

import dataclasses
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.sdk.metrics import MetricConfig
from rhesis.sdk.metrics.base import Backend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _garak_metric_config(
    detector_path: str = "garak.detectors.promptinject.AttackRogueString",
    name: str = "AttackRogueString",
    parameters: Optional[Dict[str, Any]] = None,
) -> MetricConfig:
    """Build a MetricConfig that looks like what the backend produces for a Garak metric."""
    return MetricConfig(
        class_name="GarakDetectorMetric",
        backend=Backend.GARAK,
        name=name,
        description=f"Garak detector: {detector_path}",
        evaluation_prompt=detector_path,
        score_type="numeric",
        threshold=0.5,
        threshold_operator="<",
        parameters=parameters or {},
    )


def _non_garak_metric_config() -> MetricConfig:
    return MetricConfig(
        class_name="AnswerRelevancy",
        backend=Backend.RHESIS,
        name="AnswerRelevancy",
        description="A non-garak metric",
        score_type="numeric",
        threshold=0.5,
    )


# ===========================================================================
# Link 1: _inject_probe_notes
# ===========================================================================


class TestInjectProbeNotes:
    """Verify _inject_probe_notes merges notes into the right MetricConfigs."""

    def _inject(self, metric_configs, probe_notes):
        from rhesis.backend.tasks.execution.batch.evaluation import _inject_probe_notes

        return _inject_probe_notes(metric_configs, probe_notes)

    def test_returns_original_when_no_notes(self):
        configs = [_garak_metric_config()]
        result = self._inject(configs, None)
        assert result is configs

    def test_returns_original_when_empty_notes(self):
        """Empty dict is falsy — treated as 'nothing to inject', returns original list."""
        configs = [_garak_metric_config()]
        result = self._inject(configs, {})
        assert result is configs

    def test_injects_probe_notes_into_garak_metric(self):
        notes = {"triggers": ["I hate humans"]}
        configs = [_garak_metric_config()]
        result = self._inject(configs, notes)

        assert len(result) == 1
        assert result[0].parameters["probe_notes"] == notes

    def test_does_not_modify_original_config(self):
        notes = {"triggers": ["I hate humans"]}
        original = _garak_metric_config()
        self._inject([original], notes)
        assert "probe_notes" not in (original.parameters or {})

    def test_leaves_non_garak_metrics_untouched(self):
        notes = {"triggers": ["I hate humans"]}
        non_garak = _non_garak_metric_config()
        result = self._inject([non_garak], notes)
        assert result[0] is non_garak

    def test_mixed_configs_only_injects_into_context_required(self):
        notes = {"triggers": ["I hate humans"]}
        garak = _garak_metric_config()
        non_garak = _non_garak_metric_config()
        standalone = _garak_metric_config(
            detector_path="garak.detectors.mitigation.MitigationBypass",
            name="MitigationBypass",
        )

        result = self._inject([garak, non_garak, standalone], notes)

        assert result[0].parameters["probe_notes"] == notes
        assert result[1] is non_garak
        assert "probe_notes" not in (result[2].parameters or {})

    def test_does_not_overwrite_existing_probe_notes(self):
        """probe_notes already in parameters must not be overwritten."""
        existing_notes = {"triggers": ["original"]}
        config = _garak_metric_config(parameters={"probe_notes": existing_notes})
        result = self._inject([config], {"triggers": ["new"]})
        assert result[0].parameters["probe_notes"] == existing_notes

    def test_preserves_existing_parameters(self):
        notes = {"triggers": ["test"]}
        config = _garak_metric_config(parameters={"threshold": 0.3, "model": "gpt-4"})
        result = self._inject([config], notes)

        assert result[0].parameters["probe_notes"] == notes
        assert result[0].parameters["threshold"] == 0.3
        assert result[0].parameters["model"] == "gpt-4"

    def test_short_path_is_normalised_before_lookup(self):
        """DB may store short paths like 'encoding.DecodeMatch' instead of
        'garak.detectors.encoding.DecodeMatch'.  _inject_probe_notes must
        normalise before checking CONTEXT_REQUIRED_NOTES."""
        notes = {"triggers": ["<script>alert(1)</script>"]}
        config = _garak_metric_config(
            detector_path="encoding.DecodeMatch",
            name="DecodeMatch",
        )
        result = self._inject([config], notes)

        assert len(result) == 1
        assert result[0].parameters["probe_notes"] == notes

    def test_short_path_standalone_not_injected(self):
        """A short-path standalone detector should NOT receive probe_notes."""
        notes = {"triggers": ["test"]}
        config = _garak_metric_config(
            detector_path="mitigation.MitigationBypass",
            name="MitigationBypass",
        )
        result = self._inject([config], notes)
        assert "probe_notes" not in (result[0].parameters or {})


# ===========================================================================
# Link 2+3: MetricFactory → GarakMetricFactory → GarakDetectorMetric
# ===========================================================================


class TestFactoryPassesProbeNotes:
    """Verify GarakMetricFactory.create passes probe_notes to the constructor.

    These tests patch GarakDetectorMetric.__init__ to avoid triggering heavy
    garak imports; what matters is that the factory forwards the kwarg.
    """

    def _create_via_factory(self, **kwargs):
        from rhesis.sdk.metrics.providers.garak.factory import GarakMetricFactory

        factory = GarakMetricFactory()
        return factory.create("GarakDetectorMetric", **kwargs)

    def test_factory_passes_probe_notes(self):
        notes = {"triggers": ["I hate humans"]}
        with patch(
            "rhesis.sdk.metrics.providers.garak.factory.GarakDetectorMetric"
        ) as MockCls:
            self._create_via_factory(
                detector_class="garak.detectors.promptinject.AttackRogueString",
                probe_notes=notes,
            )

            MockCls.assert_called_once()
            call_kwargs = MockCls.call_args.kwargs
            assert call_kwargs["probe_notes"] == notes

    def test_factory_without_probe_notes_defaults_to_absent(self):
        with patch(
            "rhesis.sdk.metrics.providers.garak.factory.GarakDetectorMetric"
        ) as MockCls:
            self._create_via_factory(
                detector_class="garak.detectors.promptinject.AttackRogueString",
            )

            call_kwargs = MockCls.call_args.kwargs
            assert "probe_notes" not in call_kwargs

    def test_factory_filters_unknown_params(self):
        """Unknown params are dropped; probe_notes is kept."""
        notes = {"triggers": ["test"]}
        with patch(
            "rhesis.sdk.metrics.providers.garak.factory.GarakDetectorMetric"
        ) as MockCls:
            self._create_via_factory(
                detector_class="garak.detectors.continuation.Continuation",
                probe_notes=notes,
                unknown_param="should_be_dropped",
            )

            call_kwargs = MockCls.call_args.kwargs
            assert call_kwargs["probe_notes"] == notes
            assert "unknown_param" not in call_kwargs


# ===========================================================================
# Link 2b: prepare_metrics flattens parameters["probe_notes"] into factory call
# ===========================================================================


class TestPrepareMetricsForwardsProbeNotes:
    """Verify prepare_metrics passes probe_notes from MetricConfig.parameters
    through to the factory so the resulting GarakDetectorMetric receives it."""

    def test_probe_notes_in_parameters_reaches_factory(self):
        from rhesis.backend.metrics.strategies.local import prepare_metrics

        notes = {"triggers": ["I hate humans"]}
        config = _garak_metric_config(
            detector_path="garak.detectors.promptinject.AttackRogueString",
            parameters={"probe_notes": notes},
        )

        with patch("rhesis.sdk.metrics.MetricFactory.create") as mock_create:
            mock_metric = MagicMock()
            mock_metric.requires_ground_truth = False
            mock_create.return_value = mock_metric

            tasks = prepare_metrics([config], expected_output="")

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["probe_notes"] == notes

    def test_no_probe_notes_in_parameters(self):
        from rhesis.backend.metrics.strategies.local import prepare_metrics

        config = _garak_metric_config(parameters={})

        with patch("rhesis.sdk.metrics.MetricFactory.create") as mock_create:
            mock_metric = MagicMock()
            mock_metric.requires_ground_truth = False
            mock_create.return_value = mock_metric

            tasks = prepare_metrics([config], expected_output="")

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            assert "probe_notes" not in call_kwargs


# ===========================================================================
# Link 3+4: GarakDetectorMetric uses probe_notes in evaluate
# ===========================================================================


class TestProbeNotesFallbackInEvaluate:
    """Verify GarakDetectorMetric.evaluate() uses self._probe_notes when
    explicit notes arg is not provided."""

    @pytest.fixture
    def mock_garak(self):
        """Patch garak imports so tests don't need garak installed.

        Uses a real dict for attempt.notes so we can inspect what was merged
        after evaluate() runs.
        """
        notes_dict = {}
        mock_attempt_class = MagicMock()
        mock_attempt_instance = MagicMock()
        mock_attempt_instance.notes = notes_dict
        mock_attempt_instance.outputs = []
        mock_attempt_class.return_value = mock_attempt_instance

        mock_message_class = MagicMock()

        mock_module = MagicMock()
        mock_module.Attempt = mock_attempt_class
        mock_module.Message = mock_message_class

        with patch.dict("sys.modules", {"garak.attempt": mock_module}):
            with patch("importlib.import_module") as mock_import:
                mock_detector_instance = MagicMock()
                mock_detector_instance.detect.return_value = [0.3]
                mock_detector_class = MagicMock(return_value=mock_detector_instance)
                mock_detector_module = MagicMock()
                mock_detector_module.AttackRogueString = mock_detector_class
                mock_import.return_value = mock_detector_module

                yield {
                    "attempt_class": mock_attempt_class,
                    "attempt_instance": mock_attempt_instance,
                    "detector_instance": mock_detector_instance,
                    "notes_dict": notes_dict,
                }

    def test_probe_notes_injected_into_attempt(self, mock_garak):
        from rhesis.sdk.metrics.providers.garak import GarakDetectorMetric

        notes = {"triggers": ["I hate humans"]}
        metric = GarakDetectorMetric(
            detector_class="garak.detectors.promptinject.AttackRogueString",
            probe_notes=notes,
        )

        metric.evaluate(input="test prompt", output="safe response")

        assert mock_garak["notes_dict"] == {"triggers": ["I hate humans"]}

    def test_explicit_notes_override_probe_notes(self, mock_garak):
        from rhesis.sdk.metrics.providers.garak import GarakDetectorMetric

        constructor_notes = {"triggers": ["original"]}
        override_notes = {"triggers": ["override"]}
        metric = GarakDetectorMetric(
            detector_class="garak.detectors.promptinject.AttackRogueString",
            probe_notes=constructor_notes,
        )

        metric.evaluate(input="test", output="test", notes=override_notes)

        assert mock_garak["notes_dict"]["triggers"] == ["override"]

    def test_no_notes_at_all_leaves_attempt_notes_empty(self, mock_garak):
        from rhesis.sdk.metrics.providers.garak import GarakDetectorMetric

        metric = GarakDetectorMetric(
            detector_class="garak.detectors.promptinject.AttackRogueString",
        )

        metric.evaluate(input="test", output="test")

        assert mock_garak["notes_dict"] == {}


# ===========================================================================
# Link 5: Full pipeline: _evaluate_single_turn_metrics end-to-end
# ===========================================================================


class TestEvaluateSingleTurnGarakNotes:
    """Verify _evaluate_single_turn_metrics reads garak_notes from test_metadata
    and threads them through the evaluator so the detector receives them."""

    @pytest.mark.asyncio
    async def test_garak_notes_from_metadata_reach_evaluator(self):
        """The a_evaluate call receives MetricConfigs with probe_notes injected."""
        from rhesis.backend.tasks.execution.batch.evaluation import (
            _evaluate_single_turn_metrics,
        )

        garak_notes = {"triggers": ["I hate humans"]}
        mock_test = SimpleNamespace(
            test_metadata={
                "source": "garak",
                "garak_module": "promptinject",
                "garak_notes": garak_notes,
            }
        )

        detector_path = "garak.detectors.promptinject.AttackRogueString"
        metric_config = _garak_metric_config(detector_path=detector_path)
        ctx = SimpleNamespace(metric_configs=[metric_config])

        mock_evaluator = AsyncMock()
        mock_evaluator.a_evaluate.return_value = {"AttackRogueString": {"score": 0.0}}

        output = {"response": "safe response", "metadata": None, "tool_calls": None}

        await _evaluate_single_turn_metrics(
            ctx, mock_evaluator, mock_test, output, "test prompt", ""
        )

        mock_evaluator.a_evaluate.assert_called_once()
        call_kwargs = mock_evaluator.a_evaluate.call_args
        metrics_arg = call_kwargs.kwargs.get("metrics") or call_kwargs[1].get("metrics")
        if metrics_arg is None:
            metrics_arg = call_kwargs[0][5] if len(call_kwargs[0]) > 5 else call_kwargs.kwargs["metrics"]

        assert len(metrics_arg) == 1
        assert metrics_arg[0].parameters["probe_notes"] == garak_notes

    @pytest.mark.asyncio
    async def test_missing_garak_notes_does_not_inject(self):
        """When test_metadata has no garak_notes, configs pass through unchanged."""
        from rhesis.backend.tasks.execution.batch.evaluation import (
            _evaluate_single_turn_metrics,
        )

        mock_test = SimpleNamespace(
            test_metadata={"source": "garak", "garak_module": "promptinject"}
        )

        metric_config = _garak_metric_config()
        ctx = SimpleNamespace(metric_configs=[metric_config])

        mock_evaluator = AsyncMock()
        mock_evaluator.a_evaluate.return_value = {}

        output = {"response": "safe", "metadata": None, "tool_calls": None}

        await _evaluate_single_turn_metrics(
            ctx, mock_evaluator, mock_test, output, "test", ""
        )

        call_kwargs = mock_evaluator.a_evaluate.call_args
        metrics_arg = call_kwargs.kwargs.get("metrics") or call_kwargs[1].get("metrics")
        if metrics_arg is None:
            metrics_arg = call_kwargs.kwargs["metrics"]

        assert "probe_notes" not in (metrics_arg[0].parameters or {})

    @pytest.mark.asyncio
    async def test_null_test_metadata_does_not_inject(self):
        """When test has no test_metadata at all, pipeline handles gracefully."""
        from rhesis.backend.tasks.execution.batch.evaluation import (
            _evaluate_single_turn_metrics,
        )

        mock_test = SimpleNamespace(test_metadata=None)

        metric_config = _garak_metric_config()
        ctx = SimpleNamespace(metric_configs=[metric_config])

        mock_evaluator = AsyncMock()
        mock_evaluator.a_evaluate.return_value = {}

        output = {"response": "safe", "metadata": None, "tool_calls": None}

        await _evaluate_single_turn_metrics(
            ctx, mock_evaluator, mock_test, output, "test", ""
        )

        call_kwargs = mock_evaluator.a_evaluate.call_args
        metrics_arg = call_kwargs.kwargs.get("metrics") or call_kwargs[1].get("metrics")
        if metrics_arg is None:
            metrics_arg = call_kwargs.kwargs["metrics"]

        assert "probe_notes" not in (metrics_arg[0].parameters or {})


# ===========================================================================
# LocalStrategy: inconclusive result passthrough
# ===========================================================================


class TestLocalStrategyInconclusivePassthrough:
    """Verify LocalStrategy passes is_successful=None when a metric returns
    inconclusive=True, rather than collapsing it to False via ScoreEvaluator.

    This is the critical path for GarakDetectorMetric when probe context is
    missing — the result should be stored as 'unknown', not 'failed'.
    """

    def _make_inconclusive_result(self):
        from rhesis.sdk.metrics.base import MetricResult

        return MetricResult(
            score=None,
            details={
                "is_successful": None,
                "inconclusive": True,
                "reason": "Detector returned no scores because notes['triggers'] was not provided.",
            },
        )

    def _make_future(self, result):
        import concurrent.futures

        f = concurrent.futures.Future()
        f.set_result(result)
        return f

    def test_inconclusive_yields_none_is_successful(self):
        """_process_metric_result must set is_successful=None for inconclusive results."""
        from rhesis.backend.metrics.strategies.local import LocalStrategy
        from rhesis.sdk.metrics import MetricConfig
        from rhesis.sdk.metrics.base import Backend

        strategy = LocalStrategy()
        config = MetricConfig(
            class_name="GarakDetectorMetric",
            backend=Backend.GARAK,
            name="AttackRogueString",
            threshold=0.5,
            threshold_operator="<",
        )
        future = self._make_future(self._make_inconclusive_result())
        result = strategy._process_metric_result(future, "GarakDetectorMetric", config, "garak")

        assert result["is_successful"] is None
        assert result["score"] is None

    def test_inconclusive_does_not_invoke_score_evaluator(self):
        """ScoreEvaluator must NOT be called when the result is inconclusive."""
        from unittest.mock import MagicMock

        from rhesis.backend.metrics.score_evaluator import ScoreEvaluator
        from rhesis.backend.metrics.strategies.local import LocalStrategy
        from rhesis.sdk.metrics import MetricConfig
        from rhesis.sdk.metrics.base import Backend

        mock_evaluator = MagicMock(spec=ScoreEvaluator)
        strategy = LocalStrategy(score_evaluator=mock_evaluator)
        config = MetricConfig(
            class_name="GarakDetectorMetric",
            backend=Backend.GARAK,
            name="AttackRogueString",
            threshold=0.5,
            threshold_operator="<",
        )
        future = self._make_future(self._make_inconclusive_result())
        strategy._process_metric_result(future, "GarakDetectorMetric", config, "garak")

        mock_evaluator.evaluate_score.assert_not_called()

    def test_normal_result_still_uses_score_evaluator(self):
        """A normal result with no is_successful in details still goes through ScoreEvaluator."""
        import concurrent.futures
        from unittest.mock import MagicMock

        from rhesis.backend.metrics.score_evaluator import ScoreEvaluator
        from rhesis.backend.metrics.strategies.local import LocalStrategy
        from rhesis.sdk.metrics import MetricConfig
        from rhesis.sdk.metrics.base import Backend, MetricResult

        mock_evaluator = MagicMock(spec=ScoreEvaluator)
        mock_evaluator.evaluate_score.return_value = True
        strategy = LocalStrategy(score_evaluator=mock_evaluator)
        config = MetricConfig(
            class_name="GarakDetectorMetric",
            backend=Backend.GARAK,
            name="AttackRogueString",
            threshold=0.5,
            threshold_operator="<",
        )

        normal_result = MetricResult(score=0.2, details={})
        f = concurrent.futures.Future()
        f.set_result(normal_result)

        result = strategy._process_metric_result(f, "GarakDetectorMetric", config, "garak")

        mock_evaluator.evaluate_score.assert_called_once()
        assert result["is_successful"] is True
