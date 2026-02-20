"""
Graph construction for the multi-agent Research Assistant system.

This module builds the LangGraph StateGraph that orchestrates the multi-agent
workflow, handling routing, tool execution, and agent handoffs.
"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from research_assistant.agents import (
    create_compound_node,
    create_literature_node,
    create_market_node,
    create_orchestrator_node,
    create_safety_node,
    create_synthesis_node,
    create_target_node,
)
from research_assistant.state import ALL_AGENTS, MultiAgentState
from research_assistant.tools import ANALYSIS_TOOLS, RETRIEVAL_TOOLS, SYNTHESIS_TOOLS, UTILITY_TOOLS
from research_assistant.transfers import TRANSFER_TOOL_TO_AGENT
from research_assistant.utils import format_agent_workflow, format_tool_chain, track_tools_called

# =============================================================================
# ROUTING LOGIC
# =============================================================================


def should_continue_or_handoff(state: MultiAgentState) -> str:
    """
    Determine next step: continue with tools, handoff to another agent, or end.

    Returns:
    - "tools": Execute the tool calls
    - "handoff": Transfer to another agent
    - "end": Finish the workflow
    """
    messages = state["messages"]
    handoff_count = state.get("handoff_count", 0)

    # Guard against infinite loops
    if handoff_count > 20:
        return "end"

    if not messages:
        return "end"

    last_message = messages[-1]

    if not isinstance(last_message, AIMessage):
        return "end"

    if not last_message.tool_calls:
        return "end"

    # Check if any tool call is a transfer tool
    for tool_call in last_message.tool_calls:
        if tool_call["name"] in TRANSFER_TOOL_TO_AGENT:
            return "handoff"

    # Regular tool calls - execute them
    return "tools"


def route_handoff(state: MultiAgentState) -> str:
    """Route to the appropriate agent based on the active_agent set by process_handoff."""
    return state.get("active_agent", "orchestrator")


def route_after_tools(state: MultiAgentState) -> str:
    """Route back to the active agent after tool execution."""
    return state.get("active_agent", "orchestrator")


# =============================================================================
# MAIN GRAPH BUILDER
# =============================================================================


def create_multi_agent_coscientist(
    model_name: str = "gemini-2.0-flash",
    temperature: float = 0.3,
):
    """
    Create the multi-agent Research Assistant system.

    Args:
        model_name: The model to use for agents
        temperature: Temperature for response generation

    Returns:
        Compiled LangGraph graph
    """
    # Create agent nodes using the modular agent factories
    orchestrator_node = create_orchestrator_node(model_name, temperature)
    safety_specialist_node = create_safety_node(model_name, temperature)
    target_specialist_node = create_target_node(model_name, temperature)
    compound_specialist_node = create_compound_node(model_name, temperature)
    literature_specialist_node = create_literature_node(model_name, temperature)
    market_specialist_node = create_market_node(model_name, temperature)
    synthesis_agent_node = create_synthesis_node(model_name, temperature)

    # Create tool node for domain tools (excluding transfer tools)
    all_domain_tools = RETRIEVAL_TOOLS + ANALYSIS_TOOLS + SYNTHESIS_TOOLS + UTILITY_TOOLS
    domain_tool_node = ToolNode(all_domain_tools)

    def execute_tools(state: MultiAgentState) -> dict:
        """Execute non-transfer tools and track them."""
        messages = state["messages"]
        last_message = messages[-1]

        # Get tool calls that are NOT transfer tools
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            non_transfer_calls = [
                tc for tc in last_message.tool_calls if tc["name"] not in TRANSFER_TOOL_TO_AGENT
            ]

            if non_transfer_calls:
                # Execute tools
                result = domain_tool_node.invoke(state)

                # Track tools called
                tools_called = track_tools_called(state, non_transfer_calls)

                return {
                    "messages": result["messages"],
                    "tools_called": tools_called,
                }

        return {"messages": []}

    def process_handoff(state: MultiAgentState) -> dict:
        """Process a handoff, executing any non-transfer tool calls first."""
        messages = state["messages"]
        last_message = messages[-1]
        handoff_count = state.get("handoff_count", 0)

        new_messages = []
        new_active_agent = state.get("active_agent", "orchestrator")
        tools_called = list(state.get("tools_called", []))

        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            transfer_calls = []
            non_transfer_calls = []

            for tool_call in last_message.tool_calls:
                if tool_call["name"] in TRANSFER_TOOL_TO_AGENT:
                    transfer_calls.append(tool_call)
                else:
                    non_transfer_calls.append(tool_call)

            # Execute non-transfer tool calls first so they aren't dropped
            if non_transfer_calls:
                modified_message = AIMessage(
                    content=last_message.content,
                    tool_calls=non_transfer_calls,
                )
                modified_state = {
                    **state,
                    "messages": [*messages[:-1], modified_message],
                }
                result = domain_tool_node.invoke(modified_state)
                new_messages.extend(result["messages"])
                tools_called = track_tools_called(state, non_transfer_calls)

            # Process the first transfer call
            for tool_call in transfer_calls[:1]:
                new_active_agent = TRANSFER_TOOL_TO_AGENT[tool_call["name"]]
                new_messages.append(
                    ToolMessage(
                        content=(f"Successfully transferred to {new_active_agent}"),
                        tool_call_id=tool_call["id"],
                    )
                )

            # Acknowledge any additional transfer calls
            for tool_call in transfer_calls[1:]:
                target = TRANSFER_TOOL_TO_AGENT[tool_call["name"]]
                new_messages.append(
                    ToolMessage(
                        content=(
                            f"Transfer to {target} skipped, "
                            f"already transferring to {new_active_agent}"
                        ),
                        tool_call_id=tool_call["id"],
                    )
                )

        return {
            "messages": new_messages,
            "active_agent": new_active_agent,
            "handoff_count": handoff_count + 1,
            "tools_called": tools_called,
        }

    # Build the graph
    graph_builder = StateGraph(MultiAgentState)

    # Add agent nodes
    graph_builder.add_node("orchestrator", orchestrator_node)
    graph_builder.add_node("safety_specialist", safety_specialist_node)
    graph_builder.add_node("target_specialist", target_specialist_node)
    graph_builder.add_node("compound_specialist", compound_specialist_node)
    graph_builder.add_node("literature_specialist", literature_specialist_node)
    graph_builder.add_node("market_specialist", market_specialist_node)
    graph_builder.add_node("synthesis_agent", synthesis_agent_node)

    # Add tool execution and handoff nodes
    graph_builder.add_node("tools", execute_tools)
    graph_builder.add_node("process_handoff", process_handoff)

    # Entry point - always start with orchestrator
    graph_builder.add_edge(START, "orchestrator")

    # Add conditional edges for each agent
    for agent in ALL_AGENTS:
        graph_builder.add_conditional_edges(
            agent,
            should_continue_or_handoff,
            {
                "tools": "tools",
                "handoff": "process_handoff",
                "end": END,
            },
        )

    # Build routing map for tool and handoff returns
    agent_routing_map = {agent: agent for agent in ALL_AGENTS}

    # After tool execution, return to the active agent
    graph_builder.add_conditional_edges("tools", route_after_tools, agent_routing_map)

    # After handoff processing, route to the new agent
    graph_builder.add_conditional_edges("process_handoff", route_handoff, agent_routing_map)

    return graph_builder.compile()


# =============================================================================
# INVOCATION HELPERS
# =============================================================================


def invoke_multi_agent(
    agent,
    user_message: str,
    conversation_history: list[BaseMessage] | None = None,
    conversation_id: str | None = None,
) -> dict:
    """
    Invoke the multi-agent Research Assistant with a user message.

    Args:
        agent: The compiled multi-agent graph
        user_message: The user's question or message
        conversation_history: Optional list of previous messages
        conversation_id: Optional conversation ID for tracking

    Returns:
        Dict with response, agents involved, tools called, and conversation history
    """
    messages = []

    if conversation_history:
        messages.extend(conversation_history)

    messages.append(HumanMessage(content=user_message))

    # Note: No need to manually pass callbacks - the SDK's auto_instrument("langgraph")
    # automatically patches CompiledGraph.invoke() to inject callbacks transparently
    result = agent.invoke(
        {
            "messages": messages,
            "conversation_id": conversation_id,
            "active_agent": "orchestrator",
            "agent_history": [],
            "tools_called": [],
            "handoff_count": 0,
        },
    )

    # Extract response
    response_messages = result["messages"]
    tools_called = result.get("tools_called", [])
    agent_history = result.get("agent_history", [])

    # Find the final response
    response_text = ""
    for msg in reversed(response_messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            response_text = msg.content
            break
        elif isinstance(msg, AIMessage) and msg.content:
            response_text = msg.content
            break

    return {
        "response": response_text,
        "messages": response_messages,
        "tools_called": tools_called,
        "agents_involved": agent_history,
        "agent_workflow": format_agent_workflow(agent_history),
        "tool_chain": format_tool_chain(tools_called),
        "conversation_id": conversation_id,
    }
