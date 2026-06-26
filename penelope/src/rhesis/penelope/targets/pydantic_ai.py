"""
Pydantic AI target implementation for Penelope.

Simple wrapper for Pydantic AI Agents that makes them testable with
Penelope's autonomous testing agent.
"""

from typing import Any, Dict, List, Optional

from rhesis.sdk.targets import Target, TargetResponse


class PydanticAITarget(Target):
    """
    Simple target for Pydantic AI Agents.

    Works with any Pydantic AI Agent using the standard run_sync()/run() methods.
    Maintains conversation history per conversation_id via message_history.

    Usage:
        >>> from pydantic_ai import Agent
        >>>
        >>> agent = Agent("openai:gpt-4o", name="support-bot")
        >>> target = PydanticAITarget(agent, "my-agent", "My support bot")
        >>> response = target.send_message("Hello!")
    """

    def __init__(
        self,
        agent: Any,
        target_id: str,
        description: Optional[str] = None,
    ):
        """
        Initialize the Pydantic AI target.

        Args:
            agent: Pydantic AI Agent instance
            target_id: Unique identifier for this target
            description: Human-readable description of what this target does
        """
        self.agent = agent
        self._target_id = target_id
        self._description = description or f"Pydantic AI Agent: {target_id}"

        # Store message history per conversation
        self._session_histories: Dict[str, List] = {}

        # Validate configuration
        is_valid, error = self.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid Pydantic AI target: {error}")

    @property
    def target_type(self) -> str:
        return "pydantic_ai"

    @property
    def target_id(self) -> str:
        return self._target_id

    @property
    def description(self) -> str:
        return self._description

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """Validate the Pydantic AI target configuration."""
        if self.agent is None:
            return False, "Agent cannot be None"
        if not self._target_id:
            return False, "target_id cannot be empty"
        if not hasattr(self.agent, "run_sync"):
            return False, "Agent must have run_sync() method (Pydantic AI Agent)"
        return True, None

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """Send a message to the Pydantic AI agent."""
        if not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        try:
            session_key = conversation_id or "default"
            message_history = self._session_histories.get(session_key)

            result = self.agent.run_sync(message, message_history=message_history, **kwargs)

            self._session_histories[session_key] = result.all_messages()
            content = str(result.output)

            return TargetResponse(
                success=True,
                content=content,
                conversation_id=session_key,
                metadata={
                    "input_sent": message,
                    "raw_response": content,
                    "agent_type": type(self.agent).__name__,
                    "session_messages_count": len(self._session_histories[session_key]),
                },
            )

        except Exception as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"Pydantic AI error: {str(e)}",
            )

    async def a_send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """Async version of send_message, using the Agent's native async run()."""
        if not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        try:
            session_key = conversation_id or "default"
            message_history = self._session_histories.get(session_key)

            result = await self.agent.run(message, message_history=message_history, **kwargs)

            self._session_histories[session_key] = result.all_messages()
            content = str(result.output)

            return TargetResponse(
                success=True,
                content=content,
                conversation_id=session_key,
                metadata={
                    "input_sent": message,
                    "raw_response": content,
                    "agent_type": type(self.agent).__name__,
                    "session_messages_count": len(self._session_histories[session_key]),
                },
            )

        except Exception as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"Pydantic AI error: {str(e)}",
            )

    def get_tool_documentation(self) -> str:
        """Get documentation for Penelope."""
        return f"""
Target: {self._description}
Type: Pydantic AI {type(self.agent).__name__}
Memory: Yes (conversation history via message_history)

Send messages using send_message_to_target(message, conversation_id).
Maintain conversation_id across turns for conversation continuity.
"""

    def clear_session(self, session_id: str) -> None:
        """
        Clear conversation history for a specific session.

        Args:
            session_id: The session to clear
        """
        if session_id in self._session_histories:
            del self._session_histories[session_id]
