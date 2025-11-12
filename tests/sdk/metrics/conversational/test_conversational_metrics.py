"""Tests for DeepEval conversational metrics."""

import pytest

from rhesis.sdk.metrics.conversational.types import ConversationHistory
from rhesis.sdk.metrics.providers.deepeval.conversational_metrics import (
    DeepEvalConversationCompleteness,
    DeepEvalGoalAccuracy,
    DeepEvalKnowledgeRetention,
    DeepEvalRoleAdherence,
    DeepEvalToolUse,
    DeepEvalTurnRelevancy,
)


class TestDeepEvalTurnRelevancy:
    """Tests for DeepEval Turn Relevancy metric."""

    def test_initialization(self):
        """Test metric initialization."""
        metric = DeepEvalTurnRelevancy(threshold=0.7, window_size=5)
        assert metric.name == "turn_relevancy"
        assert metric.threshold == 0.7
        assert metric.window_size == 5

    def test_default_parameters(self):
        """Test metric with default parameters."""
        metric = DeepEvalTurnRelevancy()
        assert metric.threshold == 0.5
        assert metric.window_size == 10

    def test_evaluate_relevant_conversation(self):
        """Test evaluation of a relevant conversation."""
        metric = DeepEvalTurnRelevancy(threshold=0.5)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "What insurance do you offer?"},
            {"role": "assistant", "content": "We offer auto, home, and life insurance."},
            {"role": "user", "content": "Tell me about auto coverage."},
            {"role": "assistant", "content": "Auto insurance includes liability and collision coverage."},
        ])

        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0
        assert "is_successful" in result.details
        assert "reason" in result.details

    def test_evaluate_irrelevant_conversation(self):
        """Test evaluation of an irrelevant conversation."""
        metric = DeepEvalTurnRelevancy(threshold=0.7)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "What's the weather like?"},
            {"role": "assistant", "content": "I like pizza."},
            {"role": "user", "content": "Will it rain today?"},
            {"role": "assistant", "content": "The sky is blue."},
        ])

        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0


class TestDeepEvalRoleAdherence:
    """Tests for DeepEval Role Adherence metric."""

    def test_initialization(self):
        """Test metric initialization."""
        metric = DeepEvalRoleAdherence(threshold=0.7)
        assert metric.name == "role_adherence"
        assert metric.threshold == 0.7

    def test_default_threshold(self):
        """Test metric with default threshold."""
        metric = DeepEvalRoleAdherence()
        assert metric.threshold == 0.5

    def test_evaluate_role_adherent_conversation(self):
        """Test evaluation of a conversation where assistant adheres to role."""
        metric = DeepEvalRoleAdherence(threshold=0.5)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "I need help with my order."},
            {"role": "assistant", "content": "I'll help you with that right away."},
            {"role": "user", "content": "Can you check the status?"},
            {"role": "assistant", "content": "Let me check your order status for you."},
        ])

        result = metric.evaluate(
            conversation_history=conversation,
            chatbot_role="customer support agent"
        )

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0
        assert "is_successful" in result.details
        assert "reason" in result.details

    def test_evaluate_role_violation_conversation(self):
        """Test evaluation of a conversation with role violations."""
        metric = DeepEvalRoleAdherence(threshold=0.7)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "I need help with my order."},
            {"role": "assistant", "content": "I'll help you with that."},
            {"role": "user", "content": "Can you give me stock tips?"},
            {"role": "assistant", "content": "Sure, invest in tech stocks!"},
        ])

        result = metric.evaluate(
            conversation_history=conversation,
            chatbot_role="customer support agent"
        )

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0

    def test_evaluate_without_chatbot_role(self):
        """Test evaluation without chatbot_role parameter (uses default 'assistant')."""
        metric = DeepEvalRoleAdherence(threshold=0.5)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "Hello, can you help me?"},
            {"role": "assistant", "content": "Yes, I'm here to help you."},
            {"role": "user", "content": "Great, thank you!"},
            {"role": "assistant", "content": "You're welcome!"},
        ])

        # Should work without chatbot_role parameter (defaults to "assistant")
        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0
        assert "is_successful" in result.details
        assert "reason" in result.details


class TestDeepEvalKnowledgeRetention:
    """Tests for DeepEval Knowledge Retention metric."""

    def test_initialization(self):
        """Test metric initialization."""
        metric = DeepEvalKnowledgeRetention(threshold=0.7)
        assert metric.name == "knowledge_retention"
        assert metric.threshold == 0.7

    def test_default_threshold(self):
        """Test metric with default threshold."""
        metric = DeepEvalKnowledgeRetention()
        assert metric.threshold == 0.5

    def test_evaluate_good_retention(self):
        """Test evaluation of a conversation with good knowledge retention."""
        metric = DeepEvalKnowledgeRetention(threshold=0.5)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "My order number is ABC123."},
            {"role": "assistant", "content": "I've noted your order number ABC123."},
            {"role": "user", "content": "What was my order number again?"},
            {"role": "assistant", "content": "Your order number is ABC123."},
        ])

        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0
        assert "is_successful" in result.details
        assert "reason" in result.details

    def test_evaluate_poor_retention(self):
        """Test evaluation of a conversation with poor knowledge retention."""
        metric = DeepEvalKnowledgeRetention(threshold=0.7)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "My name is John Smith."},
            {"role": "assistant", "content": "Hello John."},
            {"role": "user", "content": "What's my name?"},
            {"role": "assistant", "content": "I'm not sure."},
        ])

        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0

    def test_evaluate_multiple_facts(self):
        """Test evaluation with multiple facts to retain."""
        metric = DeepEvalKnowledgeRetention(threshold=0.6)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "I'm booking for 3 people on June 15th."},
            {"role": "assistant", "content": "Noted, 3 people on June 15th."},
            {"role": "user", "content": "How many people was that?"},
            {"role": "assistant", "content": "That was 3 people."},
            {"role": "user", "content": "And what date?"},
            {"role": "assistant", "content": "June 15th."},
        ])

        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0


class TestDeepEvalConversationCompleteness:
    """Tests for DeepEval Conversation Completeness metric."""

    def test_initialization(self):
        """Test metric initialization."""
        metric = DeepEvalConversationCompleteness(threshold=0.7)
        assert metric.name == "conversation_completeness"
        assert metric.threshold == 0.7

    def test_default_threshold(self):
        """Test metric with default threshold."""
        metric = DeepEvalConversationCompleteness()
        assert metric.threshold == 0.5

    def test_evaluate_complete_conversation(self):
        """Test evaluation of a complete conversation."""
        metric = DeepEvalConversationCompleteness(threshold=0.5)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "I need to cancel my subscription."},
            {"role": "assistant", "content": "I can help with that. Let me process the cancellation."},
            {"role": "assistant", "content": "Your subscription has been cancelled successfully."},
            {"role": "user", "content": "Thank you!"},
        ])

        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0
        assert "is_successful" in result.details
        assert "reason" in result.details

    def test_evaluate_incomplete_conversation(self):
        """Test evaluation of an incomplete conversation."""
        metric = DeepEvalConversationCompleteness(threshold=0.7)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "I need to cancel my subscription."},
            {"role": "assistant", "content": "Let me look into that."},
            {"role": "user", "content": "Okay..."},
        ])

        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0

    def test_evaluate_multi_request_conversation(self):
        """Test conversation addressing multiple requests."""
        metric = DeepEvalConversationCompleteness(threshold=0.6)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "I need to update my email and change my password."},
            {"role": "assistant", "content": "I'll help with both. What's your new email?"},
            {"role": "user", "content": "newemail@example.com"},
            {"role": "assistant", "content": "Email updated. Now for the password reset."},
            {"role": "assistant", "content": "Password reset link sent. Both tasks completed."},
        ])

        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0


class TestDeepEvalGoalAccuracy:
    """Tests for DeepEval Goal Accuracy metric."""

    def test_initialization(self):
        """Test metric initialization."""
        metric = DeepEvalGoalAccuracy(threshold=0.7)
        assert metric.name == "goal_accuracy"
        assert metric.threshold == 0.7

    def test_default_threshold(self):
        """Test metric with default threshold."""
        metric = DeepEvalGoalAccuracy()
        assert metric.threshold == 0.5

    def test_evaluate_goal_achieved(self):
        """Test evaluation of a conversation where goal is achieved."""
        metric = DeepEvalGoalAccuracy(threshold=0.5)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "Book me a flight to Paris for next week."},
            {"role": "assistant", "content": "I'll search for flights to Paris for next week."},
            {"role": "assistant", "content": "Found available flights. Would you like me to book one?"},
            {"role": "user", "content": "Yes, please."},
            {"role": "assistant", "content": "Flight booked successfully for next week to Paris."},
        ])

        result = metric.evaluate(
            conversation_history=conversation,
            goal="Book a flight to Paris for next week"
        )

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0
        assert "is_successful" in result.details
        assert "reason" in result.details

    def test_evaluate_goal_not_achieved(self):
        """Test evaluation of a conversation where goal is not achieved."""
        metric = DeepEvalGoalAccuracy(threshold=0.7)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "Book me a flight to Paris."},
            {"role": "assistant", "content": "Paris is a beautiful city."},
            {"role": "user", "content": "Can you book the flight?"},
            {"role": "assistant", "content": "Flights are available."},
        ])

        result = metric.evaluate(
            conversation_history=conversation,
            goal="Book a flight to Paris"
        )

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0


class TestDeepEvalToolUse:
    """Tests for DeepEval Tool Use metric."""

    def test_initialization(self):
        """Test metric initialization."""
        available_tools = [{"name": "get_weather", "description": "Get current weather"}]
        metric = DeepEvalToolUse(available_tools=available_tools, threshold=0.7)
        assert metric.name == "tool_use"
        assert metric.threshold == 0.7
        assert metric.available_tools == available_tools

    def test_default_threshold(self):
        """Test metric with default threshold."""
        available_tools = [{"name": "get_weather"}]
        metric = DeepEvalToolUse(available_tools=available_tools)
        assert metric.threshold == 0.5
    
    def test_initialization_without_tools(self):
        """Test metric initialization without available_tools (defaults to empty list)."""
        metric = DeepEvalToolUse(threshold=0.7)
        assert metric.name == "tool_use"
        assert metric.threshold == 0.7
        assert metric.available_tools == []

    def test_evaluate_appropriate_tool_use(self):
        """Test evaluation of appropriate tool usage."""
        available_tools = [{"name": "get_weather", "description": "Get current weather information"}]
        metric = DeepEvalToolUse(available_tools=available_tools, threshold=0.5)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "What's the weather like?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "1", "type": "function", "function": {"name": "get_weather"}}]
            },
            {"role": "tool", "tool_call_id": "1", "name": "get_weather", "content": "Sunny, 75°F"},
            {"role": "assistant", "content": "It's sunny and 75°F today!"},
        ])

        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0
        assert "is_successful" in result.details
        assert "reason" in result.details

    def test_evaluate_multiple_tools(self):
        """Test evaluation with multiple tool calls."""
        available_tools = [
            {"name": "get_weather", "description": "Get weather information"},
            {"name": "get_time", "description": "Get current time"}
        ]
        metric = DeepEvalToolUse(available_tools=available_tools, threshold=0.6)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "What's the weather and time in Tokyo?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "1", "type": "function", "function": {"name": "get_weather"}},
                    {"id": "2", "type": "function", "function": {"name": "get_time"}}
                ]
            },
            {"role": "tool", "tool_call_id": "1", "name": "get_weather", "content": "Rainy"},
            {"role": "tool", "tool_call_id": "2", "name": "get_time", "content": "2:30 PM"},
            {"role": "assistant", "content": "In Tokyo, it's rainy and currently 2:30 PM."},
        ])

        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0

    def test_evaluate_without_available_tools(self):
        """Test evaluation without available_tools parameter (uses empty list default)."""
        metric = DeepEvalToolUse(threshold=0.5)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "What's the weather like?"},
            {"role": "assistant", "content": "I don't have access to weather data."},
        ])

        # Should work without available_tools parameter (defaults to empty list)
        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0
        assert "is_successful" in result.details
        assert "reason" in result.details

    def test_evaluate_with_tool_use_no_tools_provided(self):
        """Test evaluation when tools are used but no tools list was provided."""
        metric = DeepEvalToolUse(threshold=0.5)  # No available_tools

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "What's the weather?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "1", "type": "function", "function": {"name": "get_weather"}}]
            },
            {"role": "tool", "tool_call_id": "1", "name": "get_weather", "content": "Sunny"},
            {"role": "assistant", "content": "It's sunny today!"},
        ])

        # Should evaluate even without available_tools provided
        result = metric.evaluate(conversation_history=conversation)

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0


class TestMetricConfiguration:
    """Tests for metric configuration and properties."""

    def test_turn_relevancy_config(self):
        """Test Turn Relevancy metric configuration."""
        metric = DeepEvalTurnRelevancy()
        assert metric.requires_ground_truth is False
        assert metric.requires_context is False

    def test_role_adherence_config(self):
        """Test Role Adherence metric configuration."""
        metric = DeepEvalRoleAdherence()
        assert metric.requires_ground_truth is False
        assert metric.requires_context is False

    def test_knowledge_retention_config(self):
        """Test Knowledge Retention metric configuration."""
        metric = DeepEvalKnowledgeRetention()
        assert metric.requires_ground_truth is False
        assert metric.requires_context is False

    def test_conversation_completeness_config(self):
        """Test Conversation Completeness metric configuration."""
        metric = DeepEvalConversationCompleteness()
        assert metric.requires_ground_truth is False
        assert metric.requires_context is False

    def test_goal_accuracy_config(self):
        """Test Goal Accuracy metric configuration."""
        metric = DeepEvalGoalAccuracy()
        assert metric.requires_ground_truth is False
        assert metric.requires_context is False

    def test_tool_use_config(self):
        """Test Tool Use metric configuration."""
        metric = DeepEvalToolUse()  # No longer requires available_tools
        assert metric.requires_ground_truth is False
        assert metric.requires_context is False


class TestConversationHistoryFormats:
    """Tests for different conversation history formats."""

    def test_dict_format(self):
        """Test evaluation with dict format messages."""
        metric = DeepEvalTurnRelevancy(threshold=0.5)

        conversation = ConversationHistory.from_messages([
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ])

        result = metric.evaluate(conversation_history=conversation)
        assert isinstance(result.score, float)

    def test_with_metadata(self):
        """Test evaluation with conversation metadata."""
        metric = DeepEvalGoalAccuracy(threshold=0.5)

        conversation = ConversationHistory.from_messages(
            [
                {"role": "user", "content": "Book a flight."},
                {"role": "assistant", "content": "Flight booked."},
            ],
            metadata={"goal": "Book a flight", "source": "test"}
        )

        result = metric.evaluate(
            conversation_history=conversation,
            goal="Book a flight"
        )
        assert isinstance(result.score, float)

    def test_empty_conversation_handling(self):
        """Test handling of empty conversations."""
        metric = DeepEvalTurnRelevancy(threshold=0.5)

        conversation = ConversationHistory.from_messages([])

        # Should handle empty conversation gracefully
        # Note: DeepEval might raise an error or return a default score
        # depending on implementation
        try:
            result = metric.evaluate(conversation_history=conversation)
            assert isinstance(result.score, float)
        except Exception:
            # Empty conversations might not be supported
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

