"""Tests for _generate_conversation_summary — context and metadata extraction.

Covers the separation of `context` and `metadata` on ConversationTurn, ensuring
that values are drawn from the correct keys in the endpoint's response envelope
and stored as independent fields.
"""

import json

import pytest

from rhesis.penelope.context import (
    RESPONSE_METADATA_CONTEXT_KEY,
    RESPONSE_METADATA_ENDPOINT_METADATA_KEY,
    TOOL_METADATA_KEY,
    TOOL_OUTPUT_KEY,
    TOOL_RESPONSE_KEY,
    TOOL_SUCCESS_KEY,
    ConversationTurn,
    TestContext,
    TestState,
    ToolExecution,
    Turn,
)
from rhesis.penelope.schemas import (
    AssistantMessage as PenelopeAssistantMessage,
)
from rhesis.penelope.schemas import (
    FunctionCall,
    MessageToolCall,
    ToolMessage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool_result(
    response: str,
    context: list | None = None,
    endpoint_metadata: dict | None = None,
    success: bool = True,
) -> str:
    """Build the JSON string that Penelope stores in ToolMessage.content."""
    envelope: dict = {}
    if context is not None:
        envelope[RESPONSE_METADATA_CONTEXT_KEY] = context
    if endpoint_metadata is not None:
        envelope[RESPONSE_METADATA_ENDPOINT_METADATA_KEY] = endpoint_metadata

    output: dict = {TOOL_RESPONSE_KEY: response}
    if envelope:
        output[TOOL_METADATA_KEY] = envelope

    return json.dumps({TOOL_SUCCESS_KEY: success, TOOL_OUTPUT_KEY: output})


def _add_turn(
    state: TestState,
    message: str,
    response: str,
    context: list | None = None,
    endpoint_metadata: dict | None = None,
    turn_number: int | None = None,
) -> None:
    """Append a target-interaction turn to *state*."""
    if turn_number is None:
        turn_number = len(state.turns) + 1

    tool_result = _make_tool_result(response, context=context, endpoint_metadata=endpoint_metadata)

    assistant_msg = PenelopeAssistantMessage(
        content="Penelope reasoning",
        tool_calls=[
            MessageToolCall(
                id=f"call_{turn_number}",
                type="function",
                function=FunctionCall(
                    name="send_message_to_target",
                    arguments=json.dumps({"message": message}),
                ),
            )
        ],
    )
    tool_msg = ToolMessage(
        tool_call_id=f"call_{turn_number}",
        name="send_message_to_target",
        content=tool_result,
    )
    execution = ToolExecution(
        tool_name="send_message_to_target",
        reasoning="reasoning",
        assistant_message=assistant_msg,
        tool_message=tool_msg,
    )
    turn = Turn(
        turn_number=turn_number,
        executions=[execution],
        target_interaction=execution,
    )
    state.turns.append(turn)


@pytest.fixture()
def base_state() -> TestState:
    ctx = TestContext(
        target_id="tgt",
        target_type="endpoint",
        instructions="test",
        goal="test goal",
    )
    return TestState(context=ctx)


# ---------------------------------------------------------------------------
# ConversationTurn model field tests
# ---------------------------------------------------------------------------


def test_conversation_turn_context_defaults_to_none():
    """ConversationTurn.context is None when not provided."""
    turn = ConversationTurn(
        turn=1,
        timestamp="2024-01-01T00:00:00",
        penelope_reasoning="ok",
        penelope_message="Hello",
        target_response="Hi",
        success=True,
    )
    assert turn.context is None


def test_conversation_turn_metadata_defaults_to_none():
    """ConversationTurn.metadata is None when not provided."""
    turn = ConversationTurn(
        turn=1,
        timestamp="2024-01-01T00:00:00",
        penelope_reasoning="ok",
        penelope_message="Hello",
        target_response="Hi",
        success=True,
    )
    assert turn.metadata is None


def test_conversation_turn_context_and_metadata_are_independent():
    """context and metadata can be set independently."""
    turn = ConversationTurn(
        turn=1,
        timestamp="2024-01-01T00:00:00",
        penelope_reasoning="ok",
        penelope_message="Hello",
        target_response="Hi",
        success=True,
        context=["chunk 1", "chunk 2"],
        metadata={"confidence": 0.9},
    )
    assert turn.context == ["chunk 1", "chunk 2"]
    assert turn.metadata == {"confidence": 0.9}


def test_conversation_turn_context_only():
    """context can be set without metadata."""
    turn = ConversationTurn(
        turn=1,
        timestamp="2024-01-01T00:00:00",
        penelope_reasoning="ok",
        penelope_message="Q",
        target_response="A",
        success=True,
        context=["source"],
    )
    assert turn.context == ["source"]
    assert turn.metadata is None


def test_conversation_turn_metadata_only():
    """metadata can be set without context."""
    turn = ConversationTurn(
        turn=1,
        timestamp="2024-01-01T00:00:00",
        penelope_reasoning="ok",
        penelope_message="Q",
        target_response="A",
        success=True,
        metadata={"score": 0.8},
    )
    assert turn.context is None
    assert turn.metadata == {"score": 0.8}


# ---------------------------------------------------------------------------
# _generate_conversation_summary — context extraction
# ---------------------------------------------------------------------------


def test_summary_context_populated_from_envelope(base_state):
    """context on ConversationTurn is drawn from the envelope's 'context' key."""
    _add_turn(
        base_state,
        message="What is RAG?",
        response="RAG retrieves documents.",
        context=["doc paragraph 1", "doc paragraph 2"],
    )
    summary = base_state._generate_conversation_summary()
    assert len(summary) == 1
    turn = summary[0]
    assert turn.context == ["doc paragraph 1", "doc paragraph 2"]


def test_summary_context_none_when_absent(base_state):
    """context is None when the envelope contains no 'context' key."""
    _add_turn(base_state, message="Hello", response="Hi")
    summary = base_state._generate_conversation_summary()
    assert summary[0].context is None


def test_summary_metadata_populated_from_envelope(base_state):
    """metadata on ConversationTurn is drawn from the envelope's 'endpoint_metadata' key."""
    _add_turn(
        base_state,
        message="What is the policy?",
        response="Policy details...",
        endpoint_metadata={"confidence": 0.95, "model": "gpt-4"},
    )
    summary = base_state._generate_conversation_summary()
    assert summary[0].metadata == {"confidence": 0.95, "model": "gpt-4"}


def test_summary_metadata_none_when_absent(base_state):
    """metadata is None when the envelope contains no 'endpoint_metadata' key."""
    _add_turn(base_state, message="Hello", response="Hi")
    summary = base_state._generate_conversation_summary()
    assert summary[0].metadata is None


def test_summary_context_and_metadata_stored_separately(base_state):
    """context and metadata are populated as separate, independent fields."""
    _add_turn(
        base_state,
        message="Tell me about policy X",
        response="Policy X covers...",
        context=["policy doc excerpt"],
        endpoint_metadata={"confidence": 0.9},
    )
    summary = base_state._generate_conversation_summary()
    assert len(summary) == 1
    turn = summary[0]
    assert turn.context == ["policy doc excerpt"]
    assert turn.metadata == {"confidence": 0.9}


def test_summary_context_not_nested_inside_metadata(base_state):
    """context is a top-level field on ConversationTurn, not nested inside metadata."""
    _add_turn(
        base_state,
        message="Q",
        response="A",
        context=["chunk"],
        endpoint_metadata={"k": "v"},
    )
    summary = base_state._generate_conversation_summary()
    turn = summary[0]
    # context must NOT appear inside metadata
    if turn.metadata:
        assert "context" not in turn.metadata
    # and vice-versa
    assert turn.context is not None


def test_summary_raw_envelope_fields_excluded(base_state):
    """Internal envelope fields (raw_response, message_sent) are not surfaced."""
    # Manually craft a tool result with internal fields in the envelope
    envelope = {
        RESPONSE_METADATA_CONTEXT_KEY: ["rag source"],
        RESPONSE_METADATA_ENDPOINT_METADATA_KEY: {"score": 1},
        "raw_response": "debug payload",
        "message_sent": "internal message",
    }
    output = {TOOL_RESPONSE_KEY: "The answer", TOOL_METADATA_KEY: envelope}
    tool_result = json.dumps({TOOL_SUCCESS_KEY: True, TOOL_OUTPUT_KEY: output})

    assistant_msg = PenelopeAssistantMessage(
        content="reasoning",
        tool_calls=[
            MessageToolCall(
                id="call_x",
                type="function",
                function=FunctionCall(
                    name="send_message_to_target",
                    arguments=json.dumps({"message": "Q"}),
                ),
            )
        ],
    )
    tool_msg = ToolMessage(
        tool_call_id="call_x",
        name="send_message_to_target",
        content=tool_result,
    )
    execution = ToolExecution(
        tool_name="send_message_to_target",
        reasoning="r",
        assistant_message=assistant_msg,
        tool_message=tool_msg,
    )
    turn = Turn(turn_number=1, executions=[execution], target_interaction=execution)
    base_state.turns.append(turn)

    summary = base_state._generate_conversation_summary()
    ct = summary[0]
    assert ct.context == ["rag source"]
    assert ct.metadata == {"score": 1}
    # raw_response and message_sent must NOT appear in either field
    assert ct.metadata is None or "raw_response" not in ct.metadata
    assert ct.metadata is None or "message_sent" not in ct.metadata


def test_summary_multiple_turns_context_per_turn(base_state):
    """Each turn's context is stored independently; missing context is None."""
    _add_turn(base_state, "Q1", "A1", context=["src1"])
    _add_turn(base_state, "Q2", "A2")  # no context
    _add_turn(base_state, "Q3", "A3", context=["src3a", "src3b"])

    summary = base_state._generate_conversation_summary()
    assert len(summary) == 3
    assert summary[0].context == ["src1"]
    assert summary[1].context is None
    assert summary[2].context == ["src3a", "src3b"]


def test_summary_multiple_turns_metadata_per_turn(base_state):
    """Each turn's metadata is stored independently; missing metadata is None."""
    _add_turn(base_state, "Q1", "A1", endpoint_metadata={"m": 1})
    _add_turn(base_state, "Q2", "A2")  # no metadata
    _add_turn(base_state, "Q3", "A3", endpoint_metadata={"m": 3})

    summary = base_state._generate_conversation_summary()
    assert summary[0].metadata == {"m": 1}
    assert summary[1].metadata is None
    assert summary[2].metadata == {"m": 3}
