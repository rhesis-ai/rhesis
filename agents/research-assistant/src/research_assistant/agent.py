"""
Research Assistant LangGraph Agent with Composable Tool Calling.

An advanced AI-powered reasoning agent that chains tools together to
navigate data sources, analyze information, and synthesize insights.
"""

from typing import Annotated, Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from research_assistant.tools import ALL_TOOLS

# System prompt for the Research Assistant with tool chaining guidance
COSCIENTIST_SYSTEM_PROMPT = """You are Research Assistant, an advanced AI-powered reasoning agent \
designed to support scientific workflows.

Your role is to act as an "AI colleague" that chains together multiple tools to:
- Navigate structured and unstructured data sources
- Analyze and score data using quantitative methods
- Synthesize actionable insights and recommendations
- Support iterative refinement based on user feedback

## Tool Composition Strategy

Tools are organized in three layers. Chain them together for comprehensive analysis:

### Layer 1: RETRIEVAL (Get raw data)
- `retrieve_safety_data` - Safety/toxicity profiles
- `retrieve_literature` - Publications, patents, reports
- `retrieve_target_info` - Target biology and validation
- `retrieve_compound_data` - Chemical/pharmacological data
- `retrieve_market_data` - Market/competitive intelligence
- `retrieve_patent_data` - IP landscape analysis
- `retrieve_experimental_data` - Assay/experimental results

### Layer 2: ANALYSIS (Process and analyze)
- `analyze_and_score` - Compute scores (druggability, risk, etc.)
- `compare_entities` - Compare multiple options
- `identify_gaps` - Find knowledge gaps
- `filter_and_rank` - Filter and prioritize items
- `compute_routes` - Plan synthesis/development routes
- `extract_insights` - Distill key findings

### Layer 3: SYNTHESIS (Generate outputs)
- `synthesize_report` - Create comprehensive reports
- `generate_recommendations` - Produce actionable recommendations
- `format_output` - Format for specific needs

### Utility Tools
- `update_context` - Refine analysis parameters
- `request_clarification` - Ask user for input
- `save_checkpoint` - Save intermediate state

## Chaining Patterns

Use these patterns for common queries:

**Safety Assessment:**
retrieve_safety_data → analyze_and_score(safety_risk) → extract_insights → generate_recommendations

**Target Prioritization:**
retrieve_target_info (multiple) → compare_entities → filter_and_rank → synthesize_report

**Competitive Analysis:**
retrieve_market_data → retrieve_patent_data → analyze_and_score → synthesize_report

**Knowledge Gap Analysis:**
retrieve_target_info → retrieve_literature → identify_gaps → generate_recommendations(experimental)

**Synthesis Planning:**
retrieve_compound_data → compute_routes → compare_entities (routes) → generate_recommendations

## Guidelines

1. **Start with retrieval**: Always gather relevant data first
2. **Chain logically**: Pass outputs from one tool as inputs to the next
3. **Use analysis tools**: Don't just retrieve - analyze and score
4. **Synthesize at the end**: Combine findings into coherent outputs
5. **Be transparent**: Explain which tools you're using and why
6. **Handle gaps**: If data is missing, use identify_gaps and suggest experiments

When referencing tool outputs in subsequent tool calls, summarize the key data points \
that are relevant for the next analysis step."""


class AgentState(TypedDict):
    """State for the Research Assistant agent."""

    messages: Annotated[list[BaseMessage], add_messages]
    conversation_id: str | None
    tools_called: list[dict[str, Any]]


def create_coscientist_agent(
    model_name: str = "gemini-2.0-flash",
    temperature: float = 0.3,
):
    """
    Create the Research Assistant LangGraph agent with composable tool calling.

    Args:
        model_name: The model to use for the agent
        temperature: Temperature for response generation (lower = more focused)

    Returns:
        Compiled LangGraph graph
    """
    # Create LLM with tools bound
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def should_continue(state: AgentState) -> str:
        """Determine whether to continue with tools or end."""
        messages = state["messages"]
        last_message = messages[-1]

        # If the LLM makes a tool call, route to tools
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        # Otherwise, end
        return "end"

    def reasoning_node(state: AgentState) -> dict:
        """
        Reasoning node that processes user queries and orchestrates tool chains.
        """
        messages = state["messages"]

        # Ensure system prompt is at the start
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=COSCIENTIST_SYSTEM_PROMPT)] + list(messages)

        # Get response from LLM (may include tool calls)
        response = llm_with_tools.invoke(messages)

        return {"messages": [response]}

    def track_tools_node(state: AgentState) -> dict:
        """Track which tools were called."""
        messages = state["messages"]
        tools_called = list(state.get("tools_called", []))

        # Find the last AI message with tool calls
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tools_called.append(
                        {
                            "tool_name": tool_call["name"],
                            "tool_args": tool_call["args"],
                            "tool_layer": get_tool_layer(tool_call["name"]),
                        }
                    )
                break

        return {"tools_called": tools_called}

    # Create tool node
    tool_node = ToolNode(ALL_TOOLS)

    def tools_with_tracking(state: AgentState) -> dict:
        """Execute tools and track which were called."""
        # First track the tools
        tracking_result = track_tools_node(state)

        # Then execute tools
        tool_result = tool_node.invoke(state)

        # Combine results
        return {
            "messages": tool_result["messages"],
            "tools_called": tracking_result["tools_called"],
        }

    # Build the graph
    graph_builder = StateGraph(AgentState)

    # Add nodes
    graph_builder.add_node("reasoning", reasoning_node)
    graph_builder.add_node("tools", tools_with_tracking)

    # Add edges
    graph_builder.add_edge(START, "reasoning")
    graph_builder.add_conditional_edges(
        "reasoning",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )
    graph_builder.add_edge("tools", "reasoning")

    return graph_builder.compile()


def get_tool_layer(tool_name: str) -> str:
    """Get the layer a tool belongs to."""
    retrieval_tools = [
        "retrieve_safety_data",
        "retrieve_literature",
        "retrieve_target_info",
        "retrieve_compound_data",
        "retrieve_market_data",
        "retrieve_patent_data",
        "retrieve_experimental_data",
    ]
    analysis_tools = [
        "analyze_and_score",
        "compare_entities",
        "identify_gaps",
        "filter_and_rank",
        "compute_routes",
        "extract_insights",
    ]
    synthesis_tools = [
        "synthesize_report",
        "generate_recommendations",
        "format_output",
    ]

    if tool_name in retrieval_tools:
        return "retrieval"
    elif tool_name in analysis_tools:
        return "analysis"
    elif tool_name in synthesis_tools:
        return "synthesis"
    else:
        return "utility"


def invoke_agent(
    agent,
    user_message: str,
    conversation_history: list[BaseMessage] | None = None,
    conversation_id: str | None = None,
) -> dict:
    """
    Invoke the Research Assistant agent with a user message.

    Args:
        agent: The compiled LangGraph agent
        user_message: The user's question or message
        conversation_history: Optional list of previous messages for context
        conversation_id: Optional conversation ID for tracking

    Returns:
        Dict with response, tools called (with layers), and conversation history
    """
    # Build messages list
    messages = []

    if conversation_history:
        messages.extend(conversation_history)

    messages.append(HumanMessage(content=user_message))

    # Invoke the agent
    result = agent.invoke(
        {
            "messages": messages,
            "conversation_id": conversation_id,
            "tools_called": [],
        }
    )

    # Extract the response
    response_messages = result["messages"]
    tools_called = result.get("tools_called", [])

    # Find the last AI message that's the final response
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
        "tool_chain": format_tool_chain(tools_called),
        "conversation_id": conversation_id,
    }


def format_tool_chain(tools_called: list[dict]) -> str:
    """Format the tool chain showing the flow between layers."""
    if not tools_called:
        return "No tools called."

    # Group by layer
    layers = {"retrieval": [], "analysis": [], "synthesis": [], "utility": []}
    for tool in tools_called:
        layer = tool.get("tool_layer", "utility")
        layers[layer].append(tool["tool_name"])

    # Build chain representation
    chain_parts = []
    layer_order = ["retrieval", "analysis", "synthesis", "utility"]
    layer_names = {
        "retrieval": "RETRIEVE",
        "analysis": "ANALYZE",
        "synthesis": "SYNTHESIZE",
        "utility": "UTILITY",
    }

    for layer in layer_order:
        if layers[layer]:
            tools_str = ", ".join(layers[layer])
            chain_parts.append(f"[{layer_names[layer]}] {tools_str}")

    return " → ".join(chain_parts) if chain_parts else "No tools called."


def format_tools_called(tools_called: list[dict]) -> str:
    """Format the list of tools called for display."""
    if not tools_called:
        return "No tools were called."

    lines = ["Tools Called:"]
    current_layer = None

    for tool in tools_called:
        layer = tool.get("tool_layer", "utility")
        if layer != current_layer:
            current_layer = layer
            lines.append(f"\n  [{layer.upper()}]")

        lines.append(f"    • {tool['tool_name']}")
        if tool.get("tool_args"):
            for key, value in tool["tool_args"].items():
                str_value = str(value)
                if len(str_value) > 50:
                    str_value = str_value[:47] + "..."
                lines.append(f"        {key}: {str_value}")

    return "\n".join(lines)
