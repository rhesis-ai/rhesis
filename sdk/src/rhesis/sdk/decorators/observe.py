"""ObserveDecorator for function observability with OpenTelemetry."""

import inspect
from collections.abc import Callable
from functools import wraps
from typing import Optional

from ._state import get_default_client, is_client_disabled


class ObserveDecorator:
    """
    Callable class for observing function execution with OpenTelemetry tracing.

    Can be used as:
    - @observe() - General purpose decorator
    - @observe.llm() - Pre-configured for LLM operations
    - @observe.tool() - Pre-configured for tool operations
    - @observe.retrieval() - Pre-configured for retrieval operations

    Supports sync, async, and generator functions with automatic status management.
    """

    def __call__(
        self,
        name: Optional[str] = None,
        span_name: Optional[str] = None,
        **attributes,
    ) -> Callable:
        """
        Observe function execution with OpenTelemetry tracing.

        Use this for functions that need observability but NOT remote testing.
        For functions that need both, use @endpoint (which includes tracing by default).

        Args:
            name: Display name for the operation (defaults to function name)
            span_name: Semantic span name (e.g., 'ai.llm.invoke', 'function.process')
                      Defaults to 'function.<name>'
            **attributes: Additional span attributes

        Returns:
            Decorated function

        Examples:
            from rhesis.sdk import observe

            # Basic usage
            @observe()
            def process_data(input: str) -> str:
                return llm.generate(input)

            # With semantic span name
            @observe(span_name="ai.llm.invoke")
            def call_llm(prompt: str) -> str:
                return openai.chat.completions.create(...)

            # Namespaced methods (pre-configured)
            @observe.llm(provider="openai", model="gpt-4")
            def generate(prompt: str) -> str:
                return llm.generate(prompt)
        """

        def decorator(func: Callable) -> Callable:
            # If client is disabled, return the original function unmodified
            # This completely bypasses all decorator overhead
            if is_client_disabled():
                return func

            func_name = name or func.__name__
            final_span_name = span_name or f"function.{func_name}"

            # Handle async functions
            if inspect.iscoroutinefunction(func):

                @wraps(func)
                async def async_wrapper(*args, **kwargs):
                    _default_client = get_default_client()
                    if _default_client is None:
                        raise RuntimeError(
                            "RhesisClient not initialized. Create a RhesisClient instance "
                            "before using @observe decorator.\n\n"
                            "Example:\n"
                            "    from rhesis.sdk import RhesisClient\n"
                            "    client = RhesisClient(api_key='...', project_id='...')\n"
                        )

                    # Use tracer.trace_execution_async() for consistent I/O capture
                    return await _default_client._tracer.trace_execution_async(
                        func_name, func, args, kwargs, final_span_name, attributes
                    )

                return async_wrapper

            # Handle generator functions
            elif inspect.isgeneratorfunction(func):

                @wraps(func)
                def generator_wrapper(*args, **kwargs):
                    _default_client = get_default_client()
                    if _default_client is None:
                        raise RuntimeError(
                            "RhesisClient not initialized. Create a RhesisClient instance "
                            "before using @observe decorator.\n\n"
                            "Example:\n"
                            "    from rhesis.sdk import RhesisClient\n"
                            "    client = RhesisClient(api_key='...', project_id='...')\n"
                        )

                    # Use tracer.trace_execution() which handles generators via _wrap_generator()
                    # This ensures consistent I/O capture for generators
                    return _default_client._tracer.trace_execution(
                        func_name, func, args, kwargs, final_span_name, attributes
                    )

                return generator_wrapper

            # Handle regular sync functions
            else:

                @wraps(func)
                def sync_wrapper(*args, **kwargs):
                    _default_client = get_default_client()
                    if _default_client is None:
                        raise RuntimeError(
                            "RhesisClient not initialized. Create a RhesisClient instance "
                            "before using @observe decorator.\n\n"
                            "Example:\n"
                            "    from rhesis.sdk import RhesisClient\n"
                            "    client = RhesisClient(api_key='...', project_id='...')\n"
                        )

                    # Use tracer.trace_execution() for consistent I/O capture
                    return _default_client._tracer.trace_execution(
                        func_name, func, args, kwargs, final_span_name, attributes
                    )

                return sync_wrapper

        return decorator

    def llm(
        self,
        provider: str,
        model: str,
        **extra_attributes,
    ) -> Callable:
        """
        Convenience decorator for LLM operations.

        Automatically sets:
        - span_name: "ai.llm.invoke"
        - ai.operation.type: "llm.invoke"
        - ai.model.provider: provider
        - ai.model.name: model

        Also sets a context variable to signal that an LLM observation is active,
        preventing duplicate spans from auto-instrumentation callbacks.

        Args:
            provider: LLM provider (e.g., "openai", "anthropic", "google")
            model: Model name (e.g., "gpt-4", "claude-3-opus")
            **extra_attributes: Additional custom attributes

        Example:
            @observe.llm(provider="openai", model="gpt-4", temperature=0.7)
            def generate(prompt: str) -> str:
                return openai.chat.completions.create(...)
        """
        # Import here to avoid circular imports
        from rhesis.sdk.telemetry.attributes import AIAttributes
        from rhesis.sdk.telemetry.context import set_llm_observation_active
        from rhesis.sdk.telemetry.schemas import AIOperationType

        attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
            AIAttributes.MODEL_PROVIDER: provider,
            AIAttributes.MODEL_NAME: model,
            **extra_attributes,
        }

        # Get the base decorator
        base_decorator = self(span_name=AIOperationType.LLM_INVOKE, **attributes)

        def llm_decorator(func: Callable) -> Callable:
            # Apply the base decorator
            wrapped = base_decorator(func)

            # Wrap again to set/unset the LLM observation context
            if inspect.iscoroutinefunction(func):

                @wraps(func)
                async def async_llm_wrapper(*args, **kwargs):
                    set_llm_observation_active(True)
                    try:
                        return await wrapped(*args, **kwargs)
                    finally:
                        set_llm_observation_active(False)

                return async_llm_wrapper
            else:

                @wraps(func)
                def sync_llm_wrapper(*args, **kwargs):
                    set_llm_observation_active(True)
                    try:
                        return wrapped(*args, **kwargs)
                    finally:
                        set_llm_observation_active(False)

                return sync_llm_wrapper

        return llm_decorator

    def tool(
        self,
        name: str,
        tool_type: str,
        **extra_attributes,
    ) -> Callable:
        """
        Convenience decorator for tool operations.

        Automatically sets:
        - span_name: "ai.tool.invoke"
        - ai.operation.type: "tool.invoke"
        - ai.tool.name: name
        - ai.tool.type: tool_type

        Args:
            name: Tool name (e.g., "weather_api", "calculator")
            tool_type: Tool type (e.g., "http", "function", "database")
            **extra_attributes: Additional custom attributes

        Example:
            @observe.tool(name="weather_api", tool_type="http")
            def get_weather(city: str) -> dict:
                return requests.get(f"api/{city}").json()
        """
        from rhesis.sdk.telemetry.attributes import AIAttributes
        from rhesis.sdk.telemetry.schemas import AIOperationType

        attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE,
            AIAttributes.TOOL_NAME: name,
            AIAttributes.TOOL_TYPE: tool_type,
            **extra_attributes,
        }
        return self(span_name=AIOperationType.TOOL_INVOKE, **attributes)

    def retrieval(
        self,
        backend: str,
        top_k: Optional[int] = None,
        **extra_attributes,
    ) -> Callable:
        """
        Convenience decorator for retrieval operations.

        Automatically sets:
        - span_name: "ai.retrieval"
        - ai.operation.type: "retrieval"
        - ai.retrieval.backend: backend
        - ai.retrieval.top_k: top_k (if provided)

        Args:
            backend: Retrieval backend (e.g., "pinecone", "weaviate", "chroma")
            top_k: Number of results to retrieve (optional)
            **extra_attributes: Additional custom attributes

        Example:
            @observe.retrieval(backend="pinecone", top_k=5)
            def search_docs(query: str) -> list:
                return vector_db.search(query, k=5)
        """
        from rhesis.sdk.telemetry.attributes import AIAttributes
        from rhesis.sdk.telemetry.schemas import AIOperationType

        attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_RETRIEVAL,
            AIAttributes.RETRIEVAL_BACKEND: backend,
            **extra_attributes,
        }
        if top_k is not None:
            attributes[AIAttributes.RETRIEVAL_TOP_K] = top_k

        return self(span_name=AIOperationType.RETRIEVAL, **attributes)

    def embedding(
        self,
        model: str,
        dimensions: Optional[int] = None,
        **extra_attributes,
    ) -> Callable:
        """
        Convenience decorator for embedding generation operations.

        Automatically sets:
        - span_name: "ai.embedding.generate"
        - ai.operation.type: "embedding.create"
        - ai.embedding.model: model
        - ai.embedding.vector.size: dimensions (if provided)

        Args:
            model: Embedding model name (e.g., "text-embedding-ada-002")
            dimensions: Vector dimensions (optional)
            **extra_attributes: Additional custom attributes

        Example:
            @observe.embedding(model="text-embedding-ada-002", dimensions=1536)
            def embed_texts(texts: List[str]) -> List[List[float]]:
                return embedding_model.encode(texts)
        """
        from rhesis.sdk.telemetry.attributes import AIAttributes
        from rhesis.sdk.telemetry.schemas import AIOperationType

        attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_EMBEDDING_CREATE,
            AIAttributes.EMBEDDING_MODEL: model,
            **extra_attributes,
        }
        if dimensions is not None:
            attributes[AIAttributes.EMBEDDING_VECTOR_SIZE] = dimensions

        return self(span_name=AIOperationType.EMBEDDING_GENERATE, **attributes)

    def rerank(
        self,
        model: str,
        top_n: Optional[int] = None,
        **extra_attributes,
    ) -> Callable:
        """
        Convenience decorator for reranking operations.

        Automatically sets:
        - span_name: "ai.rerank"
        - ai.operation.type: "rerank"
        - ai.rerank.model: model
        - ai.rerank.top_n: top_n (if provided)

        Args:
            model: Reranking model name (e.g., "rerank-v1", "cohere-rerank")
            top_n: Number of results to return (optional)
            **extra_attributes: Additional custom attributes

        Example:
            @observe.rerank(model="rerank-v1", top_n=10)
            def rerank_documents(query: str, docs: List[str]) -> List[str]:
                return reranker.rerank(query, docs, top_n=10)
        """
        from rhesis.sdk.telemetry.attributes import AIAttributes
        from rhesis.sdk.telemetry.schemas import AIOperationType

        attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_RERANK,
            AIAttributes.RERANK_MODEL: model,
            **extra_attributes,
        }
        if top_n is not None:
            attributes[AIAttributes.RERANK_TOP_N] = top_n

        return self(span_name=AIOperationType.RERANK, **attributes)

    def evaluation(
        self,
        metric: str,
        evaluator: str,
        **extra_attributes,
    ) -> Callable:
        """
        Convenience decorator for evaluation operations.

        Automatically sets:
        - span_name: "ai.evaluation"
        - ai.operation.type: "evaluation"
        - ai.evaluation.metric: metric
        - ai.evaluation.evaluator: evaluator

        Args:
            metric: Evaluation metric (e.g., "relevance", "faithfulness", "coherence")
            evaluator: Evaluator model/service (e.g., "gpt-4", "claude-3")
            **extra_attributes: Additional custom attributes

        Example:
            @observe.evaluation(metric="relevance", evaluator="gpt-4")
            def evaluate_relevance(query: str, response: str) -> float:
                return evaluator.score_relevance(query, response)
        """
        from rhesis.sdk.telemetry.attributes import AIAttributes
        from rhesis.sdk.telemetry.schemas import AIOperationType

        attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_EVALUATION,
            AIAttributes.EVALUATION_METRIC: metric,
            AIAttributes.EVALUATION_EVALUATOR: evaluator,
            **extra_attributes,
        }

        return self(span_name=AIOperationType.EVALUATION, **attributes)

    def guardrail(
        self,
        guardrail_type: str,
        provider: str,
        **extra_attributes,
    ) -> Callable:
        """
        Convenience decorator for guardrail/safety operations.

        Automatically sets:
        - span_name: "ai.guardrail"
        - ai.operation.type: "guardrail"
        - ai.guardrail.type: guardrail_type
        - ai.guardrail.provider: provider

        Args:
            guardrail_type: Type of guardrail (e.g., "content_safety", "pii_detection", "toxicity")
            provider: Guardrail provider (e.g., "openai", "azure", "custom")
            **extra_attributes: Additional custom attributes

        Example:
            @observe.guardrail(guardrail_type="content_safety", provider="openai")
            def check_content_safety(text: str) -> bool:
                return safety_checker.is_safe(text)
        """
        from rhesis.sdk.telemetry.attributes import AIAttributes
        from rhesis.sdk.telemetry.schemas import AIOperationType

        attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_GUARDRAIL,
            AIAttributes.GUARDRAIL_TYPE: guardrail_type,
            AIAttributes.GUARDRAIL_PROVIDER: provider,
            **extra_attributes,
        }

        return self(span_name=AIOperationType.GUARDRAIL, **attributes)

    def transform(
        self,
        transform_type: str,
        operation: str,
        **extra_attributes,
    ) -> Callable:
        """
        Convenience decorator for data transformation operations.

        Automatically sets:
        - span_name: "ai.transform"
        - ai.operation.type: "transform"
        - ai.transform.type: transform_type
        - ai.transform.operation: operation

        Args:
            transform_type: Type of transformation (e.g., "text", "image", "audio")
            operation: Specific operation (e.g., "clean", "normalize", "tokenize")
            **extra_attributes: Additional custom attributes

        Example:
            @observe.transform(transform_type="text", operation="clean")
            def preprocess_text(text: str) -> str:
                return clean_and_normalize(text)
        """
        from rhesis.sdk.telemetry.attributes import AIAttributes
        from rhesis.sdk.telemetry.schemas import AIOperationType

        attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TRANSFORM,
            AIAttributes.TRANSFORM_TYPE: transform_type,
            AIAttributes.TRANSFORM_OPERATION: operation,
            **extra_attributes,
        }

        return self(span_name=AIOperationType.TRANSFORM, **attributes)


# Create singleton instance
observe = ObserveDecorator()
