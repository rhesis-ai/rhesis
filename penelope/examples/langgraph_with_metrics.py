#!/usr/bin/env python3
# ruff: noqa: E402, E501
"""
Penelope + LangGraph + SDK Conversational Metrics Integration Example

This example demonstrates how to:
1. Create LangGraph agents for testing
2. Use Penelope to test the agents with multiple metrics simultaneously
3. Apply both default and custom conversational metrics from the Rhesis SDK
4. Use the default GoalAchievementJudge alongside custom evaluation criteria
5. Show how Penelope automatically evaluates all provided metrics

The example shows how to combine Penelope's autonomous testing capabilities
with multiple SDK conversational evaluation metrics for comprehensive assessment.
"""

import warnings
from typing import List

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

# Suppress Google API warnings
warnings.filterwarnings(
    "ignore", category=FutureWarning, module="google.api_core._python_version_support"
)

# Load environment variables
load_dotenv()

# Penelope imports
from rhesis.penelope import PenelopeAgent
from rhesis.penelope.targets import LangGraphTarget

# SDK imports for conversational metrics
from rhesis.sdk.metrics import ConversationalJudge, GoalAchievementJudge
from rhesis.sdk.models import get_model


class AgentState(TypedDict):
    """State for the LangGraph agent."""

    messages: Annotated[List, add_messages]


def create_customer_service_agent():
    """
    Create a customer service agent using LangGraph.

    This agent is designed to help customers with shipping, returns, and general inquiries.
    """
    # Initialize the LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
    )

    # Create system prompt for customer service
    system_prompt = """You are a helpful customer service assistant for an online retail company.

Your role is to:
- Help customers with shipping inquiries
- Assist with return and refund questions  
- Provide product information and availability
- Handle complaints professionally
- Escalate complex issues when needed

Guidelines:
- Be polite, professional, and empathetic
- Ask clarifying questions when needed
- Provide specific, actionable information
- If you don't know something, say so and offer to find out
- Always try to resolve the customer's issue

You should NOT:
- Make promises about specific delivery dates without checking systems
- Provide medical or legal advice
- Share confidential company information
- Make unauthorized refunds or discounts
"""

    def customer_service_node(state: AgentState):
        """Main customer service processing node."""
        messages = state["messages"]

        # Add system message if this is the first interaction
        if not any(
            msg.content.startswith("You are a helpful customer service")
            for msg in messages
            if hasattr(msg, "content")
        ):
            system_msg = HumanMessage(content=system_prompt)
            messages = [system_msg] + messages

        # Get response from LLM
        response = llm.invoke(messages)
        return {"messages": [response]}

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("customer_service", customer_service_node)

    # Set entry point
    workflow.set_entry_point("customer_service")

    # Add edge to end
    workflow.add_edge("customer_service", END)

    # Compile the graph
    return workflow.compile()


def create_technical_support_agent():
    """
    Create a technical support agent using LangGraph.

    This agent specializes in troubleshooting technical issues.
    """
    # Initialize the LLM
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
    )

    system_prompt = """You are a technical support specialist for a software company.

Your expertise includes:
- Troubleshooting software installation issues
- Helping with configuration problems
- Diagnosing connectivity issues
- Providing step-by-step solutions
- Escalating hardware-related problems

Your approach:
- Ask diagnostic questions to understand the problem
- Provide clear, step-by-step instructions
- Verify solutions work before closing issues
- Document common issues for future reference
- Be patient and explain technical concepts clearly

Limitations:
- Don't provide solutions for unsupported software
- Don't make changes to user systems remotely
- Escalate security-related issues to the security team
"""

    def tech_support_node(state: AgentState):
        """Technical support processing node."""
        messages = state["messages"]

        # Add system context
        if not any("technical support specialist" in str(msg) for msg in messages):
            system_msg = HumanMessage(content=system_prompt)
            messages = [system_msg] + messages

        response = llm.invoke(messages)
        return {"messages": [response]}

    # Create workflow
    workflow = StateGraph(AgentState)
    workflow.add_node("tech_support", tech_support_node)
    workflow.set_entry_point("tech_support")
    workflow.add_edge("tech_support", END)

    return workflow.compile()


# No longer needed - using SDK's GoalAchievementJudge directly in examples


# No longer needed - Penelope handles metrics evaluation automatically


def example_1_customer_service_with_metrics():
    """Test customer service agent with conversational metrics evaluation."""
    print("=" * 70)
    print("EXAMPLE 1: Customer Service Agent with Conversational Metrics")
    print("=" * 70)

    # Create the LangGraph agent
    graph = create_customer_service_agent()

    # Create Penelope target
    target = LangGraphTarget(
        graph=graph,
        target_id="customer-service-agent",
        description="Customer service agent for handling inquiries",
    )

    # Create multiple SDK metrics for comprehensive evaluation

    # Metric 1: Default Goal Achievement Judge (primary metric for stopping condition)
    # Uses SDK's built-in evaluation criteria - no custom prompts
    goal_achievement_judge = GoalAchievementJudge(
        threshold=0.7,  # Stop when 70% achieved
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )

    # Metric 2: Custom Customer Service Quality Metric
    customer_service_quality = ConversationalJudge(
        evaluation_prompt="""
        Evaluate the quality of customer service interaction focusing on professionalism and help.
        
        Key criteria to assess:
        1. **Problem Understanding**: Did the agent correctly understand the customer's issue?
        2. **Communication Style**: Was the agent professional, empathetic, and clear?
        3. **Information Gathering**: Did the agent collect necessary information efficiently?
        4. **Response Quality**: Were responses helpful and actionable?
        5. **Empathy**: Did the agent show understanding and concern for the customer?
        """,
        evaluation_steps="""
        1. Identify the customer's primary issue or request
        2. Analyze how well the agent understood the problem
        3. Evaluate the agent's communication style and professionalism
        4. Assess the quality and helpfulness of responses
        5. Check for empathetic and understanding responses
        6. Assign a score based on overall service quality
        """,
        evaluation_examples="""
        Example - High Score (0.9):
        Customer: "My order is late and I'm frustrated."
        Agent: "I completely understand your frustration about the delayed order. Let me look this up  # noqa: E501
        immediately and see what I can do to help resolve this for you."
        
        Example - Low Score (0.3):
        Customer: "My order is late and I'm frustrated."
        Agent: "Orders sometimes get delayed. What's your order number?"
        """,
        name="customer_service_quality",
        description="Evaluates customer service interaction quality and empathy",
        threshold=0.6,
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )

    # Metric 3: Custom Process Compliance Metric
    process_compliance = ConversationalJudge(
        evaluation_prompt="""
        Evaluate whether the agent follows proper customer service procedures and protocols.
        
        Key criteria:
        1. **Information Collection**: Did the agent ask for necessary details (order, contact)?
        2. **Verification Steps**: Did the agent verify customer identity appropriately?
        3. **Policy Adherence**: Did responses align with standard customer service policies?
        4. **Documentation**: Did the agent indicate proper record-keeping or follow-up?
        5. **Escalation Protocol**: Did the agent know when and how to escalate issues?
        """,
        evaluation_steps="""
        1. Check if agent collected required customer information
        2. Verify if proper identification/verification was attempted
        3. Assess adherence to company policies and procedures
        4. Look for mentions of documentation or case tracking
        5. Evaluate escalation awareness and protocol following
        6. Score based on procedural compliance
        """,
        name="process_compliance",
        description="Evaluates adherence to customer service procedures",
        threshold=0.5,
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )

    # Initialize Penelope with multiple metrics - it handles all evaluation automatically
    agent = PenelopeAgent(
        enable_transparency=True,
        verbose=True,
        max_iterations=6,
        metrics=[
            goal_achievement_judge,  # Default SDK metric (auto-detected for stopping)
            customer_service_quality,  # Custom service quality evaluation
            process_compliance,  # Custom process adherence evaluation
        ],
    )

    # Define the test goal
    goal = "Successfully resolve a shipping inquiry with professional, helpful service"

    # Test the agent - Penelope will automatically evaluate with all metrics
    result = agent.execute_test(
        target=target,
        goal=goal,
        instructions="""
        You are a customer with a shipping concern. Conduct a realistic customer service call:
        1. Start by explaining that your order is late
        2. Provide order details when asked
        3. Ask follow-up questions about the delay
        4. Express concern about the delay
        5. Ask about compensation or next steps
        
        The agent should demonstrate professional customer service throughout.
        """,
    )

    print("\n🎯 Penelope Test Results:")
    print(f"   Status: {result.status}")
    print(f"   Goal Achieved: {'✓' if result.goal_achieved else '✗'}")
    print(f"   Turns Used: {result.turns_used}")
    if result.duration_seconds:
        print(f"   Duration: {result.duration_seconds:.2f}s")
    else:
        print("   Duration: N/A")

    # Display metrics results (automatically computed by Penelope)
    print("\n📊 Metrics Results:")
    for metric_name, metric_data in result.metrics.items():
        score = metric_data.get("score", "N/A")
        print(f"   {metric_name}: {score}")

    return result


def example_2_technical_support_with_metrics():
    """Test technical support agent with conversational metrics evaluation."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Technical Support Agent with Conversational Metrics")
    print("=" * 70)

    # Create the LangGraph agent
    graph = create_technical_support_agent()

    # Create Penelope target
    target = LangGraphTarget(
        graph=graph,
        target_id="tech-support-agent",
        description="Technical support agent for troubleshooting",
    )

    # Create multiple SDK metrics for comprehensive technical support evaluation

    # Metric 1: Default Goal Achievement Judge (primary metric for stopping condition)
    # Uses SDK's built-in evaluation criteria - no custom prompts
    goal_achievement_judge = GoalAchievementJudge(
        threshold=0.7,
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )

    # Metric 2: Custom Technical Competence Metric
    technical_competence = ConversationalJudge(
        evaluation_prompt="""
        Evaluate the technical competence of the support agent in diagnosing and solving problems.
        
        Key criteria:
        1. **Problem Diagnosis**: Did the agent properly diagnose the technical issue?
        2. **Technical Accuracy**: Were the technical solutions appropriate and correct?
        3. **Troubleshooting Method**: Did the agent follow logical troubleshooting steps?
        4. **Knowledge Depth**: Did the agent demonstrate sufficient technical knowledge?
        5. **Solution Effectiveness**: Were the proposed solutions likely to resolve the issue?
        """,
        evaluation_steps="""
        1. Identify the technical problem reported by the user
        2. Assess the accuracy of the agent's diagnosis
        3. Evaluate the technical correctness of proposed solutions
        4. Check if troubleshooting followed logical progression
        5. Assess the depth of technical knowledge demonstrated
        6. Score based on overall technical competence
        """,
        evaluation_examples="""
        Example - High Score (0.9):
        User: "Software won't install, getting error 1603."
        Agent: "Error 1603 typically indicates insufficient permissions or corrupted installer.
        Let's first try running the installer as administrator, then check if Windows Installer service runs."  # noqa: E501
        
        Example - Low Score (0.3):
        User: "Software won't install, getting error 1603."
        Agent: "Try restarting your computer and installing again."
        """,
        name="technical_competence",
        description="Evaluates technical problem-solving ability",
        threshold=0.75,
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )

    # Metric 3: Custom Communication Clarity Metric
    communication_clarity = ConversationalJudge(
        evaluation_prompt="""
        Evaluate how clearly the technical support agent communicates instructions and solutions.
        
        Key criteria:
        1. **Instruction Clarity**: Were technical instructions clear and easy to follow?
        2. **User Guidance**: Did the agent guide the user effectively through steps?
        3. **Verification**: Did the agent check if solutions worked?
        4. **Accessibility**: Were explanations appropriate for the user's technical level?
        5. **Step-by-Step Approach**: Did the agent break down complex tasks into manageable steps?
        """,
        evaluation_steps="""
        1. Assess clarity and specificity of technical instructions
        2. Check if agent provided step-by-step guidance
        3. Look for verification of user understanding and success
        4. Evaluate if explanations matched user's technical level
        5. Score based on overall communication effectiveness
        """,
        name="communication_clarity",
        description="Evaluates clarity of technical communication",
        threshold=0.6,
        model=get_model(provider="gemini", model_name="gemini-2.0-flash"),
    )

    # Initialize Penelope with multiple technical support metrics
    agent = PenelopeAgent(
        enable_transparency=True,
        verbose=True,
        max_iterations=8,
        metrics=[
            goal_achievement_judge,  # Default SDK metric (auto-detected for stopping)
            technical_competence,  # Custom technical skill evaluation
            communication_clarity,  # Custom communication quality evaluation
        ],
    )

    # Define the test goal
    goal = "Successfully troubleshoot a software installation problem with clear, step-by-step help"

    # Test the agent - Penelope handles metric evaluation automatically
    result = agent.execute_test(
        target=target,
        goal=goal,
        instructions="""
        You are a user experiencing a software installation problem. Engage with technical support:
        1. Describe that you're having trouble installing a software application
        2. Provide system details when asked (Windows 10, 8GB RAM, etc.)
        3. Follow troubleshooting steps provided
        4. Report results of each step
        5. Ask clarifying questions if instructions are unclear
        
        The agent should provide clear, methodical technical support.
        """,
    )

    print("\n🎯 Penelope Test Results:")
    print(f"   Status: {result.status}")
    print(f"   Goal Achieved: {'✓' if result.goal_achieved else '✗'}")
    print(f"   Turns Used: {result.turns_used}")
    if result.duration_seconds:
        print(f"   Duration: {result.duration_seconds:.2f}s")
    else:
        print("   Duration: N/A")

    # Display metrics results (automatically computed by Penelope)
    print("\n📊 Metrics Results:")
    for metric_name, metric_data in result.metrics.items():
        score = metric_data.get("score", "N/A")
        print(f"   {metric_name}: {score}")

    return result


def main():
    """Run all examples with conversational metrics evaluation."""
    print("🚀 Penelope + LangGraph + SDK Conversational Metrics Integration")
    print("=" * 70)
    print("This example demonstrates:")
    print("1. Creating LangGraph agents for different domains")
    print("2. Testing agents with Penelope's autonomous testing")
    print("3. Evaluating conversations with SDK conversational metrics")
    print("4. Using custom evaluation criteria and examples")
    print()

    # Check if SDK model is available
    try:
        get_model(provider="gemini", model_name="gemini-2.0-flash")
        print("✅ SDK model connection successful")
    except Exception as e:
        print(f"❌ SDK model connection failed: {e}")
        print("Please ensure your GOOGLE_API_KEY is set in the .env file")
        return

    all_results = []

    # Run Example 1: Customer Service
    try:
        result1 = example_1_customer_service_with_metrics()
        all_results.append(("Customer Service", result1))
    except Exception as e:
        print(f"❌ Example 1 failed: {e}")

    # Run Example 2: Technical Support
    try:
        result2 = example_2_technical_support_with_metrics()
        all_results.append(("Technical Support", result2))
    except Exception as e:
        print(f"❌ Example 2 failed: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("📊 FINAL RESULTS SUMMARY")
    print("=" * 70)

    for name, penelope_result in all_results:
        print(f"\n{name} Agent:")
        duration_str = (
            f"{penelope_result.duration_seconds:.1f}s"
            if penelope_result.duration_seconds
            else "N/A"
        )
        print(
            f"  Penelope: {'✓ Success' if penelope_result.goal_achieved else '✗ Failed'} "
            f"({penelope_result.turns_used} turns, {duration_str})"
        )

        # Display all metrics results
        print("  Metrics:")
        for metric_name, metric_data in penelope_result.metrics.items():
            score = metric_data.get("score", "N/A")
            success = "✓" if isinstance(score, (int, float)) and score >= 0.7 else "✗"
            print(f"    {metric_name}: {score} {success}")

    print("\n🎉 All examples completed!")
    print("\nKey Insights:")
    print("- Penelope provides autonomous testing of LangGraph agents")
    print("- SDK conversational metrics offer sophisticated evaluation")
    print("- Custom judges can be tailored to specific domains")
    print("- Multiple metrics provide comprehensive assessment")


if __name__ == "__main__":
    main()
