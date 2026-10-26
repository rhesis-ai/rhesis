"""SDK metrics get the trace only when the function behind them declares it."""

import json

import pytest

from rhesis.backend.metrics.inputs import EvaluationInputs, ResponseTrace
from rhesis.backend.metrics.strategies.connector import ConnectorStrategy
from rhesis.sdk.entities.trace import Trace
from rhesis.sdk.metrics import Expectations, MetricConfig

TRACE_ID = "a" * 32


def _config(name, accepted_params):
    connection = {"sdk_connection": {"metric_name": name, "accepted_params": accepted_params}}
    return MetricConfig(
        class_name=name,
        backend="sdk",
        name=name,
        evaluation_examples=json.dumps(connection),
    )


def _inputs(loader, expectations=None):
    return EvaluationInputs(
        trace=ResponseTrace(input="Book a room", output="Booked.", loader=loader),
        expectations=expectations,
    )


class _Sender:
    def __init__(self):
        self.sent = {}

    async def __call__(self, metric_run_id, metric_name, inputs):
        self.sent[metric_name] = inputs
        return {"status": "success", "score": 1.0, "details": {}}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_metric_declaring_trace_receives_it_as_json():
    sender = _Sender()
    trace = Trace(trace_id=TRACE_ID, root_spans=[{"span_id": "b" * 16, "span_name": "x"}])

    await ConnectorStrategy(connector_metric_sender=sender).a_evaluate(
        [_config("tool_budget", ["input", "output", "trace"])], _inputs(lambda: trace)
    )

    sent = sender.sent["tool_budget"]["trace"]
    assert sent["trace_id"] == TRACE_ID
    assert Trace.model_validate(sent).spans()[0].span_name == "x"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_metric_without_it_gets_no_trace_and_none_is_read():
    sender = _Sender()

    def loader():
        raise AssertionError("read a trace no metric asked for")

    await ConnectorStrategy(connector_metric_sender=sender).a_evaluate(
        [_config("exact_match", ["input", "output"])], _inputs(loader)
    )

    assert "trace" not in sender.sent["exact_match"]


@pytest.mark.unit
def test_the_sync_path_sends_it_too():
    sender = _Sender()
    trace = Trace(trace_id=TRACE_ID, root_spans=[{"span_id": "b" * 16, "span_name": "x"}])

    ConnectorStrategy(connector_metric_sender=sender).evaluate(
        [_config("tool_budget", ["input", "output", "trace"])], _inputs(lambda: trace)
    )

    assert sender.sent["tool_budget"]["trace"]["trace_id"] == TRACE_ID


@pytest.mark.unit
def test_with_nothing_stored_the_trace_is_built_from_the_response():
    sender = _Sender()

    ConnectorStrategy(connector_metric_sender=sender).evaluate(
        [_config("tool_budget", ["input", "output", "trace"])], _inputs(lambda: None)
    )

    trace = Trace.model_validate(sender.sent["tool_budget"]["trace"])
    assert (trace.input, trace.output) == ("Book a room", "Booked.")


@pytest.mark.unit
def test_the_payload_carries_expectations_and_no_old_fields():
    sender = _Sender()

    ConnectorStrategy(connector_metric_sender=sender).evaluate(
        [_config("exact_match", ["output", "expectations"])],
        _inputs(lambda: None, Expectations(response="Booked.")),
    )

    sent = sender.sent["exact_match"]
    assert sent["expectations"] == {"response": "Booked."}
    assert (sent["input"], sent["output"]) == ("Book a room", "Booked.")
    assert not {"expected_output", "context"} & set(sent)


@pytest.mark.unit
def test_production_sends_no_expectations():
    sender = _Sender()

    ConnectorStrategy(connector_metric_sender=sender).evaluate(
        [_config("exact_match", ["output", "expectations"])], _inputs(lambda: None)
    )

    assert sender.sent["exact_match"]["expectations"] is None
