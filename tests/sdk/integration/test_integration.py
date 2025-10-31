import os

import pytest

from rhesis.sdk.client import Client, Endpoints, Methods
from rhesis.sdk.metrics import NumericJudge

os.environ["RHESIS_API_KEY"] = "rh-test-token"
os.environ["RHESIS_BASE_URL"] = "http://localhost:8080"


def test_integration_client_works():
    client = Client()
    response = client.send_request(endpoint=Endpoints.HEALTH, method=Methods.GET)
    assert response["status"] == "ok"


def test_push_metric():
    judge = NumericJudge(name="numeric-judge", evaluation_prompt="test-evaluation-prompt")
    judge.push()


def test_push__pullmetric():
    judge = NumericJudge(name="numeric-judge", evaluation_prompt="test-evaluation-prompt")
    judge.push()

    judge = NumericJudge.pull(name="numeric-judge")

    with pytest.raises(ValueError):
        judge.pull(name="non-existent-name")
