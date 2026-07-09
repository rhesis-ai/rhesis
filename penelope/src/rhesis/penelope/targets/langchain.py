"""
LangChain target implementation for Penelope.

Simple wrapper for LangChain Runnables (chains, agents, etc.) that makes them
testable with Penelope's autonomous testing agent.
"""

from typing import Any, List, Optional

from rhesis.penelope.targets._content_blocks import (
    afiles_to_content_blocks,
    files_to_content_blocks,
)
from rhesis.sdk.targets import Target, TargetResponse


class LangChainTarget(Target):
    """
    Simple target for LangChain Runnables.

    Works with any LangChain Runnable (chains, agents, etc.) using the standard
    invoke() method from LangChain 1.0+.

    Usage:
        >>> from langchain_google_genai import ChatGoogleGenerativeAI
        >>> from langchain_core.prompts import ChatPromptTemplate
        >>>
        >>> llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
        >>> prompt = ChatPromptTemplate.from_messages([
        ...     ("system", "You are a helpful assistant."),
        ...     ("user", "{input}")
        ... ])
        >>> chain = prompt | llm
        >>>
        >>> target = LangChainTarget(chain, "my-bot", "My chatbot")
        >>> response = target.send_message("Hello!")
    """

    def __init__(
        self,
        runnable: Any,
        target_id: str,
        description: Optional[str] = None,
        input_key: str = "input",
    ):
        """
        Initialize the LangChain target.

        Args:
            runnable: Any LangChain Runnable (chain, agent, etc.)
            target_id: Unique identifier for this target
            description: Human-readable description of what this target does
            input_key: Key name for input in the runnable (default: "input")
        """
        self.runnable = runnable
        self._target_id = target_id
        self._description = description or f"LangChain {type(runnable).__name__}: {target_id}"
        self.input_key = input_key

        # Validate configuration
        is_valid, error = self.validate_configuration()
        if not is_valid:
            raise ValueError(f"Invalid LangChain target: {error}")

    @property
    def target_type(self) -> str:
        return "langchain"

    @property
    def target_id(self) -> str:
        return self._target_id

    @property
    def description(self) -> str:
        return self._description

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        """Validate the LangChain target configuration."""
        if self.runnable is None:
            return False, "Runnable cannot be None"
        if not self._target_id:
            return False, "target_id cannot be empty"
        if not hasattr(self.runnable, "invoke"):
            return False, "Runnable must have invoke() method (LangChain 1.0+ Runnable)"
        return True, None

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """Send a message to the LangChain runnable.

        When `files` is provided, the message is sent as a HumanMessage with
        multimodal content blocks directly (bypassing input_key templating),
        since LangChain prompt templates only substitute strings - a list of
        content blocks would otherwise be stringified into the prompt text
        instead of becoming real attachments. This best-effort path works for
        runnables that accept a message (or list of messages) at the top level,
        e.g. a bare chat model or a MessagesPlaceholder-first prompt; it is not
        guaranteed to work for chains that strictly expect a string under
        input_key.

        Additional **kwargs are intentionally dropped when files are present -
        this is not an oversight. Wrapping the HumanMessage back into
        `{input_key: HumanMessage(...), **kwargs}` does not help: templates
        substitute the input_key value into a string-typed slot regardless of
        its type, so even a HumanMessage gets stringified into the prompt text
        the same way a plain content-block list does. Getting real attachments
        through requires bypassing input_key templating entirely, which is
        fundamentally incompatible with also threading extra template
        variables through **kwargs.
        """
        if not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        try:
            # Prepare input for LangChain
            if files:
                from langchain_core.messages import HumanMessage

                input_data = HumanMessage(content=files_to_content_blocks(message, files))
            else:
                input_data = {self.input_key: message, **kwargs}

            # Handle conversational chains (RunnableWithMessageHistory)
            if hasattr(self.runnable, "get_session_history"):
                config = {"configurable": {"session_id": conversation_id or "default"}}
                response = self.runnable.invoke(input_data, config=config)
            else:
                response = self.runnable.invoke(input_data)

            return self._success_response(response, message, conversation_id)

        except Exception as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"LangChain error: {str(e)}",
            )

    async def a_send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        """Async version of send_message, using the runnable's native ainvoke().

        Every LangChain Runnable exposes ``ainvoke()`` (the Runnable interface
        provides it), so this avoids the base class thread-pool fallback. File
        attachments are materialized with ``aread_bytes()`` so object-storage
        fetches don't block the event loop. The files/kwargs semantics match
        send_message (see its docstring).

        Duck-typed runnables without ``ainvoke()`` (validate_configuration
        only requires ``invoke()``) fall back to the base class thread-pool
        path instead of raising.
        """
        if not hasattr(self.runnable, "ainvoke"):
            return await super().a_send_message(message, conversation_id, files, **kwargs)

        if not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        try:
            if files:
                from langchain_core.messages import HumanMessage

                input_data = HumanMessage(content=await afiles_to_content_blocks(message, files))
            else:
                input_data = {self.input_key: message, **kwargs}

            if hasattr(self.runnable, "get_session_history"):
                config = {"configurable": {"session_id": conversation_id or "default"}}
                response = await self.runnable.ainvoke(input_data, config=config)
            else:
                response = await self.runnable.ainvoke(input_data)

            return self._success_response(response, message, conversation_id)

        except Exception as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"LangChain error: {str(e)}",
            )

    def _success_response(
        self, response: Any, message: str, conversation_id: Optional[str]
    ) -> TargetResponse:
        """Build the TargetResponse for a successful invocation."""
        if hasattr(response, "content"):
            # LangChain message object (AIMessage, etc.)
            content = response.content
            raw_response = {"content": content, "type": type(response).__name__}
        elif isinstance(response, str):
            content = response
            raw_response = response
        else:
            content = str(response)
            raw_response = str(response)

        return TargetResponse(
            success=True,
            content=content,
            conversation_id=conversation_id or "default",
            metadata={
                "input_sent": message,
                "raw_response": raw_response,
                "runnable_type": type(self.runnable).__name__,
            },
        )

    def get_tool_documentation(self) -> str:
        """Get documentation for Penelope."""
        has_memory = hasattr(self.runnable, "get_session_history")

        return f"""
Target: {self._description}
Type: LangChain {type(self.runnable).__name__}
Memory: {"Yes (conversational)" if has_memory else "No (stateless)"}

Send messages using send_message_to_target(message, conversation_id).
{"Maintain conversation_id for continuity." if has_memory else "Each message is independent."}
"""
