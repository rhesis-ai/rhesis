"""
Google ADK target implementation for Penelope.

Wraps a Google ADK Runner (or Agent) so Penelope can run multi-turn conversation
tests against ADK-based agents.
"""

import asyncio
import inspect
from typing import Any, List, Optional

from rhesis.sdk.targets import Target, TargetResponse


class GoogleADKTarget(Target):
    """
    Target for Google ADK Runner or Agent instances.

    Usage:
        >>> from google.adk.runners import Runner
        >>> runner = Runner(agent=my_agent, app_name="my-app", session_service=service)
        >>> target = GoogleADKTarget(runner, "adk-bot", user_id="penelope")
        >>> response = target.send_message("Hello!")
    """

    def __init__(
        self,
        runner: Any = None,
        target_id: str = "",
        description: Optional[str] = None,
        agent: Any = None,
        app_name: str = "penelope",
        user_id: str = "penelope-user",
        session_service: Any = None,
    ):
        self.runner = runner
        self.agent = agent
        self.app_name = app_name
        self.user_id = user_id
        self.session_service = session_service
        self._target_id = target_id
        self._description = description or self._default_description()

        if self.runner is None and self.agent is not None:
            self.runner = self._build_runner_from_agent()

        is_valid, error = self.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid Google ADK target: {error}")

    def _default_description(self) -> str:
        if self.runner is not None:
            return f"Google ADK Runner: {self._target_id or self.app_name}"
        return f"Google ADK Agent: {self._target_id or getattr(self.agent, 'name', 'agent')}"

    def _build_runner_from_agent(self) -> Any:
        from google.adk.runners import Runner

        if self.session_service is None:
            from google.adk.sessions.in_memory_session_service import InMemorySessionService

            self.session_service = InMemorySessionService()

        return Runner(
            agent=self.agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )

    @property
    def target_type(self) -> str:
        return "google_adk"

    @property
    def target_id(self) -> str:
        return self._target_id

    @property
    def description(self) -> str:
        return self._description

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        if self.runner is None:
            return False, "Runner or agent must be provided"
        if not self._target_id:
            return False, "target_id cannot be empty"
        if not hasattr(self.runner, "run"):
            return False, "Runner must have run() method"
        return True, None

    def _build_user_content(self, message: str) -> Any:
        try:
            from google.genai import types

            return types.Content(role="user", parts=[types.Part(text=message)])
        except ImportError:
            return {"role": "user", "parts": [{"text": message}]}

    def _extract_content(self, result: Any) -> str:
        if isinstance(result, str):
            return result
        content = getattr(result, "content", None)
        if content is not None:
            if hasattr(content, "parts") and content.parts:
                part = content.parts[0]
                text = getattr(part, "text", None)
                if text:
                    return str(text)
            return str(content)
        if isinstance(result, dict):
            parts = result.get("parts") or []
            if parts and isinstance(parts[0], dict) and "text" in parts[0]:
                return str(parts[0]["text"])
        return str(result)

    async def _async_send_message(
        self,
        message: str,
        session_id: str,
        **kwargs: Any,
    ) -> TargetResponse:
        user_content = self._build_user_content(message)
        run_kwargs = {
            "user_id": self.user_id,
            "session_id": session_id,
            "new_message": user_content,
            **kwargs,
        }
        result = await self.runner.run(**run_kwargs)
        content = self._extract_content(result)
        return TargetResponse(
            success=True,
            content=content,
            conversation_id=session_id,
            metadata={
                "input_sent": message,
                "raw_response": result if isinstance(result, (str, dict)) else str(result),
                "app_name": self.app_name,
            },
        )

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        if not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        session_id = conversation_id or "default"
        try:
            if inspect.iscoroutinefunction(self.runner.run):
                return asyncio.run(self._async_send_message(message, session_id, **kwargs))
            result = self.runner.run(
                user_id=self.user_id,
                session_id=session_id,
                new_message=self._build_user_content(message),
                **kwargs,
            )
            return TargetResponse(
                success=True,
                content=self._extract_content(result),
                conversation_id=session_id,
                metadata={"input_sent": message, "raw_response": str(result)},
            )
        except Exception as exc:
            return TargetResponse(
                success=False,
                content="",
                error=f"Google ADK error: {exc}",
            )

    def get_tool_documentation(self) -> str:
        return f"""
Target: {self._description}
Type: Google ADK Runner
Memory: Yes (ADK session_id / conversation_id)

Send messages using send_message_to_target(message, conversation_id).
Maintain conversation_id to preserve ADK session context across turns.
"""
