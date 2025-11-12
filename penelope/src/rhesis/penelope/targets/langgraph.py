"""
LangGraph target implementation for Penelope.

Simple wrapper for LangGraph CompiledGraphs that makes them testable
with Penelope's autonomous testing agent.
"""

from typing import Any, Dict, List, Optional

from rhesis.penelope.targets.base import Target, TargetResponse


class LangGraphTarget(Target):
    """
    Simple target for LangGraph CompiledGraphs.

    Works with any LangGraph CompiledGraph using the standard invoke() method.
    Automatically handles message-based state management for conversational agents.

    Usage:
        >>> from langgraph.graph import StateGraph, START, END
        >>> from langchain_google_genai import ChatGoogleGenerativeAI
        >>> from typing_extensions import TypedDict
        >>> from typing import Annotated
        >>> from langgraph.graph.message import add_messages
        >>>
        >>> # Define state
        >>> class State(TypedDict):
        ...     messages: Annotated[list, add_messages]
        >>>
        >>> # Create agent node
        >>> llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
        >>> def agent_node(state):
        ...     response = llm.invoke(state["messages"])
        ...     return {"messages": [response]}
        >>>
        >>> # Build graph
        >>> graph_builder = StateGraph(State)
        >>> graph_builder.add_node("agent", agent_node)
        >>> graph_builder.add_edge(START, "agent")
        >>> graph_builder.add_edge("agent", END)
        >>> graph = graph_builder.compile()
        >>>
        >>> target = LangGraphTarget(graph, "my-agent", "My conversational agent")
        >>> response = target.send_message("Hello!")
    """

    def __init__(
        self,
        graph: Any,
        target_id: str,
        description: Optional[str] = None,
        state_key: str = "messages",
    ):
        """
        Initialize the LangGraph target.

        Args:
            graph: LangGraph CompiledGraph
            target_id: Unique identifier for this target
            description: Human-readable description of what this target does
            state_key: Key name for messages in the graph state (default: "messages")
        """
        self.graph = graph
        self._target_id = target_id
        self._description = description or f"LangGraph {type(graph).__name__}: {target_id}"
        self.state_key = state_key

        # Store conversation state per session
        self._session_states: Dict[str, List] = {}

        # Validate configuration
        is_valid, error = self.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid LangGraph target: {error}")

    @property
    def target_type(self) -> str:
        return "langgraph"

    @property
    def target_id(self) -> str:
        return self._target_id

    @property
    def description(self) -> str:
        return self._description

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """Validate the LangGraph target configuration."""
        if self.graph is None:
            return False, "Graph cannot be None"
        if not self._target_id:
            return False, "target_id cannot be empty"
        if not hasattr(self.graph, "invoke"):
            return False, "Graph must have invoke() method (LangGraph CompiledGraph)"
        return True, None

    def send_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """Send a message to the LangGraph agent."""
        if not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        try:
            # Get or create session state
            session_key = session_id or "default"
            if session_key not in self._session_states:
                self._session_states[session_key] = []

            # Add user message to conversation history
            from langchain_core.messages import HumanMessage

            user_message = HumanMessage(content=message)
            self._session_states[session_key].append(user_message)

            # Prepare state for LangGraph
            state = {self.state_key: self._session_states[session_key], **kwargs}

            # Invoke the graph
            response = self.graph.invoke(state)

            # Extract the latest message from response
            if isinstance(response, dict) and self.state_key in response:
                messages = response[self.state_key]
                if messages:
                    latest_message = messages[-1]
                    # Update session state with all messages from response
                    self._session_states[session_key] = messages

                    # Extract content
                    if hasattr(latest_message, "content"):
                        content = latest_message.content
                        raw_response = {"content": content, "type": type(latest_message).__name__}
                    else:
                        content = str(latest_message)
                        raw_response = str(latest_message)
                else:
                    content = "No response generated"
                    raw_response = response
            else:
                content = str(response)
                raw_response = response

            return TargetResponse(
                success=True,
                content=content,
                session_id=session_id,
                metadata={
                    "input_sent": message,
                    "raw_response": raw_response,
                    "graph_type": type(self.graph).__name__,
                    "session_messages_count": len(self._session_states[session_key]),
                },
            )

        except Exception as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"LangGraph error: {str(e)}",
            )

    def get_tool_documentation(self) -> str:
        """Get documentation for Penelope."""
        return f"""
Target: {self._description}
Type: LangGraph {type(self.graph).__name__}
Memory: Yes (stateful agent with conversation history)

Send messages using send_message_to_target(message, session_id).
Maintain session_id for conversation continuity across multiple turns.
The agent maintains full conversation context automatically.
"""

    def clear_session(self, session_id: str) -> None:
        """
        Clear conversation history for a specific session.

        Args:
            session_id: The session to clear
        """
        if session_id in self._session_states:
            del self._session_states[session_id]
