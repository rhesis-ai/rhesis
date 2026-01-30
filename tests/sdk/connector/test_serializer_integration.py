"""Integration tests for TypeSerializer with executor and endpoint decorator."""

import dataclasses

import pytest
from pydantic import BaseModel

from rhesis.sdk.connector.executor import TestExecutor
from rhesis.sdk.connector.serializer import TypeSerializer


# Mock Pydantic types similar to mlflow's ChatAgent types
class ChatAgentMessage(BaseModel):
    """Mock mlflow ChatAgentMessage."""

    id: str
    role: str
    content: str


class ChatAgentRequest(BaseModel):
    """Mock mlflow ChatAgentRequest."""

    messages: list[ChatAgentMessage]


class ChatAgentResponse(BaseModel):
    """Mock mlflow ChatAgentResponse."""

    messages: list[ChatAgentMessage]
    finish_reason: str | None = None


@dataclasses.dataclass
class QueryRequest:
    """Dataclass request type."""

    query: str
    max_results: int = 10


@dataclasses.dataclass
class QueryResponse:
    """Dataclass response type."""

    results: list[str]
    total: int


class TestExecutorWithTypeSerializer:
    """Test executor integration with TypeSerializer."""

    @pytest.fixture
    def executor(self):
        """Create executor instance."""
        return TestExecutor()

    @pytest.mark.asyncio
    async def test_execute_with_pydantic_input(self, executor):
        """Executor constructs Pydantic model from dict input."""

        def agent(request: ChatAgentRequest) -> dict:
            # Verify we received a Pydantic model
            assert isinstance(request, ChatAgentRequest)
            assert isinstance(request.messages[0], ChatAgentMessage)
            return {"output": request.messages[0].content}

        inputs = {
            "request": {
                "messages": [{"id": "1", "role": "user", "content": "Hello"}],
            }
        }

        result = await executor.execute(agent, "agent", inputs)

        assert result["status"] == "success"
        assert result["output"] == {"output": "Hello"}

    @pytest.mark.asyncio
    async def test_execute_with_pydantic_output(self, executor):
        """Executor serializes Pydantic model output."""

        def agent(input: str) -> ChatAgentResponse:
            return ChatAgentResponse(
                messages=[ChatAgentMessage(id="1", role="assistant", content=input)],
                finish_reason="stop",
            )

        inputs = {"input": "Hello"}

        result = await executor.execute(agent, "agent", inputs)

        assert result["status"] == "success"
        assert result["output"] == {
            "messages": [{"id": "1", "role": "assistant", "content": "Hello"}],
            "finish_reason": "stop",
        }

    @pytest.mark.asyncio
    async def test_execute_with_dataclass_input(self, executor):
        """Executor constructs dataclass from dict input."""

        def search(request: QueryRequest) -> dict:
            assert isinstance(request, QueryRequest)
            return {"output": f"Searched: {request.query}"}

        inputs = {"request": {"query": "test", "max_results": 5}}

        result = await executor.execute(search, "search", inputs)

        assert result["status"] == "success"
        assert result["output"] == {"output": "Searched: test"}

    @pytest.mark.asyncio
    async def test_execute_with_dataclass_output(self, executor):
        """Executor serializes dataclass output."""

        def search(query: str) -> QueryResponse:
            return QueryResponse(results=["a", "b", "c"], total=3)

        inputs = {"query": "test"}

        result = await executor.execute(search, "search", inputs)

        assert result["status"] == "success"
        assert result["output"] == {"results": ["a", "b", "c"], "total": 3}

    @pytest.mark.asyncio
    async def test_execute_with_mixed_params(self, executor):
        """Executor handles mixed Pydantic and primitive params."""

        def agent(request: ChatAgentRequest, debug: bool = False, max_tokens: int = 100) -> dict:
            assert isinstance(request, ChatAgentRequest)
            assert isinstance(debug, bool)
            assert isinstance(max_tokens, int)
            return {"debug": debug, "tokens": max_tokens}

        inputs = {
            "request": {"messages": [{"id": "1", "role": "user", "content": "Hi"}]},
            "debug": True,
            "max_tokens": 50,
        }

        result = await executor.execute(agent, "agent", inputs)

        assert result["status"] == "success"
        assert result["output"] == {"debug": True, "tokens": 50}

    @pytest.mark.asyncio
    async def test_execute_backward_compatibility_simple_params(self, executor):
        """Executor maintains backward compatibility with simple params."""

        def simple(message: str, count: int = 1) -> dict:
            return {"message": message, "count": count}

        inputs = {"message": "hello", "count": 5}

        result = await executor.execute(simple, "simple", inputs)

        assert result["status"] == "success"
        assert result["output"] == {"message": "hello", "count": 5}

    @pytest.mark.asyncio
    async def test_execute_backward_compatibility_dict_params(self, executor):
        """Executor maintains backward compatibility with dict params."""

        def with_dict(data: dict) -> dict:
            return {"received": data}

        inputs = {"data": {"key": "value", "nested": {"a": 1}}}

        result = await executor.execute(with_dict, "with_dict", inputs)

        assert result["status"] == "success"
        assert result["output"] == {"received": {"key": "value", "nested": {"a": 1}}}

    @pytest.mark.asyncio
    async def test_execute_backward_compatibility_no_type_hints(self, executor):
        """Executor maintains backward compatibility with untyped params."""

        def untyped(message, count=1):
            return {"message": message, "count": count}

        inputs = {"message": "hello", "count": 5}

        result = await executor.execute(untyped, "untyped", inputs)

        assert result["status"] == "success"
        assert result["output"] == {"message": "hello", "count": 5}

    @pytest.mark.asyncio
    async def test_execute_with_custom_serializers(self, executor):
        """Executor uses function-specific custom serializers."""

        class CustomResponse:
            def __init__(self, text: str):
                self.text = text

        def agent(input: str) -> CustomResponse:
            return CustomResponse(text=f"Response: {input}")

        custom_serializers = {CustomResponse: {"dump": lambda r: {"custom_output": r.text}}}

        inputs = {"input": "Hello"}

        result = await executor.execute(agent, "agent", inputs, serializers=custom_serializers)

        assert result["status"] == "success"
        assert result["output"] == {"custom_output": "Response: Hello"}

    @pytest.mark.asyncio
    async def test_execute_with_nested_pydantic_output(self, executor):
        """Executor serializes nested Pydantic models in output."""

        def agent(input: str) -> ChatAgentResponse:
            return ChatAgentResponse(
                messages=[
                    ChatAgentMessage(id="1", role="user", content=input),
                    ChatAgentMessage(id="2", role="assistant", content=f"Echo: {input}"),
                ],
                finish_reason="stop",
            )

        inputs = {"input": "Hello"}

        result = await executor.execute(agent, "agent", inputs)

        assert result["status"] == "success"
        assert len(result["output"]["messages"]) == 2
        assert result["output"]["messages"][0]["content"] == "Hello"
        assert result["output"]["messages"][1]["content"] == "Echo: Hello"


class TestExecutorAsyncFunctions:
    """Test executor with async functions and type serialization."""

    @pytest.fixture
    def executor(self):
        """Create executor instance."""
        return TestExecutor()

    @pytest.mark.asyncio
    async def test_async_with_pydantic_input_output(self, executor):
        """Async functions work with Pydantic input/output."""

        async def async_agent(request: ChatAgentRequest) -> ChatAgentResponse:
            user_msg = request.messages[0].content
            return ChatAgentResponse(
                messages=[ChatAgentMessage(id="1", role="assistant", content=f"Hi: {user_msg}")]
            )

        inputs = {
            "request": {"messages": [{"id": "1", "role": "user", "content": "Hello"}]},
        }

        result = await executor.execute(async_agent, "async_agent", inputs)

        assert result["status"] == "success"
        assert result["output"]["messages"][0]["content"] == "Hi: Hello"


class TestTypeSerializerPrepareInputs:
    """Test _prepare_inputs method directly."""

    def test_prepare_inputs_constructs_pydantic(self):
        """_prepare_inputs constructs Pydantic from dict."""
        executor = TestExecutor()
        serializer = TypeSerializer()

        def func(request: ChatAgentRequest):
            pass

        inputs = {"request": {"messages": [{"id": "1", "role": "user", "content": "Hi"}]}}

        prepared = executor._prepare_inputs(func, inputs, serializer)

        assert "request" in prepared
        assert isinstance(prepared["request"], ChatAgentRequest)

    def test_prepare_inputs_passes_primitives(self):
        """_prepare_inputs passes primitives unchanged."""
        executor = TestExecutor()
        serializer = TypeSerializer()

        def func(message: str, count: int):
            pass

        inputs = {"message": "hello", "count": 42}

        prepared = executor._prepare_inputs(func, inputs, serializer)

        assert prepared["message"] == "hello"
        assert prepared["count"] == 42

    def test_prepare_inputs_skips_missing(self):
        """_prepare_inputs skips parameters not in inputs."""
        executor = TestExecutor()
        serializer = TypeSerializer()

        def func(message: str, optional: str = "default"):
            pass

        inputs = {"message": "hello"}

        prepared = executor._prepare_inputs(func, inputs, serializer)

        assert prepared == {"message": "hello"}
        assert "optional" not in prepared


class TestEndToEndScenarios:
    """Test realistic end-to-end scenarios."""

    @pytest.fixture
    def executor(self):
        """Create executor instance."""
        return TestExecutor()

    @pytest.mark.asyncio
    async def test_mlflow_style_agent(self, executor):
        """Test mlflow-style agent with ChatAgentRequest/Response."""

        def mlflow_agent(request: ChatAgentRequest) -> ChatAgentResponse:
            """Simulates an mlflow ChatAgent."""
            user_content = request.messages[-1].content
            return ChatAgentResponse(
                messages=[
                    ChatAgentMessage(
                        id="response-1",
                        role="assistant",
                        content=f"You said: {user_content}",
                    )
                ],
                finish_reason="stop",
            )

        # Simulate what the SDK receives after request_mapping
        inputs = {
            "request": {
                "messages": [{"id": "msg-1", "role": "user", "content": "What is AI?"}],
            }
        }

        result = await executor.execute(mlflow_agent, "mlflow_agent", inputs)

        assert result["status"] == "success"
        assert result["output"]["messages"][0]["content"] == "You said: What is AI?"
        assert result["output"]["finish_reason"] == "stop"

    @pytest.mark.asyncio
    async def test_search_agent_with_dataclass(self, executor):
        """Test search agent with dataclass types."""

        def search_agent(request: QueryRequest) -> QueryResponse:
            """Simulates a search endpoint."""
            return QueryResponse(
                results=[f"Result for: {request.query}"],
                total=1,
            )

        inputs = {"request": {"query": "python tutorials", "max_results": 5}}

        result = await executor.execute(search_agent, "search_agent", inputs)

        assert result["status"] == "success"
        assert result["output"]["results"] == ["Result for: python tutorials"]
        assert result["output"]["total"] == 1

    @pytest.mark.asyncio
    async def test_hybrid_agent_pydantic_and_primitives(self, executor):
        """Test agent with both Pydantic and primitive params."""

        def hybrid_agent(
            request: ChatAgentRequest,
            temperature: float = 0.7,
            max_tokens: int = 100,
        ) -> ChatAgentResponse:
            """Agent with configuration params."""
            return ChatAgentResponse(
                messages=[
                    ChatAgentMessage(
                        id="1",
                        role="assistant",
                        content=f"temp={temperature}, max={max_tokens}",
                    )
                ]
            )

        inputs = {
            "request": {"messages": [{"id": "1", "role": "user", "content": "Hi"}]},
            "temperature": 0.5,
            "max_tokens": 200,
        }

        result = await executor.execute(hybrid_agent, "hybrid_agent", inputs)

        assert result["status"] == "success"
        assert "temp=0.5" in result["output"]["messages"][0]["content"]
        assert "max=200" in result["output"]["messages"][0]["content"]
