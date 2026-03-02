"""
Base agent creation utilities for the multi-agent system.

This module provides factory functions for creating LLM instances and agent nodes
with consistent configuration across all specialists.
"""

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from research_assistant.state import MultiAgentState
from research_assistant.transfers import TRANSFER_TOOL_TO_AGENT


def create_llm_with_tools(
    tools: list,
    model_name: str = "gemini-2.0-flash",
    temperature: float = 0.3,
):
    """Create an LLM with the specified tools bound."""
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
    return llm.bind_tools(tools)


def create_agent_node(
    agent_name: str,
    system_prompt: str,
    tools: list,
    model_name: str = "gemini-2.0-flash",
    temperature: float = 0.3,
):
    """
    Create a node function for a specific agent.

    This factory creates a LangGraph node that:
    - Filters messages appropriately for the agent context
    - Injects the system prompt
    - Invokes the LLM with bound tools
    - Tracks agent history

    Args:
        agent_name: Unique identifier for this agent
        system_prompt: The system prompt defining agent behavior
        tools: List of tools available to this agent
        model_name: LLM model to use
        temperature: Response temperature

    Returns:
        A node function compatible with LangGraph StateGraph
    """
    llm_with_tools = create_llm_with_tools(tools, model_name, temperature)

    def agent_node(state: MultiAgentState) -> dict:
        messages = state["messages"]

        # Filter messages for this agent
        # Remove SystemMessage (we'll add our own)
        # For specialists (non-orchestrator), simplify context after handoff
        filtered_messages = []
        for m in messages:
            if isinstance(m, SystemMessage):
                continue
            # Skip transfer tool calls and responses for cleaner context
            if isinstance(m, ToolMessage) and "transferred" in m.content.lower():
                continue
            if isinstance(m, AIMessage) and m.tool_calls:
                # Check if this is a transfer tool call
                has_transfer = any(tc["name"] in TRANSFER_TOOL_TO_AGENT for tc in m.tool_calls)
                if has_transfer and agent_name != "orchestrator":
                    # For specialists, include the text content but not the tool call
                    if m.content:
                        # Create a simplified message with just the reasoning
                        filtered_messages.append(AIMessage(content=m.content))
                    continue
            filtered_messages.append(m)

        messages_with_prompt = [SystemMessage(content=system_prompt)] + filtered_messages

        response = llm_with_tools.invoke(messages_with_prompt)

        # Track agent history
        agent_history = list(state.get("agent_history", []))
        if agent_name not in agent_history:
            agent_history.append(agent_name)

        return {
            "messages": [response],
            "agent_history": agent_history,
        }

    return agent_node
