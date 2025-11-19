"""Tests for flexible conversation field support in Penelope."""

import pytest
from rhesis.penelope.schemas import SendMessageParams


class TestFlexibleConversationFields:
    """Tests for flexible conversation field names support."""

    def test_get_conversation_field_value_conversation_id(self):
        """Test get_conversation_field_value with conversation_id."""
        params = SendMessageParams(
            message="Hello",
            conversation_id="conv-123"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "conversation_id"
        assert field_value == "conv-123"

    def test_get_conversation_field_value_session_id(self):
        """Test get_conversation_field_value with session_id."""
        params = SendMessageParams(
            message="Hello",
            session_id="sess-456"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "session_id"
        assert field_value == "sess-456"

    def test_get_conversation_field_value_thread_id(self):
        """Test get_conversation_field_value with thread_id."""
        params = SendMessageParams(
            message="Hello",
            thread_id="thread-789"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "thread_id"
        assert field_value == "thread-789"

    def test_get_conversation_field_value_chat_id(self):
        """Test get_conversation_field_value with chat_id."""
        params = SendMessageParams(
            message="Hello",
            chat_id="chat-101"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "chat_id"
        assert field_value == "chat-101"

    def test_get_conversation_field_value_dialog_id(self):
        """Test get_conversation_field_value with dialog_id."""
        params = SendMessageParams(
            message="Hello",
            dialog_id="dialog-202"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "dialog_id"
        assert field_value == "dialog-202"

    def test_get_conversation_field_value_dialogue_id(self):
        """Test get_conversation_field_value with dialogue_id."""
        params = SendMessageParams(
            message="Hello",
            dialogue_id="dialogue-303"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "dialogue_id"
        assert field_value == "dialogue-303"

    def test_get_conversation_field_value_context_id(self):
        """Test get_conversation_field_value with context_id."""
        params = SendMessageParams(
            message="Hello",
            context_id="ctx-404"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "context_id"
        assert field_value == "ctx-404"

    def test_get_conversation_field_value_interaction_id(self):
        """Test get_conversation_field_value with interaction_id."""
        params = SendMessageParams(
            message="Hello",
            interaction_id="int-505"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "interaction_id"
        assert field_value == "int-505"

    def test_get_conversation_field_value_priority_order(self):
        """Test that conversation_id takes priority over other fields."""
        params = SendMessageParams(
            message="Hello",
            conversation_id="conv-123",
            session_id="sess-456",
            thread_id="thread-789",
            chat_id="chat-101"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "conversation_id"  # Highest priority
        assert field_value == "conv-123"

    def test_get_conversation_field_value_session_id_fallback(self):
        """Test that session_id is used when conversation_id is not set."""
        params = SendMessageParams(
            message="Hello",
            session_id="sess-456",
            thread_id="thread-789",
            chat_id="chat-101"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "session_id"  # Second priority
        assert field_value == "sess-456"

    def test_get_conversation_field_value_no_fields(self):
        """Test get_conversation_field_value when no conversation fields are set."""
        params = SendMessageParams(message="Hello")
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name is None
        assert field_value is None

    def test_get_conversation_field_value_empty_string_ignored(self):
        """Test that empty string values are ignored."""
        params = SendMessageParams(
            message="Hello",
            conversation_id="",  # Empty string should be ignored
            session_id="sess-456"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "session_id"  # Falls back to session_id
        assert field_value == "sess-456"

    def test_get_conversation_field_value_none_values_ignored(self):
        """Test that None values are properly ignored."""
        params = SendMessageParams(
            message="Hello",
            conversation_id=None,
            session_id=None,
            thread_id="thread-789"
        )
        
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "thread_id"  # Falls back to thread_id
        assert field_value == "thread-789"

    def test_send_message_params_backward_compatibility(self):
        """Test that existing session_id usage still works."""
        # This ensures backward compatibility with existing code
        params = SendMessageParams(
            message="Hello world",
            session_id="legacy-session-123"
        )
        
        # Old way still works
        assert params.session_id == "legacy-session-123"
        
        # New way also works
        field_name, field_value = params.get_conversation_field_value()
        assert field_name == "session_id"
        assert field_value == "legacy-session-123"

    def test_send_message_params_all_fields_optional(self):
        """Test that all conversation fields are optional."""
        # Should work with just message
        params = SendMessageParams(message="Hello")
        assert params.message == "Hello"
        assert params.session_id is None
        assert params.conversation_id is None
        assert params.thread_id is None
        assert params.chat_id is None
        assert params.dialog_id is None
        assert params.dialogue_id is None
        assert params.context_id is None
        assert params.interaction_id is None

    def test_send_message_params_mixed_field_usage(self):
        """Test realistic usage with mixed conversation fields."""
        # Simulate different endpoints using different field names
        
        # Endpoint 1: Uses conversation_id
        params1 = SendMessageParams(
            message="Hello endpoint 1",
            conversation_id="conv-abc123"
        )
        field1, value1 = params1.get_conversation_field_value()
        assert field1 == "conversation_id"
        assert value1 == "conv-abc123"
        
        # Endpoint 2: Uses thread_id
        params2 = SendMessageParams(
            message="Hello endpoint 2", 
            thread_id="thread-xyz789"
        )
        field2, value2 = params2.get_conversation_field_value()
        assert field2 == "thread_id"
        assert value2 == "thread-xyz789"
        
        # Endpoint 3: Uses legacy session_id
        params3 = SendMessageParams(
            message="Hello endpoint 3",
            session_id="sess-legacy456"
        )
        field3, value3 = params3.get_conversation_field_value()
        assert field3 == "session_id"
        assert value3 == "sess-legacy456"
