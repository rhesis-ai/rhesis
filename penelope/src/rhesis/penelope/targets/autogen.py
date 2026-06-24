"""
AutoGen target implementation for Penelope.

Wraps an AutoGen ConversableAgent or AssistantAgent so Penelope can run
multi-turn conversation tests against AutoGen-based agents.
"""

from typing import Any, Dict, List, Optional

from rhesis.sdk.targets import Target, TargetResponse


class AutoGenTarget(Target):
    """
    Target for AutoGen ConversableAgent / AssistantAgent instances.

    Maintains per-conversation message history and calls generate_reply()
    for each Penelope turn.

    Usage:
        >>> from autogen import AssistantAgent
        >>> agent = AssistantAgent(name="assistant", llm_config={"config_list": [...]})
        >>> target = AutoGenTarget(agent, "support-bot", "Customer support agent")
        >>> response = target.send_message("Hello!")
    """

    def __init__(
        self,
        agent: Any,
        target_id: str,
        description: Optional[str] = None,
    ):
        self.agent = agent
        self._target_id = target_id
        self._description = description or (
            f"AutoGen {type(agent).__name__}: {getattr(agent, 'name', target_id)}"
        )
        self._session_histories: Dict[str, List[dict[str, str]]] = {}

        is_valid, error = self.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid AutoGen target: {error}")

    @property
    def target_type(self) -> str:
        return "autogen"

    @property
    def target_id(self) -> str:
        return self._target_id

    @property
    def description(self) -> str:
        return self._description

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        if self.agent is None:
            return False, "Agent cannot be None"
        if not self._target_id:
            return False, "target_id cannot be empty"
        if not hasattr(self.agent, "generate_reply"):
            return False, "Agent must have generate_reply() method"
        return True, None

    def _extract_content(self, reply: Any) -> str:
        if isinstance(reply, str):
            return reply
        if isinstance(reply, dict):
            content = reply.get("content")
            if isinstance(content, str):
                return content
        if hasattr(reply, "content"):
            return str(reply.content)
        return str(reply)

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        if not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        session_key = conversation_id or "default"

        if files:
            return TargetResponse(
                success=False,
                content="",
                error="AutoGenTarget does not support file attachments",
                conversation_id=session_key,
            )

        history = self._session_histories.setdefault(session_key, [])
        history.append({"role": "user", "content": message})

        try:
            reply = self.agent.generate_reply(messages=list(history), **kwargs)
            content = self._extract_content(reply)
            history.append({"role": "assistant", "content": content})

            return TargetResponse(
                success=True,
                content=content,
                conversation_id=session_key,
                metadata={
                    "input_sent": message,
                    "raw_response": reply if isinstance(reply, (str, dict)) else str(reply),
                    "agent_name": getattr(self.agent, "name", type(self.agent).__name__),
                    "session_messages_count": len(history),
                },
            )
        except Exception as exc:
            if history and history[-1].get("role") == "user":
                history.pop()
            return TargetResponse(
                success=False,
                content="",
                error=f"AutoGen error: {exc}",
                conversation_id=session_key,
            )

    def get_tool_documentation(self) -> str:
        agent_name = getattr(self.agent, "name", type(self.agent).__name__)
        return f"""
Target: {self._description}
Type: AutoGen {type(self.agent).__name__} ({agent_name})
Memory: Yes (conversation history per conversation_id)

Send messages using send_message_to_target(message, conversation_id).
Maintain conversation_id for multi-turn continuity across agent turns.
"""

    def clear_session(self, session_id: str) -> None:
        """Clear conversation history for a specific session."""
        self._session_histories.pop(session_id, None)
