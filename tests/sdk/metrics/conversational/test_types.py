"""Tests for conversational metric types."""

from rhesis.sdk.metrics.conversational.types import (
    AssistantMessage,
    ConversationHistory,
    SystemMessage,
    ToolMessage,
    UserMessage,
)


def test_user_message_creation():
    """Test creating a user message."""
    msg = UserMessage(content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_assistant_message_creation():
    """Test creating an assistant message."""
    msg = AssistantMessage(content="Hi there")
    assert msg.role == "assistant"
    assert msg.content == "Hi there"
    assert msg.tool_calls is None


def test_assistant_message_with_tool_calls():
    """Test creating an assistant message with tool calls."""
    tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "test"}}]
    msg = AssistantMessage(content=None, tool_calls=tool_calls)
    assert msg.role == "assistant"
    assert msg.content is None
    assert msg.tool_calls == tool_calls


def test_tool_message_creation():
    """Test creating a tool message."""
    msg = ToolMessage(tool_call_id="call_1", name="test_tool", content="Result")
    assert msg.role == "tool"
    assert msg.tool_call_id == "call_1"
    assert msg.name == "test_tool"
    assert msg.content == "Result"


def test_system_message_creation():
    """Test creating a system message."""
    msg = SystemMessage(content="You are a helpful assistant")
    assert msg.role == "system"
    assert msg.content == "You are a helpful assistant"


def test_conversation_history_from_dicts():
    """Test creating conversation from dicts."""
    messages = [
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
    ]
    conv = ConversationHistory.from_messages(messages)
    assert len(conv) == 2
    # Pydantic validates and converts dicts to proper message types
    first_msg = conv.messages[0]
    if isinstance(first_msg, dict):
        assert first_msg["role"] == "user"
    else:
        assert first_msg.role == "user"


def test_conversation_history_from_pydantic():
    """Test creating conversation from Pydantic models."""
    messages = [
        UserMessage(content="What is 2+2?"),
        AssistantMessage(content="4"),
    ]
    conv = ConversationHistory.from_messages(messages)
    assert len(conv) == 2
    assert conv.messages[0].role == "user"
    assert conv.messages[1].role == "assistant"


def test_conversation_history_mixed():
    """Test mixed dict and Pydantic messages."""
    messages = [
        UserMessage(content="Hello"),
        {"role": "assistant", "content": "Hi"},
    ]
    conv = ConversationHistory.from_messages(messages)
    assert len(conv) == 2


def test_get_simple_turns():
    """Test extracting simple role/content pairs."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi", "tool_calls": [{"id": "call_1"}]},
    ]
    conv = ConversationHistory.from_messages(messages)
    simple = conv.get_simple_turns()

    assert len(simple) == 2
    assert simple[0] == {"role": "user", "content": "Hello"}
    assert simple[1] == {"role": "assistant", "content": "Hi"}


def test_get_simple_turns_skips_empty_content():
    """Test that simple turns skips messages without content."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1"}]},
        {"role": "user", "content": "Are you there?"},
    ]
    conv = ConversationHistory.from_messages(messages)
    simple = conv.get_simple_turns()

    # Should skip the empty assistant message
    assert len(simple) == 2
    assert simple[0] == {"role": "user", "content": "Hello"}
    assert simple[1] == {"role": "user", "content": "Are you there?"}


def test_conversation_with_metadata():
    """Test conversation with metadata."""
    messages = [{"role": "user", "content": "Test"}]
    conv = ConversationHistory.from_messages(
        messages,
        conversation_id="test-123",
        metadata={"goal": "Test goal", "source": "test"},
    )

    assert conv.conversation_id == "test-123"
    assert conv.metadata["goal"] == "Test goal"
    assert conv.metadata["source"] == "test"


def test_to_dict_list():
    """Test converting all messages to dict format."""
    messages = [
        UserMessage(content="Hello"),
        {"role": "assistant", "content": "Hi"},
    ]
    conv = ConversationHistory.from_messages(messages)
    dict_list = conv.to_dict_list()

    assert len(dict_list) == 2
    assert all(isinstance(msg, dict) for msg in dict_list)
    assert dict_list[0]["role"] == "user"
    assert dict_list[0]["content"] == "Hello"


def test_conversation_history_length():
    """Test __len__ method."""
    messages = [
        {"role": "user", "content": "Message 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Message 2"},
    ]
    conv = ConversationHistory.from_messages(messages)
    assert len(conv) == 3


def test_message_extra_fields_allowed():
    """Test that extra fields are allowed in messages."""
    # This tests the extra="allow" config
    msg_dict = {
        "role": "assistant",
        "content": "Hello",
        "custom_field": "custom_value",
        "another_field": 123,
    }
    msg = AssistantMessage(**msg_dict)
    assert msg.role == "assistant"
    assert msg.content == "Hello"
    # Extra fields should be preserved
    assert hasattr(msg, "custom_field") or "custom_field" in msg.model_dump()
