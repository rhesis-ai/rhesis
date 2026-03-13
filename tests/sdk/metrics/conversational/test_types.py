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


# ============================================================================
# AssistantMessage.metadata tests
# ============================================================================


def test_assistant_message_metadata_field():
    """AssistantMessage accepts and stores metadata; defaults to None."""
    msg_with = AssistantMessage(content="Hi", metadata={"citations": ["doc1"]})
    assert msg_with.metadata == {"citations": ["doc1"]}

    msg_without = AssistantMessage(content="Hi")
    assert msg_without.metadata is None


def test_assistant_message_metadata_from_dict():
    """Dict with 'metadata' key is coerced into AssistantMessage.metadata."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi", "metadata": {"source": "doc1"}},
    ]
    conv = ConversationHistory.from_messages(messages)
    asst_msg = conv.messages[1]
    # Works whether Pydantic coerced to typed model or kept as dict
    if isinstance(asst_msg, dict):
        assert asst_msg.get("metadata") == {"source": "doc1"}
    else:
        assert asst_msg.metadata == {"source": "doc1"}


# ============================================================================
# get_assistant_metadata() tests
# ============================================================================


def test_get_assistant_metadata_empty_conversation():
    """Returns empty list for a conversation with no messages."""
    conv = ConversationHistory.from_messages([])
    assert conv.get_assistant_metadata() == []


def test_get_assistant_metadata_no_metadata():
    """Returns all-None when no assistant message carries metadata."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "Fine"},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.get_assistant_metadata()
    assert result == [None, None]


def test_get_assistant_metadata_all_metadata():
    """Returns correct metadata for every turn when all assistant messages carry it."""
    messages = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1", "metadata": {"source": "doc1"}},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2", "metadata": {"source": "doc2"}},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.get_assistant_metadata()
    assert result == [{"source": "doc1"}, {"source": "doc2"}]


def test_get_assistant_metadata_partial_metadata():
    """Returns None for turns without metadata and dict for turns that have it."""
    messages = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},  # no metadata
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2", "metadata": {"citations": ["x"]}},
        {"role": "user", "content": "Q3"},
        {"role": "assistant", "content": "A3"},  # no metadata
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.get_assistant_metadata()
    assert result == [None, {"citations": ["x"]}, None]
    # Indices align with get_simple_turns() turn pairs
    simple = conv.get_simple_turns()
    assert len([m for m in simple if m["role"] == "user"]) == len(result)


# ============================================================================
# AssistantMessage.context tests
# ============================================================================


def test_assistant_message_context_field():
    """AssistantMessage accepts and stores context; defaults to None."""
    msg_with = AssistantMessage(content="Hi", context=["doc1 text", "doc2 text"])
    assert msg_with.context == ["doc1 text", "doc2 text"]

    msg_without = AssistantMessage(content="Hi")
    assert msg_without.context is None


def test_assistant_message_context_from_dict():
    """Dict with 'context' key is stored as AssistantMessage.context."""
    messages = [
        {"role": "user", "content": "What is insurance?"},
        {"role": "assistant", "content": "Insurance is...", "context": ["source A", "source B"]},
    ]
    conv = ConversationHistory.from_messages(messages)
    asst_msg = conv.messages[1]
    if isinstance(asst_msg, dict):
        assert asst_msg.get("context") == ["source A", "source B"]
    else:
        assert asst_msg.context == ["source A", "source B"]


def test_assistant_message_context_and_metadata_independent():
    """context and metadata are stored independently on AssistantMessage."""
    msg = AssistantMessage(
        content="Answer",
        context=["retrieved chunk"],
        metadata={"confidence": 0.9},
    )
    assert msg.context == ["retrieved chunk"]
    assert msg.metadata == {"confidence": 0.9}


# ============================================================================
# ConversationHistory._msg_context() tests
# ============================================================================


def test_msg_context_from_dict_with_context():
    """_msg_context extracts context from a dict message."""
    msg = {"role": "assistant", "content": "A", "context": ["chunk 1"]}
    assert ConversationHistory._msg_context(msg) == ["chunk 1"]


def test_msg_context_from_dict_without_context():
    """_msg_context returns None when dict has no context key."""
    msg = {"role": "assistant", "content": "A"}
    assert ConversationHistory._msg_context(msg) is None


def test_msg_context_from_pydantic_with_context():
    """_msg_context extracts context from an AssistantMessage model."""
    msg = AssistantMessage(content="A", context=["chunk 1", "chunk 2"])
    assert ConversationHistory._msg_context(msg) == ["chunk 1", "chunk 2"]


def test_msg_context_from_pydantic_without_context():
    """_msg_context returns None for an AssistantMessage with no context."""
    msg = AssistantMessage(content="A")
    assert ConversationHistory._msg_context(msg) is None


def test_msg_context_from_user_message():
    """_msg_context returns None for a UserMessage (no context attribute)."""
    msg = UserMessage(content="Q")
    assert ConversationHistory._msg_context(msg) is None


# ============================================================================
# ConversationHistory.get_assistant_context() tests
# ============================================================================


def test_get_assistant_context_empty_conversation():
    """Returns empty list for a conversation with no messages."""
    conv = ConversationHistory.from_messages([])
    assert conv.get_assistant_context() == []


def test_get_assistant_context_no_context():
    """Returns all-None when no assistant message carries context."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "Fine"},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.get_assistant_context()
    assert result == [None, None]


def test_get_assistant_context_all_context():
    """Returns correct context for every turn when all assistant messages carry it."""
    messages = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1", "context": ["source1"]},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2", "context": ["source2", "source3"]},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.get_assistant_context()
    assert result == [["source1"], ["source2", "source3"]]


def test_get_assistant_context_partial():
    """Returns None for turns without context and list for turns that have it."""
    messages = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},  # no context
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2", "context": ["doc_a"]},
        {"role": "user", "content": "Q3"},
        {"role": "assistant", "content": "A3"},  # no context
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.get_assistant_context()
    assert result == [None, ["doc_a"], None]


def test_get_assistant_context_independent_from_metadata():
    """context and metadata are returned independently by their respective getters."""
    messages = [
        {"role": "user", "content": "Q"},
        {
            "role": "assistant",
            "content": "A",
            "context": ["rag chunk"],
            "metadata": {"confidence": 0.8},
        },
    ]
    conv = ConversationHistory.from_messages(messages)
    assert conv.get_assistant_context() == [["rag chunk"]]
    assert conv.get_assistant_metadata() == [{"confidence": 0.8}]


# ============================================================================
# ConversationHistory._msg_tool_calls() tests
# ============================================================================


def test_msg_tool_calls_from_dict_with_tool_calls():
    """_msg_tool_calls extracts tool_calls from a dict message."""
    msg = {"role": "assistant", "content": "A", "tool_calls": [{"name": "fn"}]}
    assert ConversationHistory._msg_tool_calls(msg) == [{"name": "fn"}]


def test_msg_tool_calls_from_dict_without_tool_calls():
    """_msg_tool_calls returns None when dict has no tool_calls key."""
    msg = {"role": "assistant", "content": "A"}
    assert ConversationHistory._msg_tool_calls(msg) is None


def test_msg_tool_calls_from_pydantic_with_tool_calls():
    """_msg_tool_calls extracts tool_calls from an AssistantMessage model."""
    tc = [{"name": "search", "arguments": {"q": "test"}}]
    msg = AssistantMessage(content="A", tool_calls=tc)
    assert ConversationHistory._msg_tool_calls(msg) == tc


def test_msg_tool_calls_from_pydantic_without_tool_calls():
    """_msg_tool_calls returns None for an AssistantMessage with no tool_calls."""
    msg = AssistantMessage(content="A")
    assert ConversationHistory._msg_tool_calls(msg) is None


def test_msg_tool_calls_from_user_message():
    """_msg_tool_calls returns None for a UserMessage (no tool_calls attribute)."""
    msg = UserMessage(content="Q")
    assert ConversationHistory._msg_tool_calls(msg) is None


# ============================================================================
# ConversationHistory.get_assistant_tool_calls() tests
# ============================================================================


def test_get_assistant_tool_calls_empty_conversation():
    """Returns empty list for a conversation with no messages."""
    conv = ConversationHistory.from_messages([])
    assert conv.get_assistant_tool_calls() == []


def test_get_assistant_tool_calls_no_tool_calls():
    """Returns all-None when no assistant message carries tool_calls."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "Fine"},
    ]
    conv = ConversationHistory.from_messages(messages)
    assert conv.get_assistant_tool_calls() == [None, None]


def test_get_assistant_tool_calls_all_present():
    """Returns correct tool_calls for every turn when all assistant messages carry them."""
    messages = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1", "tool_calls": [{"name": "f1"}]},
        {"role": "user", "content": "Q2"},
        {
            "role": "assistant",
            "content": "A2",
            "tool_calls": [{"name": "f2"}, {"name": "f3"}],
        },
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.get_assistant_tool_calls()
    assert result == [[{"name": "f1"}], [{"name": "f2"}, {"name": "f3"}]]


def test_get_assistant_tool_calls_partial():
    """Returns None for turns without tool_calls and list for turns that have them."""
    messages = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2", "tool_calls": [{"name": "fn"}]},
        {"role": "user", "content": "Q3"},
        {"role": "assistant", "content": "A3"},
    ]
    conv = ConversationHistory.from_messages(messages)
    assert conv.get_assistant_tool_calls() == [None, [{"name": "fn"}], None]


def test_get_assistant_tool_calls_independent_from_context_and_metadata():
    """tool_calls, context, and metadata are returned independently."""
    messages = [
        {"role": "user", "content": "Q"},
        {
            "role": "assistant",
            "content": "A",
            "context": ["rag chunk"],
            "metadata": {"confidence": 0.8},
            "tool_calls": [{"name": "search"}],
        },
    ]
    conv = ConversationHistory.from_messages(messages)
    assert conv.get_assistant_context() == [["rag chunk"]]
    assert conv.get_assistant_metadata() == [{"confidence": 0.8}]
    assert conv.get_assistant_tool_calls() == [[{"name": "search"}]]


# ============================================================================
# ConversationHistory.to_text() tests
# ============================================================================


def test_to_text_simple():
    """to_text() returns role-prefixed lines separated by blank lines."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.to_text()
    assert result == "User: Hello\n\nAssistant: Hi there"


def test_to_text_multi_turn():
    """to_text() separates each turn pair with a blank line."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "Fine"},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.to_text()
    assert result == "User: Hello\n\nAssistant: Hi\n\nUser: How are you?\n\nAssistant: Fine"


def test_to_text_skips_empty_content():
    """to_text() skips messages with empty or None content."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": ""},
        {"role": "user", "content": "Anyone there?"},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.to_text()
    assert result == "User: Hello\n\nUser: Anyone there?"


def test_to_text_excludes_metadata():
    """to_text() never includes metadata, context, or tool_calls."""
    messages = [
        {"role": "user", "content": "What is RAG?"},
        {
            "role": "assistant",
            "content": "RAG is retrieval augmented generation.",
            "metadata": {"confidence": 0.95},
            "context": ["doc1"],
            "tool_calls": [{"name": "search"}],
        },
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.to_text()
    assert "metadata" not in result.lower()
    assert "confidence" not in result
    assert "doc1" not in result
    assert "search" not in result
    assert "RAG is retrieval augmented generation." in result


# ============================================================================
# ConversationHistory._format_conversation() tests
# ============================================================================


def test_format_conversation_basic_structure():
    """_format_conversation() produces numbered turns with indented role lines."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "Turn 1:" in result
    assert "  User: Hello" in result
    assert "  Assistant: Hi there" in result


def test_format_conversation_multi_turn_numbering():
    """Each user/assistant pair gets its own incrementing turn number."""
    messages = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2"},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "Turn 1:" in result
    assert "Turn 2:" in result
    assert "Turn 3:" not in result


def test_format_conversation_blank_lines_between_turns():
    """Turns are separated by blank lines (double newline)."""
    messages = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2"},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "\n\n" in result
    turns = result.split("\n\n")
    assert len(turns) == 2


def test_format_conversation_inline_metadata():
    """Metadata appears inline beneath the assistant response in its turn."""
    messages = [
        {"role": "user", "content": "What is RAG?"},
        {
            "role": "assistant",
            "content": "RAG is retrieval augmented generation.",
            "metadata": {"confidence": 0.95, "source": "docs"},
        },
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "  Metadata:" in result
    assert '"confidence"' in result
    assert "0.95" in result
    assert '"source"' in result


def test_format_conversation_inline_context():
    """Context appears inline beneath the assistant response."""
    messages = [
        {"role": "user", "content": "Q"},
        {"role": "assistant", "content": "A", "context": ["chunk 1", "chunk 2"]},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "  Context:" in result
    assert "chunk 1" in result
    assert "chunk 2" in result


def test_format_conversation_inline_tool_calls():
    """Tool calls appear inline beneath the assistant response."""
    messages = [
        {"role": "user", "content": "Search for X"},
        {
            "role": "assistant",
            "content": "Found it.",
            "tool_calls": [{"name": "search", "arguments": {"q": "X"}}],
        },
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "  Tool Calls:" in result
    assert "search" in result


def test_format_conversation_partial_metadata():
    """Only turns with metadata show a Metadata block; others do not."""
    messages = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},  # no metadata
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2", "metadata": {"key": "val"}},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    turns = result.split("\n\n")
    assert "Metadata" not in turns[0]
    assert "Metadata" in turns[1]


def test_format_conversation_no_metadata_no_extra_lines():
    """When no metadata/context/tool_calls exist, no extra lines are added."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "Metadata" not in result
    assert "Context" not in result
    assert "Tool Calls" not in result


def test_format_conversation_metadata_tied_to_correct_turn():
    """Metadata from turn 2 does not bleed into turn 1's text block."""
    messages = [
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
        {"role": "assistant", "content": "A2", "metadata": {"tag": "important"}},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    turn1_text, turn2_text = result.split("\n\n")
    assert "tag" not in turn1_text
    assert "tag" in turn2_text


def test_format_conversation_all_fields_inline():
    """All three fields (metadata, context, tool_calls) render together in one turn."""
    messages = [
        {"role": "user", "content": "Q"},
        {
            "role": "assistant",
            "content": "A",
            "context": ["rag chunk"],
            "metadata": {"confidence": 0.9},
            "tool_calls": [{"name": "fn"}],
        },
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "  Context:" in result
    assert "  Metadata:" in result
    assert "  Tool Calls:" in result


def test_format_conversation_standalone_assistant():
    """A standalone assistant message (no preceding user) gets its own turn."""
    messages = [
        {"role": "assistant", "content": "Welcome!"},
        {"role": "user", "content": "Thanks"},
        {"role": "assistant", "content": "You're welcome"},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "Turn 1:" in result
    assert "  Assistant: Welcome!" in result
    assert "Turn 2:" in result


def test_format_conversation_system_message():
    """System messages are rendered without a turn number."""
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "[system]: You are helpful." in result
    assert "Turn 1:" in result


def test_format_conversation_empty():
    """Empty conversation returns an empty string."""
    conv = ConversationHistory.from_messages([])
    result = conv.format_conversation()
    assert result == ""


def test_format_conversation_tool_call_only_assistant():
    """Assistant message with content=None but tool_calls is not silently dropped."""
    messages = [
        {"role": "user", "content": "Search for X"},
        {"role": "assistant", "content": None, "tool_calls": [{"name": "search", "arguments": {"q": "X"}}]},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "Turn 1:" in result
    assert "  User: Search for X" in result
    assert "  Tool Calls:" in result
    assert "search" in result
    assert "Assistant:" not in result  # no text content, so Assistant: line is omitted


def test_format_conversation_tool_call_only_standalone_assistant():
    """Standalone assistant with content=None but tool_calls is not dropped."""
    messages = [
        {"role": "assistant", "content": None, "tool_calls": [{"name": "fn"}]},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "Turn 1:" in result
    assert "  Tool Calls:" in result
    assert "fn" in result


def test_format_conversation_metadata_only_assistant():
    """Assistant message with content=None but metadata is not silently dropped."""
    messages = [
        {"role": "user", "content": "Q"},
        {"role": "assistant", "content": None, "metadata": {"intent": "search"}},
    ]
    conv = ConversationHistory.from_messages(messages)
    result = conv.format_conversation()
    assert "Turn 1:" in result
    assert "  Metadata:" in result
    assert "intent" in result
