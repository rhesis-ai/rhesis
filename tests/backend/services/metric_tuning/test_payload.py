"""Unit tests for the tuning case payload.

The payload is what a tuning case shows its metric — input, output and the
case's own expected response, stored together in ``prompt.content``.

Parsing has to be total: content that will not parse still has to render as
something a human can repair, because the alternative is a case that vanishes
from the tab or takes the whole list down with it. No higher seam can reach
this, since the API cannot write unparseable content.

Run with: python -m pytest tests/backend/services/metric_tuning/test_payload.py -v
"""

import json

import pytest

from rhesis.backend.app.services.metric_tuning.payload import (
    CasePayload,
    parse_payload,
    serialize_payload,
)


@pytest.mark.unit
class TestRoundTrip:
    def test_every_field_survives(self):
        payload = CasePayload(
            input="How are you?",
            output="I am fine you fucking basterd",
            expected_output="I am fine, thanks for asking.",
        )

        assert parse_payload(serialize_payload(payload)) == payload

    def test_absent_expected_output_stays_absent(self):
        """Plenty of metrics judge an answer without a reference to compare to."""
        payload = CasePayload(input="Hi", output="Hello")

        serialized = serialize_payload(payload)

        assert "expected_output" not in json.loads(serialized)
        assert parse_payload(serialized).expected_output is None

    def test_empty_expected_output_is_kept(self):
        """"Present but empty" is a different statement from "absent"."""
        serialized = serialize_payload(CasePayload(input="Hi", output="Hello", expected_output=""))

        assert parse_payload(serialized).expected_output == ""


@pytest.mark.unit
class TestParseIsTotal:
    def test_none_and_empty_give_defaults(self):
        assert parse_payload(None) == CasePayload()
        assert parse_payload("") == CasePayload()

    def test_content_that_is_not_json_becomes_the_input(self):
        """A case written before the payload existed held the bare input in
        content. It has to keep rendering, with the text where a human can see
        and fix it."""
        parsed = parse_payload("How are you?")

        assert parsed.input == "How are you?"
        assert parsed.output == ""

    def test_json_that_is_not_an_object_becomes_the_input(self):
        parsed = parse_payload("[1, 2, 3]")

        assert parsed.input == "[1, 2, 3]"

    def test_unknown_keys_round_trip(self):
        """The payload may gain fields; an older reader must not drop them."""
        parsed = parse_payload('{"input": "Hi", "output": "Hello", "context": ["a"]}')

        assert parsed.input == "Hi"
        assert serialize_payload(parsed).count("context") == 1

    def test_garbage_shaped_values_do_not_raise(self):
        parsed = parse_payload('{"input": {"nested": true}, "output": 12345}')

        assert isinstance(parsed, CasePayload)


@pytest.mark.unit
class TestTheVerdictIsNeverInThePayload:
    def test_serialized_payload_has_no_verdict_field(self):
        """The verdict is the answer key. It lives on prompt.expected_response
        precisely so the metric is never shown it."""
        serialized = serialize_payload(CasePayload(input="Hi", output="Hello"))

        assert "expected" not in json.loads(serialized)
