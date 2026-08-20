"""
Haystack target implementation for Penelope.

Wraps a Haystack ``Pipeline`` or ``Agent`` so Penelope can drive multi-turn conversations against
it. Haystack is an optional dependency, so nothing here imports it at module level -- the target
duck-types instead, which is also what lets it accept both a pipeline and an agent.
"""

from typing import Any, Dict, List, Optional

from rhesis.sdk.targets import Target, TargetResponse

# Output sockets that plausibly hold a reply, tried in order. Haystack pipelines name their
# components freely, so there is no single correct key -- ``output_component``/``output_key``
# override this when a pipeline puts its answer somewhere unusual.
# ``last_message`` before ``messages``: an Agent returns both, and the former is already the single
# assistant turn worth showing. ``replies`` leads because that is what a ChatGenerator publishes.
_DEFAULT_REPLY_KEYS = (
    "replies",
    "last_message",
    "messages",
    "answers",
    "answer",
    "reply",
    "result",
    "output",
)


_TEXT_ATTRIBUTES = ("text", "data", "answer", "content")


def _message_text(value: Any) -> str:
    """Best-effort text of a Haystack ``ChatMessage``, answer object, or plain value."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        for key in _TEXT_ATTRIBUTES:
            text = value.get(key)
            if isinstance(text, str):
                return text
        return str(value)

    # ChatMessage in 2.x/3.0, and GeneratedAnswer, both expose text-ish attributes. An object that
    # has one returns it even when empty -- falling through to ``str(value)`` there would put an
    # object repr into the transcript, which reads as a real reply.
    for attribute in _TEXT_ATTRIBUTES:
        text = getattr(value, attribute, None)
        if isinstance(text, str):
            return text
    return str(value)


def _first_text(value: Any) -> str:
    """Text of ``value``, or of its last element when it is a non-empty list.

    The *last* element, not the first: a generator returns its newest reply last, and an agent's
    message list ends with the assistant turn worth showing.
    """
    if isinstance(value, (list, tuple)):
        for item in reversed(value):
            text = _message_text(item)
            if text:
                return text
        return ""
    return _message_text(value)


def _extract_reply(result: Any, reply_keys: tuple) -> str:
    """Pull a human-readable reply out of a pipeline or agent result.

    Pipeline results are keyed by component name -- ``{"llm": {"replies": [...]}}`` -- so both the
    mapping itself and each component's output are searched.
    """
    if not isinstance(result, dict):
        return _first_text(result)

    for key in reply_keys:
        if key in result:
            text = _first_text(result[key])
            if text:
                return text

    for component_output in result.values():
        if isinstance(component_output, dict):
            for key in reply_keys:
                if key in component_output:
                    text = _first_text(component_output[key])
                    if text:
                        return text
    return ""


class HaystackTarget(Target):
    """
    Target for Haystack pipelines and agents.

    Accepts either a ``Pipeline`` (invoked as ``pipeline.run({component: {input_key: message}})``)
    or an ``Agent`` (invoked as ``agent.run(messages=[...])``). Conversation history is kept per
    ``conversation_id`` and replayed on each turn, so a multi-turn Penelope run behaves like a real
    conversation rather than a series of unrelated questions.

    Usage:
        >>> from haystack import Pipeline
        >>> target = HaystackTarget(pipeline, "rag-bot", input_component="prompt", input_key="q")
        >>> response = target.send_message("What is Haystack?")

        >>> from haystack.components.agents import Agent
        >>> target = HaystackTarget(agent, "support-agent")
        >>> response = target.send_message("I need help with my order")
    """

    def __init__(
        self,
        pipeline: Any,
        target_id: str,
        description: Optional[str] = None,
        input_component: Optional[str] = None,
        input_key: str = "query",
        output_component: Optional[str] = None,
        output_key: Optional[str] = None,
        reply_keys: Optional[tuple] = None,
    ):
        """
        Initialize the Haystack target.

        Args:
            pipeline: A Haystack ``Pipeline`` or ``Agent`` instance.
            target_id: Unique identifier for this target.
            description: Human-readable description of what this target does.
            input_component: Name of the component the message is fed to. Required for pipelines
                with more than one entry point; ignored for agents.
            input_key: Input socket on ``input_component`` that receives the message.
            output_component: Component whose output holds the reply. Defaults to searching every
                component's output.
            output_key: Output socket holding the reply. Defaults to trying the common names.
            reply_keys: Override the full list of output socket names to try.
        """
        self.pipeline = pipeline
        self._target_id = target_id
        self._description = description or f"Haystack {type(pipeline).__name__}: {target_id}"
        self.input_component = input_component
        self.input_key = input_key
        self.output_component = output_component
        self.output_key = output_key
        self.reply_keys = tuple(reply_keys) if reply_keys else _DEFAULT_REPLY_KEYS
        if output_key:
            # An explicit key wins, but the defaults stay as a fallback.
            self.reply_keys = (output_key, *self.reply_keys)

        # Chat history per conversation, as Haystack ChatMessage objects.
        self._session_histories: Dict[str, List[Any]] = {}

        is_valid, error = self.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid Haystack target: {error}")

    @property
    def target_type(self) -> str:
        return "haystack"

    @property
    def target_id(self) -> str:
        return self._target_id

    @property
    def description(self) -> str:
        return self._description

    @property
    def _is_agent(self) -> bool:
        """Whether the wrapped object is an Agent rather than a Pipeline.

        Detected by shape, not by ``isinstance``: importing ``haystack.components.agents`` here
        would make Haystack a hard dependency of this module.
        """
        return not hasattr(self.pipeline, "add_component")

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """Validate the Haystack target configuration."""
        if self.pipeline is None:
            return False, "pipeline cannot be None"
        if not self._target_id:
            return False, "target_id cannot be empty"
        if not callable(getattr(self.pipeline, "run", None)):
            return False, "pipeline must have a run() method (Haystack Pipeline or Agent)"
        if not self._is_agent and not self.input_component:
            return False, "input_component is required when wrapping a Pipeline"
        return True, None

    def _build_history(self, conversation_id: Optional[str]) -> List[Any]:
        if conversation_id is None:
            return []
        return self._session_histories.setdefault(conversation_id, [])

    def _run_agent(self, message: str, history: List[Any], kwargs: Dict[str, Any]) -> Any:
        from haystack.dataclasses import ChatMessage

        messages = [*history, ChatMessage.from_user(message)]
        return self.pipeline.run(messages=messages, **kwargs)

    def _run_pipeline(self, message: str, kwargs: Dict[str, Any]) -> Any:
        data = {self.input_component: {self.input_key: message}}
        return self.pipeline.run(data, **kwargs)

    def _record_turn(self, conversation_id: Optional[str], message: str, reply: str) -> None:
        if conversation_id is None:
            return
        from haystack.dataclasses import ChatMessage

        history = self._build_history(conversation_id)
        history.append(ChatMessage.from_user(message))
        if reply:
            history.append(ChatMessage.from_assistant(reply))

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """
        Send a message to the Haystack pipeline or agent.

        Args:
            message: The message to send.
            conversation_id: Conversation ID; history is replayed for agents.
            files: Not supported -- Haystack file handling is pipeline-specific, so attachments
                are reported as an error rather than silently dropped.
            **kwargs: Forwarded to ``run()``.

        Returns:
            TargetResponse with the reply text.
        """
        if files:
            return TargetResponse(
                success=False,
                content="",
                conversation_id=conversation_id,
                error=(
                    "HaystackTarget does not support file attachments; how a file reaches a "
                    "pipeline depends on its converters, so it cannot be inferred here."
                ),
            )

        try:
            if self._is_agent:
                history = self._build_history(conversation_id)
                result = self._run_agent(message, history, kwargs)
            else:
                result = self._run_pipeline(message, kwargs)
        except Exception as exc:  # noqa: BLE001 - report failures, do not crash the test run
            return TargetResponse(
                success=False,
                content="",
                conversation_id=conversation_id,
                error=f"{type(exc).__name__}: {exc}",
                metadata={"target_type": self.target_type},
            )

        scoped = result
        if self.output_component and isinstance(result, dict):
            scoped = result.get(self.output_component, result)
        reply = _extract_reply(scoped, self.reply_keys)
        self._record_turn(conversation_id, message, reply)

        return TargetResponse(
            success=True,
            content=reply,
            conversation_id=conversation_id,
            metadata={
                "target_type": self.target_type,
                "is_agent": self._is_agent,
                "output_keys": sorted(result) if isinstance(result, dict) else [],
            },
        )

    def get_tool_documentation(self) -> str:
        kind = "Agent" if self._is_agent else "Pipeline"
        return f"""
Target Type: {self.target_type} ({kind})
Target ID: {self.target_id}
Description: {self.description}

Send messages using send_message_to_target(message, conversation_id).
Maintain conversation_id across turns for conversation continuity.
"""

    def clear_session(self, conversation_id: str) -> None:
        """Forget the stored history for one conversation."""
        self._session_histories.pop(conversation_id, None)
