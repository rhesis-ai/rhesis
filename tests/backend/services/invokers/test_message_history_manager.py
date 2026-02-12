"""Tests for MessageHistoryManager."""

from rhesis.backend.app.services.invokers.conversation.history import (
    MessageHistoryManager,
)


class TestMessageHistoryManager:
    """Test MessageHistoryManager class functionality."""

    def test_init_empty(self):
        """No system prompt: get_messages() returns empty list."""
        history = MessageHistoryManager()
        assert history.get_messages() == []

    def test_init_with_system_prompt(self):
        """System prompt is prepended as first message."""
        history = MessageHistoryManager(system_prompt="You are helpful.")
        messages = history.get_messages()
        assert len(messages) == 1
        assert messages[0] == {"role": "system", "content": "You are helpful."}

    def test_add_user_message(self):
        """Appends a user-role message."""
        history = MessageHistoryManager()
        history.add_user_message("Hello")
        messages = history.get_messages()
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello"}

    def test_add_assistant_message(self):
        """Appends an assistant-role message."""
        history = MessageHistoryManager()
        history.add_assistant_message("Hi there!")
        messages = history.get_messages()
        assert len(messages) == 1
        assert messages[0] == {"role": "assistant", "content": "Hi there!"}

    def test_multi_turn_accumulation(self):
        """Messages accumulate in order across multiple turns."""
        history = MessageHistoryManager()
        history.add_user_message("Hello")
        history.add_assistant_message("Hi!")
        history.add_user_message("How are you?")

        messages = history.get_messages()
        assert len(messages) == 3
        assert messages[0] == {"role": "user", "content": "Hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi!"}
        assert messages[2] == {"role": "user", "content": "How are you?"}

    def test_system_prompt_stays_first(self):
        """After adding multiple messages, system prompt remains at index 0."""
        history = MessageHistoryManager(system_prompt="Be concise.")
        history.add_user_message("Hello")
        history.add_assistant_message("Hi!")
        history.add_user_message("Tell me a joke")

        messages = history.get_messages()
        assert len(messages) == 4
        assert messages[0] == {"role": "system", "content": "Be concise."}
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"

    def test_get_messages_returns_copy(self):
        """Modifying the returned list does not affect internal state."""
        history = MessageHistoryManager()
        history.add_user_message("Hello")

        returned = history.get_messages()
        returned.append({"role": "user", "content": "injected"})
        returned[0]["content"] = "modified"

        # Internal state should be unchanged
        messages = history.get_messages()
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello"}

    def test_add_empty_message(self):
        """Empty string content is accepted without error."""
        history = MessageHistoryManager()
        history.add_user_message("")
        history.add_assistant_message("")

        messages = history.get_messages()
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": ""}
        assert messages[1] == {"role": "assistant", "content": ""}

    def test_message_format_matches_openai(self):
        """Each message has exactly 'role' and 'content' keys."""
        history = MessageHistoryManager(system_prompt="System")
        history.add_user_message("User")
        history.add_assistant_message("Assistant")

        for msg in history.get_messages():
            assert set(msg.keys()) == {"role", "content"}

    def test_multi_turn_conversation_flow(self):
        """Full 3-turn conversation with system prompt matches expected format."""
        history = MessageHistoryManager(system_prompt="You are a customer support agent.")
        history.add_user_message("I need help with my order")
        history.add_assistant_message("I'd be happy to help! What's your order number?")
        history.add_user_message("It's #12345")
        history.add_assistant_message("Let me look that up for you.")
        history.add_user_message("Thanks")

        expected = [
            {
                "role": "system",
                "content": "You are a customer support agent.",
            },
            {"role": "user", "content": "I need help with my order"},
            {
                "role": "assistant",
                "content": "I'd be happy to help! What's your order number?",
            },
            {"role": "user", "content": "It's #12345"},
            {
                "role": "assistant",
                "content": "Let me look that up for you.",
            },
            {"role": "user", "content": "Thanks"},
        ]
        assert history.get_messages() == expected
