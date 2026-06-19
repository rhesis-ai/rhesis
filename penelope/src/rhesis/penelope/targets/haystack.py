"""
Haystack target implementation for Penelope.

Wraps a Haystack Pipeline so Penelope can run multi-turn conversation tests
against NLP / RAG pipelines.
"""

from typing import Any, Dict, List, Optional

from rhesis.sdk.targets import Target, TargetResponse


class HaystackTarget(Target):
    """
    Target for Haystack Pipeline instances.

    Usage:
        >>> from haystack import Pipeline
        >>> pipeline = Pipeline()
        >>> target = HaystackTarget(pipeline, "rag-bot", input_key="query")
        >>> response = target.send_message("What is Haystack?")
    """

    def __init__(
        self,
        pipeline: Any,
        target_id: str,
        description: Optional[str] = None,
        input_key: str = "query",
        output_keys: Optional[List[str]] = None,
        history_key: Optional[str] = None,
    ):
        self.pipeline = pipeline
        self._target_id = target_id
        self._description = description or f"Haystack {type(pipeline).__name__}: {target_id}"
        self.input_key = input_key
        self.output_keys = output_keys or [
            "answer",
            "reply",
            "result",
            "output",
            "generator",
            "llm",
        ]
        self.history_key = history_key
        self._session_histories: Dict[str, List[dict[str, str]]] = {}

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

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        if self.pipeline is None:
            return False, "Pipeline cannot be None"
        if not self._target_id:
            return False, "target_id cannot be empty"
        if not hasattr(self.pipeline, "run"):
            return False, "Pipeline must have run() method"
        return True, None

    def _extract_output(self, result: Any) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            for key in self.output_keys:
                if key not in result:
                    continue
                value = result[key]
                if hasattr(value, "text"):
                    return str(value.text)
                if hasattr(value, "content"):
                    return str(value.content)
                if isinstance(value, str):
                    return value
                if isinstance(value, dict):
                    nested = value.get("replies") or value.get("content")
                    if nested:
                        return str(nested)
                return str(value)
        if hasattr(result, "content"):
            return str(result.content)
        return str(result)

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
        run_data: Dict[str, Any] = {self.input_key: message, **kwargs}

        if self.history_key:
            history = self._session_histories.setdefault(session_key, [])
            history.append({"role": "user", "content": message})
            run_data[self.history_key] = list(history)

        try:
            result = self.pipeline.run(run_data)
            content = self._extract_output(result)

            if self.history_key:
                self._session_histories[session_key].append(
                    {"role": "assistant", "content": content}
                )

            return TargetResponse(
                success=True,
                content=content,
                conversation_id=session_key,
                metadata={
                    "input_sent": message,
                    "raw_response": result if isinstance(result, dict) else str(result),
                    "pipeline_type": type(self.pipeline).__name__,
                },
            )
        except Exception as exc:
            return TargetResponse(
                success=False,
                content="",
                error=f"Haystack error: {exc}",
            )

    def get_tool_documentation(self) -> str:
        memory = "Yes" if self.history_key else "No"
        return f"""
Target: {self._description}
Type: Haystack {type(self.pipeline).__name__}
Memory: {memory} (history_key={self.history_key or "none"})

Send messages using send_message_to_target(message, conversation_id).
{"Maintain conversation_id for multi-turn pipeline context." if self.history_key else "Each message is independent unless history_key is configured."}
"""

    def clear_session(self, session_id: str) -> None:
        """Clear conversation history for a specific session."""
        self._session_histories.pop(session_id, None)
