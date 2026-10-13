"""Tests for the toxicity detector that replaces garak's Perspective detector."""

from unittest.mock import MagicMock, patch

import pytest
import requests

pytest.importorskip("garak")

from garak.attempt import Attempt, Message

from rhesis.sdk.metrics.base import UnsupportedModelType
from rhesis.sdk.metrics.providers.garak import GarakDetectorMetric
from rhesis.sdk.metrics.providers.garak.detector_metric import (
    ToxicityBackendUnavailable,
)
from rhesis.sdk.metrics.providers.garak.moderation import (
    DEFAULT_ENDPOINT,
    GOOGLE_BACKEND,
    JUDGE_BACKEND,
    Toxicity,
    toxic_confidence,
)
from rhesis.sdk.models.base import BaseDecisionModel, BaseLLM

_REQUESTS_POST = "rhesis.sdk.metrics.providers.garak.moderation.requests.post"
_SLEEP = "rhesis.sdk.metrics.providers.garak.moderation.time.sleep"


def _attempt(*outputs):
    attempt = Attempt()
    attempt.prompt = Message(text="prompt", lang="*")
    attempt.outputs = list(outputs)
    return attempt


def _response(status_code=200, toxic=0.3):
    response = MagicMock(status_code=status_code)
    response.json.return_value = {
        "moderationCategories": [
            {"name": "Insult", "confidence": 0.9},
            {"name": "Toxic", "confidence": toxic},
        ]
    }
    return response


def _error_response(status_code):
    response = MagicMock(status_code=status_code)
    response.raise_for_status.side_effect = requests.HTTPError(f"{status_code}")
    return response


def _judge(score=0.7):
    judge = MagicMock(spec=BaseLLM)
    judge.generate.return_value = {"score": score, "reason": "rude"}
    return judge


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_MODERATION_API_KEY", "test-key")
    monkeypatch.delenv("GOOGLE_MODERATION_ENDPOINT", raising=False)


@pytest.fixture
def without_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MODERATION_API_KEY", raising=False)


class TestGoogleModeration:
    def test_scores_with_toxic_confidence(self, with_key):
        judge = _judge()
        with patch(_REQUESTS_POST, return_value=_response(toxic=0.42)) as post:
            scores = Toxicity(judge=judge).detect(_attempt("you are awful"))

        assert scores == [0.42]
        url = post.call_args.args[0]
        assert url == f"https://{DEFAULT_ENDPOINT}/v2/documents:moderateText"
        assert post.call_args.kwargs["headers"] == {"x-goog-api-key": "test-key"}
        assert post.call_args.kwargs["json"]["document"]["content"] == "you are awful"
        judge.generate.assert_not_called()

    def test_endpoint_is_configurable(self, with_key, monkeypatch):
        monkeypatch.setenv("GOOGLE_MODERATION_ENDPOINT", "us-language.googleapis.com")
        with patch(_REQUESTS_POST, return_value=_response()) as post:
            Toxicity().detect(_attempt("text"))

        assert post.call_args.args[0].startswith("https://us-language.googleapis.com/")

    def test_empty_and_missing_outputs_skip_the_call(self, with_key):
        with patch(_REQUESTS_POST) as post:
            scores = Toxicity().detect(_attempt("  ", None))

        assert scores == [0.0, None]
        post.assert_not_called()

    def test_retries_rate_limits(self, with_key):
        responses = [_response(status_code=429), _response(toxic=0.1)]
        with patch(_REQUESTS_POST, side_effect=responses) as post, patch(_SLEEP):
            scores = Toxicity().detect(_attempt("text"))

        assert scores == [0.1]
        assert post.call_count == 2

    def test_retries_connection_errors(self, with_key):
        responses = [requests.ConnectionError("reset"), _response(toxic=0.2)]
        with patch(_REQUESTS_POST, side_effect=responses) as post, patch(_SLEEP):
            scores = Toxicity().detect(_attempt("text"))

        assert scores == [0.2]
        assert post.call_count == 2

    def test_missing_toxic_category_raises(self):
        with pytest.raises(ValueError, match="Toxic"):
            toxic_confidence({"moderationCategories": [{"name": "Insult", "confidence": 1}]})


class TestJudgeFallback:
    def test_scores_with_judge_without_key(self, without_key):
        judge = _judge(score=0.8)
        with patch(_REQUESTS_POST) as post:
            detector = Toxicity(judge=judge)
            scores = detector.detect(_attempt("you idiot"))

        assert scores == [0.8]
        assert detector.scoring_backend == JUDGE_BACKEND
        assert "you idiot" in judge.generate.call_args.args[0]
        post.assert_not_called()

    def test_judge_error_response_raises(self, without_key):
        judge = MagicMock(spec=BaseLLM)
        judge.generate.return_value = {"error": "upstream failed"}

        with pytest.raises(RuntimeError, match="upstream failed"):
            Toxicity(judge=judge).detect(_attempt("text"))

    def test_no_key_and_no_judge_is_unavailable(self, without_key):
        with pytest.raises(ToxicityBackendUnavailable):
            Toxicity().detect(_attempt("text"))


class TestMetricIntegration:
    def test_perspective_path_scores_with_google(self, with_key):
        metric = GarakDetectorMetric(
            detector_class="garak.detectors.perspective.Toxicity", model=_judge()
        )
        with patch(_REQUESTS_POST, return_value=_response(toxic=0.9)):
            result = metric.evaluate(input="hi", output="you are awful")

        assert result.score == 0.9
        assert result.details["is_successful"] is False
        assert result.details["scoring_backend"] == GOOGLE_BACKEND

    def test_metric_passes_its_model_as_judge(self, without_key):
        metric = GarakDetectorMetric(
            detector_class="garak.detectors.unsafe_content.ToxicCommentModel",
            model=_judge(score=0.1),
        )
        result = metric.evaluate(input="hi", output="have a nice day")

        assert result.score == 0.1
        assert result.details["is_successful"] is True
        assert result.details["scoring_backend"] == JUDGE_BACKEND

    def test_decision_model_without_key_is_refused(self, without_key):
        with pytest.raises(UnsupportedModelType):
            GarakDetectorMetric(
                detector_class="garak.detectors.perspective.Toxicity",
                model=MagicMock(spec=BaseDecisionModel),
            )

    def test_decision_model_with_key_is_accepted(self, with_key):
        metric = GarakDetectorMetric(
            detector_class="garak.detectors.perspective.Toxicity",
            model=MagicMock(spec=BaseDecisionModel),
        )
        with patch(_REQUESTS_POST, return_value=_response(toxic=0.1)):
            assert metric.evaluate(input="hi", output="text").score == 0.1

    def test_model_that_cannot_judge_is_inconclusive(self, without_key):
        metric = GarakDetectorMetric(
            detector_class="garak.detectors.perspective.Toxicity", model=object()
        )
        result = metric.evaluate(input="hi", output="text")

        assert result.score is None
        assert result.details["inconclusive"] is True
        assert result.details["not_implemented"] is False

    def test_scoring_errors_raise_instead_of_failing_the_test(self, with_key):
        metric = GarakDetectorMetric(
            detector_class="garak.detectors.perspective.Toxicity", model=_judge()
        )
        with patch(_REQUESTS_POST, return_value=_error_response(400)), patch(_SLEEP):
            with pytest.raises(requests.HTTPError):
                metric.evaluate(input="hi", output="text")
