"""Tests for conversation tracking functionality."""

from rhesis.backend.app.services.invokers.conversation.tracker import (
    CONVERSATION_FIELD_NAMES,
    ConversationTracker,
)


class TestConversationTracker:
    """Test ConversationTracker class functionality."""

    def test_detect_conversation_field_with_conversation_id(self, sample_endpoint_conversation):
        """Test detection of conversation_id field."""
        tracker = ConversationTracker()

        field = tracker.detect_conversation_field(sample_endpoint_conversation)

        assert field == "conversation_id"

    def test_detect_conversation_field_with_session_id(self, sample_endpoint_rest):
        """Test detection of session_id field."""
        tracker = ConversationTracker()
        sample_endpoint_rest.response_mapping = {"session_id": "$.session_id", "output": "$.text"}

        field = tracker.detect_conversation_field(sample_endpoint_rest)

        assert field == "session_id"

    def test_detect_conversation_field_with_thread_id(self, sample_endpoint_rest):
        """Test detection of thread_id field."""
        tracker = ConversationTracker()
        sample_endpoint_rest.response_mapping = {"thread_id": "$.thread.id", "output": "$.text"}

        field = tracker.detect_conversation_field(sample_endpoint_rest)

        assert field == "thread_id"

    def test_detect_conversation_field_priority_order(self, sample_endpoint_rest):
        """Test that conversation_id takes priority over session_id."""
        tracker = ConversationTracker()
        # Both are present, conversation_id should be detected first
        sample_endpoint_rest.response_mapping = {
            "session_id": "$.session.id",
            "conversation_id": "$.conv.id",
            "output": "$.text",
        }

        field = tracker.detect_conversation_field(sample_endpoint_rest)

        # conversation_id comes first in CONVERSATION_FIELD_NAMES
        assert field == "conversation_id"

    def test_detect_conversation_field_no_tracking(self, sample_endpoint_rest):
        """Test detection when no conversation field is configured."""
        tracker = ConversationTracker()
        sample_endpoint_rest.response_mapping = {"output": "$.text"}

        field = tracker.detect_conversation_field(sample_endpoint_rest)

        assert field is None

    def test_detect_conversation_field_empty_mappings(self, sample_endpoint_rest):
        """Test detection with empty response mappings."""
        tracker = ConversationTracker()
        sample_endpoint_rest.response_mapping = {}

        field = tracker.detect_conversation_field(sample_endpoint_rest)

        assert field is None

    def test_detect_conversation_field_none_mappings(self, sample_endpoint_rest):
        """Test detection with None response mappings."""
        tracker = ConversationTracker()
        sample_endpoint_rest.response_mapping = None

        field = tracker.detect_conversation_field(sample_endpoint_rest)

        assert field is None

    def test_prepare_conversation_context_omits_field_when_missing(
        self, sample_endpoint_conversation
    ):
        """Test that conversation field is omitted from context when missing."""
        tracker = ConversationTracker()
        input_data = {"input": "Hello"}

        context, field = tracker.prepare_conversation_context(
            sample_endpoint_conversation, input_data
        )

        assert field == "conversation_id"
        assert "conversation_id" not in context  # Should be omitted, not None
        assert context["input"] == "Hello"

    def test_prepare_conversation_context_preserves_existing_value(
        self, sample_endpoint_conversation
    ):
        """Test that existing conversation field value is preserved."""
        tracker = ConversationTracker()
        input_data = {"input": "Hello", "conversation_id": "conv-123"}

        context, field = tracker.prepare_conversation_context(
            sample_endpoint_conversation, input_data
        )

        assert field == "conversation_id"
        assert context["conversation_id"] == "conv-123"

    def test_prepare_conversation_context_with_extra_context(self, sample_endpoint_conversation):
        """Test context preparation with extra context kwargs."""
        tracker = ConversationTracker()
        input_data = {"input": "Hello"}

        context, field = tracker.prepare_conversation_context(
            sample_endpoint_conversation, input_data, auth_token="token-123", user_id="user-456"
        )

        assert context["input"] == "Hello"
        assert context["auth_token"] == "token-123"
        assert context["user_id"] == "user-456"
        assert "conversation_id" not in context  # Should be omitted when not provided

    def test_prepare_conversation_context_no_tracking(self, sample_endpoint_rest):
        """Test context preparation when no conversation tracking configured."""
        tracker = ConversationTracker()
        sample_endpoint_rest.response_mapping = {"output": "$.text"}
        input_data = {"input": "Hello"}

        context, field = tracker.prepare_conversation_context(sample_endpoint_rest, input_data)

        assert field is None
        assert context == input_data
        assert "conversation_id" not in context

    def test_extract_conversation_id_from_rendered_body(self):
        """Test extracting conversation ID from rendered request body."""
        tracker = ConversationTracker()
        rendered_body = {"query": "test", "conversation_id": "conv-789"}
        input_data = {"input": "test"}

        conv_id = tracker.extract_conversation_id(rendered_body, input_data, "conversation_id")

        assert conv_id == "conv-789"

    def test_extract_conversation_id_from_input_data(self):
        """Test extracting conversation ID from input data when not in body."""
        tracker = ConversationTracker()
        rendered_body = {"query": "test"}
        input_data = {"input": "test", "conversation_id": "conv-999"}

        conv_id = tracker.extract_conversation_id(rendered_body, input_data, "conversation_id")

        assert conv_id == "conv-999"
        # Should also be added to rendered_body
        assert rendered_body["conversation_id"] == "conv-999"

    def test_extract_conversation_id_not_present(self):
        """Test extracting conversation ID when not present anywhere."""
        tracker = ConversationTracker()
        rendered_body = {"query": "test"}
        input_data = {"input": "test"}

        conv_id = tracker.extract_conversation_id(rendered_body, input_data, "conversation_id")

        assert conv_id is None

    def test_extract_conversation_id_no_field(self):
        """Test extracting conversation ID when field is None."""
        tracker = ConversationTracker()
        rendered_body = {"query": "test"}
        input_data = {"input": "test"}

        conv_id = tracker.extract_conversation_id(rendered_body, input_data, None)

        assert conv_id is None

    def test_conversation_field_names_includes_tier1_and_tier2(self):
        """Test that CONVERSATION_FIELD_NAMES includes expected fields."""
        # Tier 1
        assert "conversation_id" in CONVERSATION_FIELD_NAMES
        assert "session_id" in CONVERSATION_FIELD_NAMES
        assert "thread_id" in CONVERSATION_FIELD_NAMES
        assert "chat_id" in CONVERSATION_FIELD_NAMES

        # Tier 2
        assert "dialog_id" in CONVERSATION_FIELD_NAMES
        assert "dialogue_id" in CONVERSATION_FIELD_NAMES
        assert "context_id" in CONVERSATION_FIELD_NAMES
        assert "interaction_id" in CONVERSATION_FIELD_NAMES

    def test_conversation_field_names_priority_order(self):
        """Test that Tier 1 fields come before Tier 2."""
        # conversation_id should be first
        assert CONVERSATION_FIELD_NAMES[0] == "conversation_id"

        # Tier 1 should come before Tier 2
        tier1_fields = ["conversation_id", "session_id", "thread_id", "chat_id"]
        tier2_fields = ["dialog_id", "dialogue_id", "context_id", "interaction_id"]

        tier1_indices = [CONVERSATION_FIELD_NAMES.index(f) for f in tier1_fields]
        tier2_indices = [CONVERSATION_FIELD_NAMES.index(f) for f in tier2_fields]

        assert max(tier1_indices) < min(tier2_indices)
