"""
LangChain target implementation for Penelope.

Simple wrapper for LangChain Runnables (chains, agents, etc.) that makes them
testable with Penelope's autonomous testing agent.
"""

from typing import Any, Optional

from rhesis.penelope.targets.base import Target, TargetResponse


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
        **kwargs: Any,
    ) -> TargetResponse:
        """Send a message to the LangChain runnable."""
        if not message.strip():
            return TargetResponse(success=False, content="", error="Empty message")

        try:
            # Prepare input for LangChain
            input_data = {self.input_key: message, **kwargs}

            # Handle conversational chains (RunnableWithMessageHistory)
            if hasattr(self.runnable, "get_session_history"):
                config = {"configurable": {"session_id": conversation_id or "default"}}
                response = self.runnable.invoke(input_data, config=config)
            else:
                response = self.runnable.invoke(input_data)

            # Extract content from response
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

        except Exception as e:
            return TargetResponse(
                success=False,
                content="",
                error=f"LangChain error: {str(e)}",
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
