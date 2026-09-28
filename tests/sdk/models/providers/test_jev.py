import os
from unittest.mock import Mock, patch

import pytest
import requests

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import get_model
from rhesis.sdk.models.providers.jev import DEFAULT_API_BASE, JevDecisionModel

ANSWERS = {"score": {"type": "choice", "choice": "pass", "probabilities": {"pass": 0.9}}}


def _response(body, status=200):
    response = Mock(status_code=status)
    response.json.return_value = body
    if status >= 400:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=response)
    return response


class TestJevDecisionModel:
    def test_defaults(self):
        llm = JevDecisionModel(api_key="key")
        assert llm.model_name == "jev-latest"
        assert llm.api_base == DEFAULT_API_BASE
        assert llm.MODEL_TYPE == "decision"
        assert not isinstance(llm, BaseLLM)

    def test_reads_env(self):
        env = {"TYPESAFE_API_KEY": "env-key", "TYPESAFE_API_BASE": "https://proxy/typesafe/"}
        with patch.dict(os.environ, env, clear=True):
            llm = JevDecisionModel()
        assert llm.api_key == "env-key"
        assert llm.api_base == "https://proxy/typesafe"

    def test_missing_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="TYPESAFE_API_KEY is not set"):
                JevDecisionModel()

    @pytest.mark.parametrize("model_type", [None, "decision"])
    def test_factory_builds_jev_as_a_decision_model(self, model_type):
        llm = get_model(
            "jev",
            "jev-1.13.0",
            api_key="key",
            model_type=model_type,
            api_base="https://proxy/typesafe",
        )
        assert isinstance(llm, JevDecisionModel)
        assert llm.model_name == "jev-1.13.0"
        assert llm.api_base == "https://proxy/typesafe"

    @patch("rhesis.sdk.models.providers.jev.requests.post")
    def test_decide_posts_questions_and_reports_usage(self, mock_post):
        mock_post.return_value = _response(
            {"answers": ANSWERS, "usage": {"input_tokens": 10, "output_tokens": 2}}
        )
        usages = []
        llm = JevDecisionModel(api_key="key", on_usage=usages.append)
        question = {"type": "choice", "instructions": "i", "criteria": {"pass": "pass"}}

        answers = llm.decide({"output": "hi"}, {"score": question})

        assert answers == ANSWERS
        url = mock_post.call_args.args[0]
        assert url == "https://api.typesafe.ai/v1/systemone"
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer key"
        assert mock_post.call_args.kwargs["json"] == {
            "model": "jev-latest",
            "state": {"output": "hi"},
            "questions": {"score": question},
        }
        assert usages == [{"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}]

    @patch("rhesis.sdk.models.providers.jev.requests.post")
    def test_decide_does_not_retry_client_errors(self, mock_post):
        mock_post.return_value = _response({}, status=400)
        llm = JevDecisionModel(api_key="key")
        with pytest.raises(requests.exceptions.HTTPError):
            llm.decide("state", {})
        assert mock_post.call_count == 1

    def test_factory_default_model(self):
        assert get_model("jev", api_key="key").model_name == "jev-latest"

    def test_factory_refuses_jev_as_a_language_model(self):
        with pytest.raises(ValueError, match="does not support model type 'language'"):
            get_model("jev", "jev-latest", api_key="key", model_type="language")

    def test_has_no_text_generation(self):
        assert not hasattr(JevDecisionModel(api_key="key"), "generate")

    @patch("rhesis.sdk.models.providers.jev.requests.post")
    def test_generate_batch_asks_about_each_state(self, mock_post):
        mock_post.return_value = _response({"answers": ANSWERS})
        results = JevDecisionModel(api_key="key").generate_batch(["a", "b"], {"score": {}})
        assert results == [ANSWERS, ANSWERS]
        assert [c.kwargs["json"]["state"] for c in mock_post.call_args_list] == ["a", "b"]
