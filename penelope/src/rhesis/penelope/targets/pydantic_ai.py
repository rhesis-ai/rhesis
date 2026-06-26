"""
Pydantic AI target implementation for Penelope.

Simple wrapper for Pydantic AI Agents that makes them testable with
Penelope's autonomous testing agent.
"""

from typing import Any, Dict, List, Optional

from rhesis.sdk.targets import Target, TargetResponse


def _file_to_part(file: Any) -> Any:
    """Build a single Pydantic AI user_prompt part for a file attachment.

    `file` may be a dict with inline base64 `data`, or a `FileReference`
    (object-storage-backed, see `_file_compat.py`). Prefers pre-extracted text
    when available (cheap, no network call); otherwise materializes the raw
    bytes as a BinaryContent part.

    pydantic-ai is an optional dependency, so the import is deferred to call
    time - importing this module must not require pydantic-ai to be installed.
    """
    from rhesis.penelope._file_compat import file_attr, file_bytes_and_type, file_extracted_text

    extracted_text = file_extracted_text(file)
    if extracted_text:
        filename = file_attr(file, "filename", "attachment")
        return f"[Attached file: {filename}]\n{extracted_text}"

    from pydantic_ai import BinaryContent

    data, content_type = file_bytes_and_type(file)
    return BinaryContent(data=data, media_type=content_type)


async def _afile_to_part(file: Any) -> Any:
    """Async sibling of `_file_to_part` - uses FileReference.aread_bytes() so
    materializing object-storage attachments doesn't block the event loop."""
    from rhesis.penelope._file_compat import (
        afile_bytes_and_type,
        file_attr,
        file_extracted_text,
    )

    extracted_text = file_extracted_text(file)
    if extracted_text:
        filename = file_attr(file, "filename", "attachment")
        return f"[Attached file: {filename}]\n{extracted_text}"

    from pydantic_ai import BinaryContent

    data, content_type = await afile_bytes_and_type(file)
    return BinaryContent(data=data, media_type=content_type)


def _files_to_user_prompt(message: str, files: Optional[List[Any]]) -> Any:
    """Build a Pydantic AI user_prompt for `message`, attaching `files` if present.

    Returns the plain `message` string when there are no files, or a list
    mixing the text and file parts when there are.
    """
    if not files:
        return message
    return [message, *(_file_to_part(f) for f in files)]


async def _afiles_to_user_prompt(message: str, files: Optional[List[Any]]) -> Any:
    """Async sibling of `_files_to_user_prompt`."""
    if not files:
        return message
    return [message, *([await _afile_to_part(f) for f in files])]


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
        if not hasattr(self.agent, "run"):
            return False, "Agent must have run() method (Pydantic AI Agent)"
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
            user_prompt = _files_to_user_prompt(message, files)

            result = self.agent.run_sync(user_prompt, message_history=message_history, **kwargs)

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
            user_prompt = await _afiles_to_user_prompt(message, files)

            result = await self.agent.run(user_prompt, message_history=message_history, **kwargs)

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
