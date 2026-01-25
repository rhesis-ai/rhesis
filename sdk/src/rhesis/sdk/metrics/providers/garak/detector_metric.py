"""
Garak detector metric implementation.

This module wraps Garak detectors as Rhesis metrics, enabling
the use of Garak's vulnerability detection capabilities within
the Rhesis evaluation framework.
"""

import importlib
import logging
from typing import List, Optional, Union

from rhesis.sdk.metrics.base import (
    Backend,
    BaseMetric,
    MetricConfig,
    MetricResult,
    MetricScope,
    MetricType,
    ScoreType,
)
from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)


class GarakDetectorMetric(BaseMetric):
    """
    Wraps a Garak detector as a Rhesis metric backend.

    This metric class dynamically loads a Garak detector and uses it
    to evaluate model outputs. The detector determines whether the
    model's response represents a successful attack (vulnerability)
    or a proper defense.

    Garak detectors use the convention:
    - 0 = safe (no vulnerability detected)
    - 1 = detected (vulnerability/attack succeeded)

    This metric inverts this for Rhesis conventions:
    - pass = model defended against the attack
    - fail = attack succeeded (vulnerability)
    """

    def __init__(
        self,
        detector_class: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        model: Optional[Union[BaseLLM, str]] = None,
        **kwargs,
    ):
        """
        Initialize the Garak detector metric.

        Args:
            detector_class: Full path to the Garak detector class
                           (e.g., "garak.detectors.mitigation.MitigationBypass")
            name: Optional metric name
            description: Optional metric description
            model: Optional model (not used by Garak detectors, but kept for interface)
            **kwargs: Additional arguments passed to the detector
        """
        self.detector_class_path = detector_class
        self._detector = None
        self._detector_kwargs = kwargs

        # Create metric config
        config = MetricConfig(
            class_name="GarakDetectorMetric",
            backend=Backend.CUSTOM,
            name=name or f"Garak: {detector_class.split('.')[-1]}",
            description=description or f"Garak detector: {detector_class}",
            score_type=ScoreType.CATEGORICAL,
            metric_type=MetricType.CUSTOM_CODE,
            metric_scope=[MetricScope.SINGLE_TURN],
            requires_ground_truth=False,
            requires_context=False,
        )

        super().__init__(config, model)

    @property
    def detector(self):
        """Lazy-load the Garak detector."""
        if self._detector is None:
            self._detector = self._load_detector()
        return self._detector

    def _load_detector(self):
        """
        Dynamically load and instantiate the Garak detector.

        Returns:
            Instantiated Garak detector

        Raises:
            ImportError: If Garak is not installed or detector not found
        """
        try:
            # Normalize the detector path
            # Garak's recommended_detector can be relative (e.g., "perspective.Toxicity")
            # or full (e.g., "garak.detectors.perspective.Toxicity")
            detector_path = self.detector_class_path
            if not detector_path.startswith("garak."):
                detector_path = f"garak.detectors.{detector_path}"

            # Split the class path
            parts = detector_path.rsplit(".", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid detector class path: {detector_path}")

            module_path, class_name = parts

            # Import the module
            module = importlib.import_module(module_path)

            # Get the detector class
            detector_class = getattr(module, class_name)

            # Instantiate the detector
            return detector_class(**self._detector_kwargs)

        except ImportError as e:
            logger.error(f"Failed to import Garak detector module: {e}")
            raise ImportError(
                f"Garak detector '{self.detector_class_path}' not available. "
                "Ensure garak is installed: pip install garak"
            ) from e
        except AttributeError as e:
            logger.error(f"Detector class not found: {e}")
            raise ImportError(
                f"Detector class '{self.detector_class_path}' not found in module"
            ) from e

    def evaluate(
        self,
        input: str = "",
        output: str = "",
        expected_output: str = "",
        context: Optional[List[str]] = None,
        **kwargs,
    ) -> MetricResult:
        """
        Evaluate the model output using the Garak detector.

        Args:
            input: The input prompt (used as the attack prompt)
            output: The model's response to evaluate
            expected_output: Not used by Garak detectors
            context: Not used by Garak detectors
            **kwargs: Additional arguments

        Returns:
            MetricResult with score ("pass" or "fail") and details
        """
        try:
            # Create a Garak Attempt object
            # Garak's Attempt takes no args in __init__, attributes are set after
            from garak.attempt import Attempt

            # Debug: Log evaluation inputs
            logger.debug(f"[GARAK] Evaluating with detector: {self.detector_class_path}")
            logger.debug(f"[GARAK] Input prompt (first 200 chars): {input[:200]}...")
            logger.debug(f"[GARAK] Model output (first 200 chars): {output[:200]}...")

            attempt = Attempt()
            attempt.prompt = input
            attempt.outputs = [output]

            logger.debug("[GARAK] Created Attempt with prompt and 1 output")

            # Run the detector
            logger.debug("[GARAK] Calling detector.detect()...")
            results = self.detector.detect(attempt)
            logger.debug(
                f"[GARAK] Raw detector results: {results} (type: {type(results).__name__})"
            )

            # Garak convention: 0 = safe, 1 = detected (attack succeeded)
            # Rhesis convention: pass = good, fail = bad
            # So we invert: all 0s = pass, any 1 = fail

            if isinstance(results, (list, tuple)):
                attack_succeeded = any(r > 0 for r in results)
                raw_scores = list(results)
                logger.debug(
                    f"[GARAK] Results is list/tuple: {raw_scores}, any > 0 = {attack_succeeded}"
                )
            else:
                attack_succeeded = results > 0
                raw_scores = [results]
                logger.debug(f"[GARAK] Results is scalar: {results}, > 0 = {attack_succeeded}")

            # Determine result
            # Garak: 0 = safe (model defended), 1 = attack succeeded (vulnerability)
            # Rhesis: pass = model defended, fail = vulnerability detected
            if attack_succeeded:
                score = "fail"
                reason = "Garak detector identified potential vulnerability in model response"
                logger.debug(
                    f"[GARAK] FAIL: Attack succeeded (raw_scores={raw_scores}). "
                    "Model response may have a vulnerability."
                )
            else:
                score = "pass"
                reason = "Model response passed Garak security check"
                logger.debug(
                    f"[GARAK] PASS: No attack detected (raw_scores={raw_scores}). "
                    "Model defended against the probe."
                )

            logger.info(
                f"[GARAK] Final result: score={score}, raw_scores={raw_scores}, "
                f"detector={self.detector_class_path.split('.')[-1]}"
            )

            return MetricResult(
                score=score,
                details={
                    "detector": self.detector_class_path,
                    "detector_class": self.detector_class_path.split(".")[-1],
                    "raw_scores": raw_scores,
                    "attack_detected": attack_succeeded,
                    "reason": reason,
                },
            )

        except ImportError as e:
            logger.error(f"[GARAK] Import error - Garak not available: {e}")
            return MetricResult(
                score="fail",
                details={
                    "error": str(e),
                    "detector": self.detector_class_path,
                    "reason": "Garak package not available",
                },
            )
        except Exception as e:
            logger.error(f"[GARAK] Error running detector: {e}", exc_info=True)
            return MetricResult(
                score="fail",
                details={
                    "error": str(e),
                    "detector": self.detector_class_path,
                    "reason": f"Detector evaluation failed: {str(e)}",
                },
            )

    def __repr__(self) -> str:
        return f"GarakDetectorMetric(detector={self.detector_class_path})"
