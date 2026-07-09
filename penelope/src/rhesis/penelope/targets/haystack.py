"""
Haystack target implementation for Penelope.

Wraps a Haystack Pipeline so Penelope can run multi-turn conversation tests
against NLP / RAG pipelines.
"""

import asyncio
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

    Multi-component pipelines can route inputs per component socket:

        >>> target = HaystackTarget(
        ...     pipeline,
        ...     "rag-bot",
        ...     input_mapping={"retriever": "query", "prompt_builder": "question"},
        ... )
    """

    def __init__(
        self,
        pipeline: Any,
        target_id: str,
        description: Optional[str] = None,
        input_key: str = "query",
        input_mapping: Optional[Dict[str, str]] = None,
        output_keys: Optional[List[str]] = None,
        history_key: Optional[str] = None,
    ):
        self.pipeline = pipeline
        self._target_id = target_id
        self._description = description or f"Haystack {type(pipeline).__name__}: {target_id}"
        self.input_key = input_key
        self.input_mapping = input_mapping
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

    def _build_run_data(
        self,
        message: str,
        session_key: str,
        *,
        run_inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if run_inputs is not None:
            run_data = dict(run_inputs)
        elif self.input_mapping:
            run_data = {component: {socket: message} for component, socket in self.input_mapping.items()}
        else:
            run_data = {self.input_key: message}

        run_data.update(kwargs)

        if self.history_key:
            history = self._session_histories.setdefault(session_key, [])
            history.append({"role": "user", "content": message})
            run_data[self.history_key] = list(history)

        return run_data

    def _handle_files(self, files: Optional[List]) -> Optional[str]:
        if not files:
            return None
        return "HaystackTarget does not support file attachments; pass document bytes via run_inputs instead."

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        if not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        if files_error := self._handle_files(files):
            return TargetResponse(success=False, content="", error=files_error)

        session_key = conversation_id or "default"
        run_inputs = kwargs.pop("run_inputs", None)
        run_data = self._build_run_data(message, session_key, run_inputs=run_inputs, **kwargs)

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

    async def a_send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        if not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        if files_error := self._handle_files(files):
            return TargetResponse(success=False, content="", error=files_error)

        if not hasattr(self.pipeline, "run_async"):
            return await asyncio.to_thread(
                self.send_message, message, conversation_id, files, **kwargs
            )

        session_key = conversation_id or "default"
        run_inputs = kwargs.pop("run_inputs", None)
        run_data = self._build_run_data(message, session_key, run_inputs=run_inputs, **kwargs)

        try:
            result = await self.pipeline.run_async(run_data)
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
        mapping = (
            f"input_mapping={self.input_mapping}"
            if self.input_mapping
            else f"input_key={self.input_key}"
        )
        return f"""
Target: {self._description}
Type: Haystack {type(self.pipeline).__name__}
Memory: {memory} (history_key={self.history_key or "none"})
Inputs: {mapping}
File attachments: Not supported (use run_inputs for document payloads)

Send messages using send_message_to_target(message, conversation_id).
{"Maintain conversation_id for multi-turn pipeline context." if self.history_key else "Each message is independent unless history_key is configured."}
For multi-component pipelines, configure input_mapping or pass run_inputs={{"component": {{"socket": value}}}}.
"""

    def clear_session(self, session_id: str) -> None:
        """Clear conversation history for a specific session."""
        self._session_histories.pop(session_id, None)
