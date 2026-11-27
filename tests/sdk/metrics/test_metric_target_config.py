"""A metric's target as configuration: kept on the metric, and pushed and pulled with it."""

from unittest.mock import Mock, patch

import pytest

import rhesis.sdk.metrics as metrics
from rhesis.sdk.metrics.base import MetricConfig
from rhesis.sdk.metrics.providers.native import NumericJudge
from rhesis.sdk.metrics.utils import backend_config_to_sdk_config, sdk_config_to_backend_config


def _judge(**kwargs):
    with patch("rhesis.sdk.models.factory.get_model", return_value=Mock()):
        return NumericJudge(
            name="test_metric",
            evaluation_prompt="Test prompt",
            model="gemini",
            **kwargs,
        )


class TestTargetOnConfig:
    def test_metric_scope_is_gone(self):
        assert not hasattr(metrics, "MetricScope")
        with pytest.raises(TypeError):
            MetricConfig(name="m", metric_scope=["Single-Turn"])

    def test_no_target_is_none(self):
        assert MetricConfig(name="m").target is None

    def test_a_kind_becomes_a_target(self):
        assert MetricConfig(name="m", target="conversation").target == {"on": "conversation"}

    def test_refinements_are_kept_and_defaults_dropped(self):
        config = MetricConfig(
            name="m", target={"on": "tool_call", "name": "issue_refund", "aggregate": "all"}
        )
        assert config.target == {"on": "tool_call", "name": "issue_refund"}

    def test_an_unknown_target_is_refused(self):
        with pytest.raises(ValueError):
            MetricConfig(name="m", target="everything")


class TestJudgeTarget:
    def test_a_judge_keeps_its_target(self):
        metric = _judge(target="conversation")

        assert metric.target == {"on": "conversation"}
        assert metric.to_config().target == {"on": "conversation"}

    def test_a_judge_without_one_has_none(self):
        assert _judge().target is None


class TestConversion:
    def test_the_target_is_sent_in_config(self):
        result = sdk_config_to_backend_config({"name": "m", "target": {"on": "turn"}})

        assert result["config"] == {"target": {"on": "turn"}}
        assert "target" not in result

    def test_no_target_sends_no_config(self):
        result = sdk_config_to_backend_config({"name": "m", "target": None})

        assert "config" not in result

    def test_the_target_is_read_from_config(self):
        result = backend_config_to_sdk_config(
            {"name": "m", "config": {"target": {"on": "retrieval"}, "match": "exact"}}
        )

        assert result["target"] == {"on": "retrieval"}
        assert "config" not in result


class TestPushPull:
    @patch("rhesis.sdk.metrics.providers.native.serialization.APIClient")
    def test_push_sends_the_target(self, mock_client_class):
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        _judge(target={"on": "tool_call", "name": "issue_refund"}).push()

        sent = mock_client.send_request.call_args[0][2]
        assert sent["config"] == {"target": {"on": "tool_call", "name": "issue_refund"}}

    @patch("rhesis.sdk.metrics.providers.native.serialization.APIClient")
    def test_push_without_a_target_leaves_it_to_the_server(self, mock_client_class):
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        _judge().push()

        sent = mock_client.send_request.call_args[0][2]
        assert "config" not in sent

    @patch("rhesis.sdk.metrics.providers.native.serialization.APIClient")
    def test_pull_reads_the_target(self, mock_client_class):
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.send_request.return_value = [
            {
                "name": "test_metric",
                "evaluation_prompt": "Test prompt",
                "config": {"target": {"on": "conversation"}},
                "score_type": "numeric",
                "class_name": "NumericJudge",
                "backend_type": "rhesis",
            }
        ]

        with patch("rhesis.sdk.models.factory.get_model", return_value=Mock()):
            metric = NumericJudge.pull(name="test_metric")

        assert metric.target == {"on": "conversation"}

    @patch("rhesis.sdk.metrics.providers.native.serialization.APIClient")
    def test_pull_of_a_newer_target_says_the_sdk_needs_upgrading(self, mock_client_class):
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.send_request.return_value = [
            {
                "name": "test_metric",
                "evaluation_prompt": "Test prompt",
                "config": {"target": {"on": "trajectory"}},
                "score_type": "numeric",
                "class_name": "NumericJudge",
                "backend_type": "rhesis",
            }
        ]

        with patch("rhesis.sdk.models.factory.get_model", return_value=Mock()):
            with pytest.raises(metrics.UnsupportedTarget, match="needs a newer rhesis-sdk"):
                NumericJudge.pull(name="test_metric")


class TestTargetsThisSdkCantRead:
    """A metric made with a newer Rhesis version can carry a target this SDK doesn't know."""

    @pytest.mark.parametrize(
        "target",
        [
            {"on": "trajectory"},
            {"on": "tool_call", "group_by": "ai.agent.name"},
            "trajectory",
        ],
    )
    def test_a_newer_target_says_the_sdk_needs_upgrading(self, target):
        with pytest.raises(metrics.UnsupportedTarget, match="needs a newer rhesis-sdk"):
            MetricConfig(name="m", target=target)

    def test_an_unknown_target_still_lists_the_valid_ones(self):
        with pytest.raises(metrics.UnsupportedTarget, match="valid targets: turn"):
            MetricConfig(name="m", target="tool_calls")
