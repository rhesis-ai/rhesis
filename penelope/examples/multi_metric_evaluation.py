"""
Example: Using Multiple Metrics with Penelope Agent

This demonstrates how to configure Penelope to evaluate conversations
using multiple SDK metrics simultaneously.
"""

from rhesis.penelope import PenelopeAgent
from rhesis.penelope.targets import EndpointTarget
from rhesis.sdk.metrics.providers.native import GoalAchievementJudge
from rhesis.sdk.metrics.providers.deepeval import DeepEvalTurnRelevancy
from rhesis.sdk.models import VertexAILLM


def example_multiple_metrics():
    """Example: Evaluate conversation with multiple metrics."""
    
    # Initialize model
    model = VertexAILLM(model_name="gemini-2.0-flash")
    
    # Configure multiple metrics for evaluation
    metrics = [
        # Metric 1: Goal Achievement (used for stopping condition)
        GoalAchievementJudge(
            name="goal_achievement",
            description="Evaluates if conversation achieves stated goal",
            model=model,
            threshold=0.7,  # Stop when 70% achieved
        ),
        
        # Metric 2: Turn Relevancy (evaluates conversation coherence)
        DeepEvalTurnRelevancy(
            name="turn_relevancy",
            model=model,
            threshold=0.6,
            window_size=3,  # Look at last 3 turns
        ),
        
        # You can add more metrics here:
        # - Custom safety metrics
        # - Coherence metrics
        # - Toxicity metrics
        # - Any ConversationalMetricBase subclass
    ]
    
    # Initialize Penelope with multiple metrics
    agent = PenelopeAgent(
        model=model,
        metrics=metrics,  # Pass list of metrics
        verbose=True
    )
    
    # Define target
    target = EndpointTarget(
        endpoint_id="customer-support-bot",
        url="https://api.example.com/chat",
    )
    
    # Execute test - all metrics will be evaluated
    result = agent.execute_test(
        target=target,
        goal="Verify chatbot provides accurate refund policy information",
        instructions="Ask about return windows, refund methods, and exceptions",
    )
    
    # Access results - all metrics appear in result.metrics
    print("\n=== Evaluation Results ===")
    for metric_name, metric_data in result.metrics.items():
        print(f"\n{metric_name}:")
        print(f"  Score: {metric_data['score']}")
        print(f"  Successful: {metric_data.get('details', {}).get('is_successful', 'N/A')}")
        
        # Goal Achievement has structured criteria
        if metric_name == "Goal Achievement":
            criteria = metric_data.get("details", {}).get("criteria_evaluations", [])
            if criteria:
                print(f"  Criteria breakdown:")
                for criterion in criteria:
                    status = "✓" if criterion.get("met") else "✗"
                    print(f"    {status} {criterion.get('criterion')}")
    
    return result


def example_single_metric():
    """Example: Default behavior with single metric (backward compatible)."""
    
    model = VertexAILLM(model_name="gemini-2.0-flash")
    
    # If no metrics provided, Penelope uses default GoalAchievementJudge
    agent = PenelopeAgent(model=model)
    
    # Or explicitly provide a single metric
    agent = PenelopeAgent(
        model=model,
        metrics=[
            GoalAchievementJudge(model=model, threshold=0.8)
        ]
    )
    
    target = EndpointTarget(
        endpoint_id="support-bot",
        url="https://api.example.com/chat",
    )
    
    result = agent.execute_test(
        target=target,
        goal="Test basic greeting functionality",
    )
    
    return result


def example_custom_metric():
    """Example: Using custom conversational metric."""
    
    from rhesis.sdk.metrics.conversational import ConversationalJudge
    
    model = VertexAILLM(model_name="gemini-2.0-flash")
    
    # Define custom metric inheriting from ConversationalJudge
    class ToneConsistencyJudge(ConversationalJudge):
        """Evaluates if chatbot maintains consistent tone throughout conversation."""
        
        def __init__(self, model, **kwargs):
            super().__init__(
                evaluation_prompt=(
                    "Evaluate if the assistant maintains a consistent, professional tone "
                    "throughout the conversation. Consider formality, empathy, and language style."
                ),
                evaluation_steps=(
                    "1. Identify the initial tone in first response\n"
                    "2. Compare each subsequent response to the baseline\n"
                    "3. Note any shifts in formality, empathy, or style\n"
                    "4. Determine overall consistency"
                ),
                name="tone_consistency",
                description="Evaluates tone consistency across conversation",
                model=model,
                threshold=0.7,
                **kwargs
            )
    
    # Use custom metric alongside built-in ones
    metrics = [
        GoalAchievementJudge(model=model, threshold=0.7),
        ToneConsistencyJudge(model=model),
    ]
    
    agent = PenelopeAgent(model=model, metrics=metrics)
    
    target = EndpointTarget(
        endpoint_id="support-bot",
        url="https://api.example.com/chat",
    )
    
    result = agent.execute_test(
        target=target,
        goal="Test if chatbot maintains professional tone",
        instructions="Ask various questions with different emotional contexts",
    )
    
    # Both metrics will appear in results
    print(f"Goal Achievement Score: {result.metrics['Goal Achievement']['score']}")
    print(f"Tone Consistency Score: {result.metrics['Tone Consistency']['score']}")
    
    return result


if __name__ == "__main__":
    print("Example 1: Multiple Built-in Metrics")
    print("=" * 50)
    example_multiple_metrics()
    
    print("\n\nExample 2: Single Metric (Default Behavior)")
    print("=" * 50)
    example_single_metric()
    
    print("\n\nExample 3: Custom Metric")
    print("=" * 50)
    example_custom_metric()

