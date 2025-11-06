"""
Demo script for Phase 1: Conversational Metrics Core Infrastructure.

This demonstrates the new conversational metric types and shows how
they work with standard message formats.
"""

from rhesis.sdk.metrics.conversational import (
    AssistantMessage,
    ConversationHistory,
    SystemMessage,
    UserMessage,
)


def main():
    print("=" * 60)
    print("Phase 1: Conversational Metrics Demo")
    print("=" * 60)
    print()

    # Example 1: Creating messages with Pydantic models
    print("1. Creating messages with Pydantic models:")
    print("-" * 60)
    user_msg = UserMessage(content="What types of insurance do you offer?")
    assistant_msg = AssistantMessage(content="We offer auto, home, and life insurance.")
    system_msg = SystemMessage(content="You are a helpful insurance agent.")

    print(f"User: {user_msg.content}")
    print(f"Assistant: {assistant_msg.content}")
    print(f"System: {system_msg.content}")
    print()

    # Example 2: Creating conversation from dicts
    print("2. Creating conversation from dicts:")
    print("-" * 60)
    conversation_dicts = [
        {"role": "user", "content": "What is your refund policy?"},
        {"role": "assistant", "content": "We offer 30-day money-back guarantee."},
        {"role": "user", "content": "Does it apply to all products?"},
        {"role": "assistant", "content": "Yes, it applies to all our products."},
    ]

    conv = ConversationHistory.from_messages(conversation_dicts)
    print(f"Created conversation with {len(conv)} messages")
    print()

    # Example 3: Mixed Pydantic and dict messages
    print("3. Mixed Pydantic models and dicts:")
    print("-" * 60)
    mixed_messages = [
        SystemMessage(content="You are a helpful assistant."),
        {"role": "user", "content": "Hello!"},
        AssistantMessage(content="Hi! How can I help you today?"),
    ]

    conv_mixed = ConversationHistory.from_messages(mixed_messages)
    print(f"Created mixed conversation with {len(conv_mixed)} messages")
    print()

    # Example 4: Getting simple turns (role/content pairs)
    print("4. Extracting simple turns:")
    print("-" * 60)
    simple_turns = conv.get_simple_turns()
    for i, turn in enumerate(simple_turns, 1):
        print(f"  Turn {i}: {turn['role']} - {turn['content'][:40]}...")
    print()

    # Example 5: Conversation with metadata
    print("5. Conversation with metadata:")
    print("-" * 60)
    conv_with_meta = ConversationHistory.from_messages(
        conversation_dicts,
        conversation_id="demo-123",
        metadata={
            "goal": "Customer learns about refund policy",
            "source": "demo",
            "test_type": "policy_inquiry",
        },
    )
    print(f"Conversation ID: {conv_with_meta.conversation_id}")
    print(f"Metadata: {conv_with_meta.metadata}")
    print()

    # Example 6: Converting to dict list
    print("6. Converting to dict list:")
    print("-" * 60)
    dict_list = conv.to_dict_list()
    print(f"Converted {len(dict_list)} messages to dict format")
    print(f"First message: {dict_list[0]}")
    print()

    # Example 7: Assistant message with tool calls
    print("7. Assistant message with tool calls:")
    print("-" * 60)
    tool_calls = [
        {
            "id": "call_123",
            "type": "function",
            "function": {"name": "get_policy", "arguments": '{"policy_type": "auto"}'},
        }
    ]
    assistant_with_tools = AssistantMessage(
        content="Let me check that for you.", tool_calls=tool_calls
    )
    print(f"Assistant content: {assistant_with_tools.content}")
    print(f"Tool calls: {len(assistant_with_tools.tool_calls)} tool(s) called")
    print()

    print("=" * 60)
    print("✓ Phase 1 Complete: All conversational types working!")
    print("=" * 60)


if __name__ == "__main__":
    main()
