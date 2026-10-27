"""Tool spans record their arguments by name, so a trace's tool calls carry them."""

import json
from unittest.mock import MagicMock, patch

import pytest
from rhesis.telemetry.attributes import AIAttributes

from rhesis.sdk.entities.trace import Span


@pytest.fixture
def tracer():
    from rhesis.sdk.telemetry.tracer import Tracer

    with patch("rhesis.sdk.telemetry.tracer.get_tracer_provider"):
        return Tracer(api_key="key", project_id="project", environment="test", base_url="http://x")


def recorded(tracer, func, args, kwargs, operation=AIAttributes.OPERATION_TOOL_INVOKE):
    span = MagicMock()
    tracer._setup_span_attributes(
        span, func.__name__, args, kwargs, {AIAttributes.OPERATION_TYPE: operation}, func=func
    )
    return {c.args[0]: c.args[1] for c in span.set_attribute.call_args_list}


def test_positional_arguments_are_named(tracer):
    def lookup_order(order, *, verbose=False, **extra):
        return None

    attributes = recorded(tracer, lookup_order, (7,), {"region": "eu"})

    assert attributes["ai.tool.arguments"] == '{"order": 7, "region": "eu"}'


def test_a_methods_self_is_left_out(tracer):
    class Tools:
        def refund(self, order):
            return None

    tools = Tools()
    attributes = recorded(tracer, Tools.refund, (tools, 7), {})

    assert attributes["ai.tool.arguments"] == '{"order": 7}'


def test_other_spans_record_none(tracer):
    def plan(task):
        return None

    attributes = recorded(tracer, plan, ("task",), {}, AIAttributes.OPERATION_LLM_INVOKE)

    assert "ai.tool.arguments" not in attributes


def test_arguments_too_long_to_keep_whole_are_left_out(tracer):
    def search(query):
        return None

    attributes = recorded(tracer, search, ("x" * 5000,), {})

    assert "ai.tool.arguments" not in attributes


def test_the_span_reads_them_as_its_input():
    span = Span.model_validate(
        {
            "span_id": "s",
            "trace_id": "t",
            "span_name": "ai.tool.invoke",
            "attributes": {
                "ai.operation.type": "tool.invoke",
                "ai.tool.arguments": '{"order": 7}',
                "function.args": "[7]",
            },
        }
    )

    assert json.loads(span.input) == {"order": 7}
