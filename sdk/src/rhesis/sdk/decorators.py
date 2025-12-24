"""Decorators for endpoint registration and observability."""

import inspect
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

if TYPE_CHECKING:
    from rhesis.sdk.client import Client

# Module-level default client (managed transparently)
_default_client: Optional["Client"] = None


def _register_default_client(client: "Client") -> None:  # pyright: ignore[reportUnusedFunction]
    """
    Internal: Automatically register client (called from Client.__init__).

    Args:
        client: Client instance to register
    """
    global _default_client
    _default_client = client


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
            func_name = name or func.__name__
            final_span_name = span_name or f"function.{func_name}"

            # Handle async functions
            if inspect.iscoroutinefunction(func):

                @wraps(func)
                async def async_wrapper(*args, **kwargs):
                    if _default_client is None:
                        raise RuntimeError(
                            "RhesisClient not initialized. Create a RhesisClient instance "
                            "before using @observe decorator.\n\n"
                            "Example:\n"
                            "    from rhesis.sdk import RhesisClient\n"
                            "    client = RhesisClient(api_key='...', project_id='...')\n"
                        )

                    # Extract test execution context (injected by backend during test execution)
                    test_context = kwargs.pop("_rhesis_test_context", None)

                    tracer = trace.get_tracer(__name__)

                    with tracer.start_as_current_span(
                        name=final_span_name,
                        kind=SpanKind.INTERNAL,
                    ) as span:
                        span.set_attribute("function.name", func_name)
                        for key, value in attributes.items():
                            span.set_attribute(key, value)

                        # Inject test execution context as span attributes if present
                        if test_context:
                            span.set_attribute(
                                "rhesis.test.run_id", test_context.get("test_run_id")
                            )
                            span.set_attribute(
                                "rhesis.test.result_id", test_context.get("test_result_id")
                            )
                            span.set_attribute("rhesis.test.id", test_context.get("test_id"))
                            span.set_attribute(
                                "rhesis.test.configuration_id",
                                test_context.get("test_configuration_id"),
                            )

                        try:
                            result = await func(*args, **kwargs)
                            span.set_status(Status(StatusCode.OK))
                            return result
                        except Exception as e:
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                            span.record_exception(e)
                            raise

                return async_wrapper

            # Handle generator functions
            elif inspect.isgeneratorfunction(func):

                @wraps(func)
                def generator_wrapper(*args, **kwargs):
                    if _default_client is None:
                        raise RuntimeError(
                            "RhesisClient not initialized. Create a RhesisClient instance "
                            "before using @observe decorator.\n\n"
                            "Example:\n"
                            "    from rhesis.sdk import RhesisClient\n"
                            "    client = RhesisClient(api_key='...', project_id='...')\n"
                        )

                    # Extract test execution context (injected by backend during test execution)
                    test_context = kwargs.pop("_rhesis_test_context", None)

                    tracer = trace.get_tracer(__name__)

                    with tracer.start_as_current_span(
                        name=final_span_name,
                        kind=SpanKind.INTERNAL,
                    ) as span:
                        span.set_attribute("function.name", func_name)
                        for key, value in attributes.items():
                            span.set_attribute(key, value)

                        # Inject test execution context as span attributes if present
                        if test_context:
                            span.set_attribute(
                                "rhesis.test.run_id", test_context.get("test_run_id")
                            )
                            span.set_attribute(
                                "rhesis.test.result_id", test_context.get("test_result_id")
                            )
                            span.set_attribute("rhesis.test.id", test_context.get("test_id"))
                            span.set_attribute(
                                "rhesis.test.configuration_id",
                                test_context.get("test_configuration_id"),
                            )

                        try:
                            # Yield from the generator
                            generator = func(*args, **kwargs)
                            chunk_count = 0
                            for item in generator:
                                chunk_count += 1
                                yield item

                            # Generator completed successfully
                            span.set_attribute("generator.chunks", chunk_count)
                            span.set_status(Status(StatusCode.OK))
                        except Exception as e:
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                            span.record_exception(e)
                            raise

                return generator_wrapper

            # Handle regular sync functions
            else:

                @wraps(func)
                def sync_wrapper(*args, **kwargs):
                    if _default_client is None:
                        raise RuntimeError(
                            "RhesisClient not initialized. Create a RhesisClient instance "
                            "before using @observe decorator.\n\n"
                            "Example:\n"
                            "    from rhesis.sdk import RhesisClient\n"
                            "    client = RhesisClient(api_key='...', project_id='...')\n"
                        )

                    # Extract test execution context (injected by backend during test execution)
                    test_context = kwargs.pop("_rhesis_test_context", None)

                    tracer = trace.get_tracer(__name__)

                    with tracer.start_as_current_span(
                        name=final_span_name,
                        kind=SpanKind.INTERNAL,
                    ) as span:
                        span.set_attribute("function.name", func_name)
                        for key, value in attributes.items():
                            span.set_attribute(key, value)

                        # Inject test execution context as span attributes if present
                        if test_context:
                            span.set_attribute(
                                "rhesis.test.run_id", test_context.get("test_run_id")
                            )
                            span.set_attribute(
                                "rhesis.test.result_id", test_context.get("test_result_id")
                            )
                            span.set_attribute("rhesis.test.id", test_context.get("test_id"))
                            span.set_attribute(
                                "rhesis.test.configuration_id",
                                test_context.get("test_configuration_id"),
                            )

                        try:
                            result = func(*args, **kwargs)
                            span.set_status(Status(StatusCode.OK))
                            return result
                        except Exception as e:
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                            span.record_exception(e)
                            raise

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
        from rhesis.sdk.telemetry.schemas import AIOperationType

        attributes = {
            AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
            AIAttributes.MODEL_PROVIDER: provider,
            AIAttributes.MODEL_NAME: model,
            **extra_attributes,
        }
        return self(span_name=AIOperationType.LLM_INVOKE, **attributes)

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


def create_observer(
    name: str = "custom",
    base_attributes: Optional[dict] = None,
) -> ObserveDecorator:
    """
    Create a custom ObserveDecorator instance for domain-specific use cases.

    This enables developers to create their own observability decorators with
    custom methods and default attributes, following the pattern:
    `myproject.telemetry.decorators import my_custom_observer`

    Args:
        name: Name for the custom observer (for debugging/logging)
        base_attributes: Default attributes to apply to all spans from this observer

    Returns:
        New ObserveDecorator instance that can be extended with custom methods

    Example:
        # myproject/telemetry/decorators.py
        from rhesis.sdk.decorators import create_observer

        # Create domain-specific observer
        db_observer = create_observer(
            name="database",
            base_attributes={"service.name": "user-service", "db.system": "postgresql"}
        )

        # Add custom methods
        db_observer.add_method("query", "ai.database.query", operation_type="database.query")
        db_observer.add_method(
            "transaction", "ai.database.transaction", operation_type="database.transaction"
        )

        # myproject/services/user.py
        from myproject.telemetry.decorators import db_observer

        @db_observer.query(table="users", operation="select")
        def get_user(user_id: str):
            return db.query("SELECT * FROM users WHERE id = %s", user_id)
    """

    class CustomObserveDecorator(ObserveDecorator):
        def __init__(self):
            super().__init__()
            self._name = name
            self._base_attributes = base_attributes or {}

        def __call__(self, name=None, span_name=None, **attributes):
            # Merge base attributes with provided attributes (provided takes precedence)
            merged_attributes = {**self._base_attributes, **attributes}
            return super().__call__(name=name, span_name=span_name, **merged_attributes)

        def add_method(
            self,
            method_name: str,
            span_name: str,
            operation_type: Optional[str] = None,
            **default_attributes,
        ) -> "CustomObserveDecorator":
            """
            Add a new convenience method to this observer.

            Args:
                method_name: Name of the method to add (e.g., "query", "api_call")
                span_name: Semantic span name for this operation type
                operation_type: Operation type for ai.operation.type attribute (optional)
                **default_attributes: Default attributes for this operation type

            Returns:
                Self for method chaining

            Example:
                db_observer.add_method(
                    "query",
                    "ai.database.query",
                    operation_type="database.query",
                    db_operation="select"
                )

                @db_observer.query(table="users")
                def get_user(user_id: str):
                    return db.get_user(user_id)
            """
            # Validate inputs
            if not method_name.isidentifier():
                raise ValueError(f"method_name '{method_name}' must be a valid Python identifier")

            if hasattr(self, method_name):
                raise ValueError(f"Method '{method_name}' already exists on this observer")

            from rhesis.sdk.telemetry.attributes import validate_span_name

            if not validate_span_name(span_name):
                raise ValueError(
                    f"Invalid span_name '{span_name}'. Must follow 'ai.<domain>.<action>' "
                    "or 'function.<name>' pattern."
                )

            # Create the method dynamically
            def custom_method(**extra_attributes):
                """Dynamically created convenience method."""
                # Merge: base_attributes < default_attributes < extra_attributes
                attributes = {**self._base_attributes, **default_attributes, **extra_attributes}

                if operation_type:
                    from rhesis.sdk.telemetry.attributes import AIAttributes

                    attributes[AIAttributes.OPERATION_TYPE] = operation_type

                return self(span_name=span_name, **attributes)

            # Add helpful docstring
            custom_method.__doc__ = f"""
            Convenience decorator for {method_name} operations.
            
            Automatically sets:
            - span_name: "{span_name}"
            {f'- ai.operation.type: "{operation_type}"' if operation_type else ""}
            {f"- Default attributes: {default_attributes}" if default_attributes else ""}
            
            Example:
                @{self._name}_observer.{method_name}()
                def my_function():
                    pass
            """

            # Bind the method to the instance
            setattr(self, method_name, custom_method)
            return self

        def extend_from_config(self, config: dict) -> "CustomObserveDecorator":
            """
            Add multiple methods from a configuration dictionary.

            Args:
                config: Dictionary mapping method names to their configurations

            Returns:
                Self for method chaining

            Example:
                config = {
                    "query": {
                        "span_name": "ai.database.query",
                        "operation_type": "database.query",
                        "default_attributes": {"db.operation": "select"}
                    },
                    "transaction": {
                        "span_name": "ai.database.transaction",
                        "operation_type": "database.transaction"
                    }
                }
                db_observer.extend_from_config(config)
            """
            for method_name, method_config in config.items():
                span_name = method_config["span_name"]
                operation_type = method_config.get("operation_type")
                default_attributes = method_config.get("default_attributes", {})

                self.add_method(
                    method_name=method_name,
                    span_name=span_name,
                    operation_type=operation_type,
                    **default_attributes,
                )
            return self

    return CustomObserveDecorator()


class ObserverBuilder:
    """
    Builder pattern for creating custom observers with fluent API.

    This provides the most ergonomic way to create domain-specific observers.

    Example:
        # myproject/telemetry/decorators.py
        from rhesis.sdk.decorators import ObserverBuilder

        # Create API observer with fluent interface
        api_observer = (
            ObserverBuilder("api")
            .with_base_attributes(service_name="payment-service", service_version="1.2.0")
            .add_method("http_call", "ai.api.http", operation_type="api.http")
            .add_method("webhook", "ai.api.webhook", operation_type="api.webhook")
            .add_method("graphql", "ai.api.graphql", operation_type="api.graphql")
            .build()
        )

        # myproject/services/payment.py
        from myproject.telemetry.decorators import api_observer

        @api_observer.http_call(method="POST", endpoint="/charges")
        def create_charge(amount: float):
            return stripe.create_charge(amount)

        @api_observer.webhook(event_type="payment.succeeded")
        def handle_payment_webhook(payload: dict):
            return process_payment_success(payload)
    """

    def __init__(self, name: str):
        self.name = name
        self.base_attributes = {}
        self.methods = {}

    def with_base_attributes(self, **attributes) -> "ObserverBuilder":
        """Add base attributes that will be applied to all spans."""
        self.base_attributes.update(attributes)
        return self

    def add_method(
        self,
        method_name: str,
        span_name: str,
        operation_type: Optional[str] = None,
        **default_attributes,
    ) -> "ObserverBuilder":
        """Add a convenience method to the observer."""
        self.methods[method_name] = {
            "span_name": span_name,
            "operation_type": operation_type,
            "default_attributes": default_attributes,
        }
        return self

    def build(self) -> ObserveDecorator:
        """Build and return the configured observer."""
        observer = create_observer(name=self.name, base_attributes=self.base_attributes)
        observer.extend_from_config(self.methods)
        return observer


def endpoint(
    name: str | None = None,
    request_mapping: dict | None = None,
    response_mapping: dict | None = None,
    span_name: str | None = None,
    observe: bool = True,
    **metadata,
) -> Callable:
    """
    Decorator to register functions as Rhesis endpoints with observability.

    This decorator registers functions as remotely callable Rhesis endpoints.
    It enables two features:
    1. OBSERVABILITY (Default On): Traces all executions with OpenTelemetry
    2. REMOTE TESTING: Enables remote triggering from Rhesis platform

    Args:
        name: Optional function name for registration (defaults to function.__name__)
        span_name: Optional semantic span name (e.g., 'ai.llm.invoke', 'ai.tool.invoke')
            Defaults to 'function.<name>' if not provided.
            This allows power users to specify AI operation types for better observability.
        observe: Enable tracing (default: True). Set to False to disable tracing
            while keeping remote testing capability.
        request_mapping: Manual input mappings (Rhesis standard field → function param)
            Maps incoming API request fields to your function's parameters.
            Standard Rhesis REQUEST fields: input, session_id
            Custom fields: Any additional fields in the request are passed through
            Template syntax: Jinja2 ({{ variable_name }})
            Example: {
                "user_message": "{{ input }}",
                "conv_id": "{{ session_id }}",
                "policy_id": "{{ policy_number }}"  # Custom field
            }
        response_mapping: Manual output mappings (function output → Rhesis standard field)
            Maps your function's return value to Rhesis API response fields.
            Standard Rhesis RESPONSE fields: output, context, metadata, tool_calls
            Path syntax: Jinja2 or JSONPath ($.path.to.field)
            Example: {
                "output": "$.result.text",
                "session_id": "$.conv_id",
                "context": "$.sources",
                "metadata": "$.stats"
            }
        **metadata: Additional metadata about the function

    Returns:
        Decorated function

    Examples:
        # Example 1: Auto-mapping (zero config - recommended)
        @endpoint()
        def chat(input: str, session_id: str = None):
            # REQUEST: input, session_id auto-detected
            # RESPONSE: output, session_id auto-extracted
            return {"output": "...", "session_id": session_id}

        # Example 2: Manual mapping with custom naming
        @endpoint(
            request_mapping={
                "user_query": "{{ input }}",      # Standard field
                "conv_id": "{{ session_id }}",    # Standard field
                "docs": "{{ context }}"           # Standard field
            },
            response_mapping={
                "output": "$.result.text",        # Nested output
                "session_id": "$.conv_id",
                "context": "$.sources"
            }
        )
        def chat(user_query: str, conv_id: str = None, docs: list = None):
            return {"result": {"text": "..."}, "conv_id": conv_id, "sources": [...]}

        # Example 3: Custom fields with manual mapping
        @endpoint(
            request_mapping={
                "question": "{{ input }}",
                "policy_id": "{{ policy_number }}",  # Custom field from request
                "tier": "{{ customer_tier }}"        # Custom field from request
            },
            response_mapping={
                "output": "$.answer",
                "metadata": "$.stats"
            }
        )
        def insurance_query(question: str, policy_id: str, tier: str):
            # Custom fields (policy_number, customer_tier) must be in API request
            return {"answer": "...", "stats": {"premium": tier == "gold"}}

        # Example 4: Opt-out of tracing (rare use case)
        @endpoint(observe=False)
        def simple_function(x: int) -> int:
            # Registered for remote testing but NOT traced
            return x * 2

    Field Separation:
        REQUEST fields (function inputs):
        - input: User query/message (required in API request)
        - session_id: Conversation tracking (optional in API request)
        - custom fields: Any additional fields in the API request

        RESPONSE fields (function outputs):
        - output: Main response text (extracted from function return)
        - context: Retrieved documents/sources
        - metadata: Response metadata/stats
        - tool_calls: Available tools/functions
        - session_id: Can also be in response to preserve conversation ID

    Raises:
        RuntimeError: If RhesisClient not initialized before using decorator
    """

    def decorator(func: Callable) -> Callable:
        if _default_client is None:
            raise RuntimeError(
                "RhesisClient not initialized. Create a RhesisClient instance "
                "before using @endpoint decorator."
            )

        func_name = name or func.__name__

        # Include mappings in metadata sent to backend
        enriched_metadata = metadata.copy()
        if request_mapping:
            enriched_metadata["request_mapping"] = request_mapping
        if response_mapping:
            enriched_metadata["response_mapping"] = response_mapping

        # Lazy connector initialization happens here
        _default_client.register_collaborative_function(func_name, func, enriched_metadata)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Conditionally trace based on observe parameter
            if observe and _default_client._connector_manager:
                return _default_client._connector_manager.trace_execution(
                    func_name, func, args, kwargs, span_name
                )
            # Execute without tracing if observe=False or no connector manager
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Backwards compatibility alias
collaborate = endpoint
