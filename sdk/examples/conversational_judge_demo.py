"""
Demo: ConversationalJudge Architecture and Extension

This demonstrates:
1. How GoalAchievementJudge uses ConversationalJudge as a base
2. How to create custom conversational judges
3. Using the conversational judge architecture with real LLMs
"""

from typing import Optional, Union

from pydantic import BaseModel, Field

from rhesis.sdk.metrics import (
    ConversationalJudge,
    ConversationHistory,
    GoalAchievementJudge,
)
from rhesis.sdk.metrics.base import MetricResult, MetricType, ScoreType
from rhesis.sdk.metrics.providers.native.conversational_judge import (
    ConversationalJudgeConfig,
)
from rhesis.sdk.models import BaseLLM, VertexAILLM


# Example: Creating a custom conversational judge
class ToneConsistencyScoreResponse(BaseModel):
    """Response model for tone consistency evaluation."""

    score: float = Field(description="Tone consistency score")
    reason: str = Field(description="Explanation for the score", default="")


class ToneConsistencyJudge(ConversationalJudge):
    """
    Custom conversational judge that evaluates tone consistency.

    This demonstrates how to extend ConversationalJudge to create
    specialized conversational metrics.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        model: Optional[Union[str, BaseLLM]] = None,
        **kwargs,
    ):
        config = ConversationalJudgeConfig(
            evaluation_prompt="""Evaluate the consistency of the assistant's tone throughout the conversation.

Consider:
- Does the assistant maintain a professional, helpful tone?
- Are there any inappropriate shifts in formality or politeness?
- Is the emotional tone appropriate for the context?""",
            evaluation_steps="""1. Analyze each assistant response for tone
2. Identify the predominant tone (formal, casual, professional, friendly, etc.)
3. Note any inconsistencies or inappropriate shifts
4. Evaluate if the tone matches the context and user's style
5. Assign a score based on overall consistency""",
            reasoning="""When evaluating tone:
- Consistency: Tone should remain stable unless context requires adaptation
- Appropriateness: Tone should match the conversation context
- Professionalism: Maintain appropriate boundaries
- Responsiveness: Tone can adapt to user's style while staying consistent""",
            name=name or "tone_consistency",
            description=description or "Evaluates tone consistency across conversation",
            metric_type=MetricType.CONVERSATIONAL,
            score_type=ScoreType.NUMERIC,
            class_name=self.__class__.__name__,
        )
        super().__init__(config=config, model=model)
        self._setup_jinja_environment()

    def evaluate(
        self,
        conversation_history: ConversationHistory,
        expected_tone: Optional[str] = None,
    ) -> MetricResult:
        """
        Evaluate tone consistency in the conversation.

        Args:
            conversation_history: The conversation to evaluate
            expected_tone: Optional description of expected tone (e.g., "professional and friendly")

        Returns:
            MetricResult with tone consistency score (0-1)
        """
        self._validate_evaluate_inputs(conversation_history)

        # Generate prompt with optional expected tone
        prompt = self._get_prompt_template(
            conversation_history=conversation_history,
            goal=expected_tone or "Consistent, appropriate tone",
        )

        details = self._get_base_details(prompt)
        details["turn_count"] = len(conversation_history)
        details["expected_tone"] = expected_tone or "Infer from context"

        try:
            response = self.model.generate(prompt, schema=ToneConsistencyScoreResponse)
            response = ToneConsistencyScoreResponse(**response)  # type: ignore

            score = response.score
            reason = response.reason

            details.update(
                {
                    "score": score,
                    "reason": reason,
                    "is_successful": score >= 0.7,  # Simple threshold for demo
                }
            )

            return MetricResult(score=score, details=details)

        except Exception as e:
            return self._handle_evaluation_error(e, details, 0.0)


def main():
    print("=" * 70)
    print("ConversationalJudge Architecture Demo")
    print("=" * 70)
    print()

    # Initialize model
    model = VertexAILLM(model_name="gemini-2.0-flash")

    # Example 1: Using the built-in GoalAchievementJudge
    print("1. Built-in Judge: GoalAchievementJudge")
    print("-" * 70)
    print()

    goal_judge = GoalAchievementJudge(
        name="insurance_goal_judge",
        threshold=0.7,
        model=model,
    )

    print(f"Judge Name: {goal_judge.name}")
    print(f"Base Class: {goal_judge.__class__.__bases__[0].__name__}")
    print(f"Metric Type: {goal_judge.metric_type}")
    print(f"Score Type: {goal_judge.score_type}")
    print(f"Score Range: {goal_judge.min_score} - {goal_judge.max_score}")
    print(f"Threshold: {goal_judge.threshold}")
    print()

    # Test Case 1a: Goal Fully Achieved
    print("Test 1a: Goal Fully Achieved")
    print("~" * 50)

    successful_conversation = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "I need help understanding my insurance coverage."},
            {
                "role": "assistant",
                "content": "I'd be happy to help! What specific aspect of your coverage would you like to understand better?",
            },
            {"role": "user", "content": "What's covered under collision insurance?"},
            {
                "role": "assistant",
                "content": "Collision insurance covers damage to your vehicle from accidents with other vehicles or objects, regardless of fault. It pays for repairs or replacement up to your vehicle's actual cash value.",
            },
            {"role": "user", "content": "Thanks, that's very clear!"},
            {
                "role": "assistant",
                "content": "You're welcome! Feel free to ask if you have any other questions about your coverage.",
            },
        ]
    )

    print(f"Conversation: {len(successful_conversation)} messages")
    print("Goal: Customer understands collision insurance coverage")
    print()

    result = goal_judge.evaluate(
        conversation_history=successful_conversation,
        goal="Customer understands collision insurance coverage",
    )

    print(f"✓ Score: {result.score}/{goal_judge.max_score}")
    print(f"✓ Successful: {result.details['is_successful']} (threshold: {goal_judge.threshold})")
    print(f"✓ Turn Count: {result.details['turn_count']}")
    print(f"✓ Reason: {result.details['reason'][:200]}...")
    print()

    # Test Case 1b: Goal Partially Achieved
    print("Test 1b: Goal Partially Achieved")
    print("~" * 50)

    partial_conversation = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "Can you help me file a claim?"},
            {
                "role": "assistant",
                "content": "Sure! I can help with that. First, I need some information.",
            },
            {"role": "user", "content": "What information do you need?"},
            {
                "role": "assistant",
                "content": "I'll need your policy number and the date of the incident.",
            },
            {"role": "user", "content": "My policy is #123456."},
            {
                "role": "assistant",
                "content": "Thanks! And when did the incident occur?",
            },
        ]
    )

    print(f"Conversation: {len(partial_conversation)} messages")
    print("Goal: Customer successfully files insurance claim")
    print()

    partial_result = goal_judge.evaluate(
        conversation_history=partial_conversation,
        goal="Customer successfully files insurance claim",
    )

    print(f"◐ Score: {partial_result.score}/{goal_judge.max_score}")
    print(
        f"◐ Successful: {partial_result.details['is_successful']} (threshold: {goal_judge.threshold})"
    )
    print(f"◐ Turn Count: {partial_result.details['turn_count']}")
    print(f"◐ Reason: {partial_result.details['reason'][:200]}...")
    print()

    # Test Case 1c: Goal Not Achieved (Off-topic)
    print("Test 1c: Goal Not Achieved (Off-topic conversation)")
    print("~" * 50)

    offtopic_conversation = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "I need to file a claim for my car accident."},
            {
                "role": "assistant",
                "content": "I can help! But first, have you considered our life insurance products?",
            },
            {"role": "user", "content": "No, I just need help with my car claim."},
            {
                "role": "assistant",
                "content": "Life insurance is really important for your family's financial security. We have great rates!",
            },
            {"role": "user", "content": "This is frustrating. Can someone else help me?"},
        ]
    )

    print(f"Conversation: {len(offtopic_conversation)} messages")
    print("Goal: Customer successfully files car accident claim")
    print()

    offtopic_result = goal_judge.evaluate(
        conversation_history=offtopic_conversation,
        goal="Customer successfully files car accident claim",
    )

    print(f"✗ Score: {offtopic_result.score}/{goal_judge.max_score}")
    print(
        f"✗ Successful: {offtopic_result.details['is_successful']} (threshold: {goal_judge.threshold})"
    )
    print(f"✗ Turn Count: {offtopic_result.details['turn_count']}")
    print(f"✗ Reason: {offtopic_result.details['reason'][:200]}...")
    print()

    # Test Case 1d: Inferred Goal
    print("Test 1d: Inferred Goal (no explicit goal provided)")
    print("~" * 50)

    inferred_conversation = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "What's your refund policy?"},
            {
                "role": "assistant",
                "content": "We offer a 30-day money-back guarantee on all policies.",
            },
            {"role": "user", "content": "Perfect, thank you!"},
        ]
    )

    print(f"Conversation: {len(inferred_conversation)} messages")
    print("Goal: (Inferred from conversation)")
    print()

    inferred_result = goal_judge.evaluate(
        conversation_history=inferred_conversation
        # No goal parameter - judge will infer
    )

    print(f"✓ Score: {inferred_result.score}/{goal_judge.max_score}")
    print(f"✓ Successful: {inferred_result.details['is_successful']}")
    print(f"✓ Turn Count: {inferred_result.details['turn_count']}")
    print(f"✓ Inferred Goal: {inferred_result.details['goal']}")
    print(f"✓ Reason: {inferred_result.details['reason'][:150]}...")
    print()
    print()

    # Example 2: Custom Judge - ToneConsistencyJudge
    print("2. Custom Judge: ToneConsistencyJudge")
    print("-" * 70)

    tone_judge = ToneConsistencyJudge(
        name="professional_tone_judge",
        model=model,
    )

    print(f"Judge: {tone_judge.name}")
    print(f"Base Class: {tone_judge.__class__.__bases__[0].__name__}")
    print(f"Metric Type: {tone_judge.metric_type}")
    print(f"Score Type: {tone_judge.score_type}")
    print()

    # Test with consistent tone
    consistent_conversation = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "Can you help me with my account?"},
            {
                "role": "assistant",
                "content": "Of course! I'd be happy to assist you with your account. What would you like to know?",
            },
            {"role": "user", "content": "How do I reset my password?"},
            {
                "role": "assistant",
                "content": "I can help you reset your password. Please click on 'Forgot Password' on the login page and follow the instructions sent to your email.",
            },
            {"role": "user", "content": "Got it, thanks!"},
            {
                "role": "assistant",
                "content": "You're welcome! Let me know if you need any other assistance.",
            },
        ]
    )

    print(f"Evaluating tone consistency ({len(consistent_conversation)} messages)...")
    print("Expected tone: Professional and friendly")
    print()

    tone_result = tone_judge.evaluate(
        conversation_history=consistent_conversation,
        expected_tone="Professional and friendly",
    )

    print(f"Score: {tone_result.score}")
    print(f"Consistent: {tone_result.details['is_successful']}")
    print(f"Reason: {tone_result.details['reason'][:150]}...")
    print()
    print()

    # Example 3: Testing with inconsistent tone
    print("3. Testing Tone Consistency with Inconsistent Conversation")
    print("-" * 70)

    inconsistent_conversation = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "I need help with billing."},
            {
                "role": "assistant",
                "content": "Good morning! I'd be delighted to assist you with your billing inquiry. How may I help you today?",
            },
            {"role": "user", "content": "Why was I charged twice?"},
            {
                "role": "assistant",
                "content": "Ugh, looks like our system glitched again. Super annoying, right? 😅",
            },
            {"role": "user", "content": "Can you fix it?"},
            {
                "role": "assistant",
                "content": "I sincerely apologize for the inconvenience. I will immediately process a refund for the duplicate charge. You should see it within 3-5 business days.",
            },
        ]
    )

    print(f"Evaluating inconsistent tone ({len(inconsistent_conversation)} messages)...")
    print()

    inconsistent_result = tone_judge.evaluate(
        conversation_history=inconsistent_conversation,
        expected_tone="Consistently professional",
    )

    print(f"Score: {inconsistent_result.score}")
    print(f"Consistent: {inconsistent_result.details['is_successful']}")
    print(f"Reason: {inconsistent_result.details['reason'][:200]}...")
    print()
    print()

    # Example 4: Demonstrating the base ConversationalJudge infrastructure
    print("4. ConversationalJudge Base Class Infrastructure")
    print("-" * 70)
    print()
    print("Both judges inherit these capabilities from ConversationalJudge:")
    print("  ✓ Jinja2 template rendering")
    print("  ✓ Conversation formatting (turn numbering)")
    print("  ✓ Error handling with detailed logging")
    print("  ✓ Validation of conversation inputs")
    print("  ✓ Structured prompt generation")
    print("  ✓ Configuration management (push/pull)")
    print()

    # Show conversation formatting
    sample = ConversationHistory.from_messages(
        [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]
    )

    formatted = goal_judge._format_conversation(sample)
    print("Example formatted conversation:")
    print(formatted)
    print()
    print()

    print("=" * 70)
    print("✓ ConversationalJudge Architecture Working!")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print("  • ConversationalJudge provides base infrastructure")
    print("  • Easy to extend for custom conversational metrics")
    print("  • Consistent architecture across all conversational judges")
    print("  • Built-in template system with conditional defaults")
    print("  • Full integration with SDK metrics ecosystem")
    print()
    print("Future judges can follow the same pattern:")
    print("  - CoherenceJudge: Evaluate conversation coherence")
    print("  - TurnQualityJudge: Evaluate individual turn quality")
    print("  - SafetyJudge: Evaluate conversation safety")
    print("  - and more...")


if __name__ == "__main__":
    main()
