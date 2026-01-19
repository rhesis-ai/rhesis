"""Tests for custom observer functionality (create_observer, ObserverBuilder)."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.sdk import decorators
from rhesis.sdk.decorators import ObserverBuilder, create_observer
from rhesis.sdk.decorators import _state as decorators_state
from rhesis.sdk.telemetry.attributes import AIAttributes


class TestCreateObserver:
    """Tests for create_observer function."""

    def test_create_observer_basic(self):
        """Test basic custom observer creation."""
        observer = create_observer("test")

        assert observer is not None
        assert observer._name == "test"
        assert observer._base_attributes == {}

    def test_create_observer_with_base_attributes(self):
        """Test custom observer creation with base attributes."""
        base_attrs = {"service.name": "test-service", "version": "1.0.0"}
        observer = create_observer("test", base_attrs)

        assert observer._name == "test"
        assert observer._base_attributes == base_attrs

    def test_add_method_basic(self):
        """Test adding a basic method to custom observer."""
        observer = create_observer("test")
        observer.add_method("query", "ai.database.query")

        assert hasattr(observer, "query")
        assert callable(getattr(observer, "query"))

    def test_add_method_with_operation_type(self):
        """Test adding method with operation type."""
        observer = create_observer("test")
        observer.add_method("query", "ai.database.query", operation_type="database.query")

        assert hasattr(observer, "query")

    def test_add_method_with_default_attributes(self):
        """Test adding method with default attributes."""
        observer = create_observer("test")
        observer.add_method(
            "query",
            "ai.database.query",
            operation_type="database.query",
            table="default_table",
            timeout=5000,
        )

        assert hasattr(observer, "query")

    def test_add_method_invalid_name_raises_error(self):
        """Test adding method with invalid name raises ValueError."""
        observer = create_observer("test")

        with pytest.raises(ValueError, match="must be a valid Python identifier"):
            observer.add_method("invalid-name", "ai.database.query")

    def test_add_method_duplicate_name_raises_error(self):
        """Test adding duplicate method name raises ValueError."""
        observer = create_observer("test")
        observer.add_method("query", "ai.database.query")

        with pytest.raises(ValueError, match="Method 'query' already exists"):
            observer.add_method("query", "ai.database.query")

    def test_add_method_invalid_span_name_raises_error(self):
        """Test adding method with invalid span name raises ValueError."""
        observer = create_observer("test")

        with pytest.raises(ValueError, match="Invalid span_name"):
            observer.add_method("query", "invalid.span.name")

    def test_add_method_forbidden_domain_raises_error(self):
        """Test adding method with forbidden domain raises ValueError."""
        observer = create_observer("test")

        with pytest.raises(ValueError, match="Invalid span_name"):
            observer.add_method("run", "ai.agent.run")

    def test_add_method_returns_self_for_chaining(self):
        """Test add_method returns self for method chaining."""
        observer = create_observer("test")
        result = observer.add_method("query", "ai.database.query")

        assert result is observer

    def test_method_chaining(self):
        """Test method chaining works correctly."""
        observer = (
            create_observer("test")
            .add_method("query", "ai.database.query")
            .add_method("transaction", "ai.database.transaction")
        )

        assert hasattr(observer, "query")
        assert hasattr(observer, "transaction")

    def test_extend_from_config(self):
        """Test extending observer from configuration dictionary."""
        observer = create_observer("test")
        config = {
            "query": {
                "span_name": "ai.database.query",
                "operation_type": "database.query",
                "default_attributes": {"db.operation": "select"},
            },
            "transaction": {
                "span_name": "ai.database.transaction",
                "operation_type": "database.transaction",
            },
        }

        observer.extend_from_config(config)

        assert hasattr(observer, "query")
        assert hasattr(observer, "transaction")

    def test_extend_from_config_returns_self(self):
        """Test extend_from_config returns self for chaining."""
        observer = create_observer("test")
        config = {"query": {"span_name": "ai.database.query"}}

        result = observer.extend_from_config(config)

        assert result is observer

    def test_custom_method_creates_span(self):
        """Test custom method creates OpenTelemetry span."""
        # Setup mock client with tracer
        mock_client = MagicMock()
        mock_client._tracer.trace_execution = MagicMock(
            side_effect=lambda name, func, args, kwargs, span_name, attrs: func(*args, **kwargs)
        )
        mock_client.is_disabled = False  # Explicitly mark as not disabled

        with patch("rhesis.sdk.decorators._state._default_client", mock_client):
            # Create observer with custom method
            observer = create_observer("test")
            observer.add_method("query", "ai.database.query", operation_type="database.query")

            # Define function with custom decorator
            @observer.query(table="users")
            def test_query():
                return "result"

            # Execute function
            result = test_query()

            assert result == "result"

            # Verify trace_execution was called
            mock_client._tracer.trace_execution.assert_called_once()
            call_args = mock_client._tracer.trace_execution.call_args
            assert call_args[0][4] == "ai.database.query"  # span_name is 5th argument

    def test_attribute_precedence(self):
        """Test attribute precedence: base < default < call-time."""
        # Setup mock client with tracer
        mock_client = MagicMock()
        mock_client._tracer.trace_execution = MagicMock(
            side_effect=lambda name, func, args, kwargs, span_name, attrs: func(*args, **kwargs)
        )
        mock_client.is_disabled = False  # Explicitly mark as not disabled

        with patch("rhesis.sdk.decorators._state._default_client", mock_client):
            # Create observer with base attributes
            observer = create_observer("test", {"env": "prod", "service": "base"})
            observer.add_method(
                "query",
                "ai.database.query",
                operation_type="database.query",
                service="default",  # Should override base
                table="default_table",
            )

            # Define function with call-time attributes
            @observer.query(table="users")  # Should override default
            def test_query():
                return "result"

            # Execute function
            test_query()

            # Verify trace_execution was called with correct attributes
            mock_client._tracer.trace_execution.assert_called_once()
            call_args = mock_client._tracer.trace_execution.call_args
            attributes = call_args[0][5]  # attributes is 6th argument

            # Check precedence: call-time > default > base
            assert attributes["env"] == "prod"  # From base (not overridden)
            assert attributes["service"] == "default"  # Default overrides base
            assert attributes["table"] == "users"  # Call-time overrides default
            assert attributes[AIAttributes.OPERATION_TYPE] == "database.query"


class TestObserverBuilder:
    """Tests for ObserverBuilder class."""

    def test_observer_builder_basic(self):
        """Test basic ObserverBuilder usage."""
        builder = ObserverBuilder("test")

        assert builder.name == "test"
        assert builder.base_attributes == {}
        assert builder.methods == {}

    def test_with_base_attributes(self):
        """Test adding base attributes to builder."""
        builder = ObserverBuilder("test")
        result = builder.with_base_attributes(service="test-service", version="1.0.0")

        assert result is builder  # Returns self for chaining
        assert builder.base_attributes == {"service": "test-service", "version": "1.0.0"}

    def test_add_method_to_builder(self):
        """Test adding method to builder."""
        builder = ObserverBuilder("test")
        result = builder.add_method("query", "ai.database.query", operation_type="database.query")

        assert result is builder  # Returns self for chaining
        assert "query" in builder.methods
        assert builder.methods["query"]["span_name"] == "ai.database.query"
        assert builder.methods["query"]["operation_type"] == "database.query"

    def test_add_method_with_default_attributes(self):
        """Test adding method with default attributes to builder."""
        builder = ObserverBuilder("test")
        builder.add_method(
            "query",
            "ai.database.query",
            operation_type="database.query",
            table="default",
            timeout=5000,
        )

        method_config = builder.methods["query"]
        assert method_config["default_attributes"] == {"table": "default", "timeout": 5000}

    def test_fluent_builder_pattern(self):
        """Test complete fluent builder pattern."""
        observer = (
            ObserverBuilder("api")
            .with_base_attributes(service="api-service", version="2.0.0")
            .add_method("http_call", "ai.api.http", operation_type="api.http")
            .add_method("webhook", "ai.api.webhook", operation_type="api.webhook")
            .build()
        )

        assert observer is not None
        assert observer._name == "api"
        assert observer._base_attributes == {"service": "api-service", "version": "2.0.0"}
        assert hasattr(observer, "http_call")
        assert hasattr(observer, "webhook")

    def test_built_observer_works(self):
        """Test observer built from builder works correctly."""
        # Setup mock client with tracer
        mock_client = MagicMock()
        mock_client._tracer.trace_execution = MagicMock(
            side_effect=lambda name, func, args, kwargs, span_name, attrs: func(*args, **kwargs)
        )
        mock_client.is_disabled = False  # Explicitly mark as not disabled

        with patch("rhesis.sdk.decorators._state._default_client", mock_client):
            # Build observer
            observer = (
                ObserverBuilder("ml")
                .with_base_attributes(framework="pytorch")
                .add_method("train", "ai.ml.train", operation_type="ml.train", phase="training")
                .build()
            )

            # Define function with built observer
            @observer.train(epochs=10)
            def train_model():
                return "trained"

            # Execute function
            result = train_model()

            assert result == "trained"

            # Verify trace_execution was called
            mock_client._tracer.trace_execution.assert_called_once()
            call_args = mock_client._tracer.trace_execution.call_args
            assert call_args[0][4] == "ai.ml.train"  # span_name is 5th argument

            # Verify attributes include base, default, and call-time
            attributes = call_args[0][5]  # attributes is 6th argument

            assert attributes["framework"] == "pytorch"  # Base attribute
            assert attributes["phase"] == "training"  # Default attribute
            assert attributes["epochs"] == 10  # Call-time attribute
            assert attributes[AIAttributes.OPERATION_TYPE] == "ml.train"


class TestCustomObserverIntegration:
    """Integration tests for custom observers."""

    def test_custom_observer_without_client_raises_error(self):
        """Test custom observer raises RuntimeError when client not initialized."""
        # Save current client state and clear it
        original_client = decorators_state._default_client
        decorators_state._default_client = None

        try:
            observer = create_observer("test")
            observer.add_method("query", "ai.database.query")

            @observer.query()
            def test_function():
                return "result"

            # Execute function - should raise RuntimeError
            with pytest.raises(RuntimeError, match="RhesisClient not initialized"):
                test_function()

        finally:
            # Restore original client state
            decorators_state._default_client = original_client

    def test_multiple_custom_observers(self):
        """Test multiple custom observers work independently."""
        # Setup mock client with tracer
        mock_client = MagicMock()
        mock_client._tracer.trace_execution = MagicMock(
            side_effect=lambda name, func, args, kwargs, span_name, attrs: func(*args, **kwargs)
        )
        mock_client.is_disabled = False  # Explicitly mark as not disabled

        with patch("rhesis.sdk.decorators._state._default_client", mock_client):
            # Create multiple observers
            db_observer = create_observer("db", {"service": "db-service"})
            db_observer.add_method("query", "ai.database.query")

            api_observer = create_observer("api", {"service": "api-service"})
            api_observer.add_method("http_call", "ai.api.http")

            # Define functions with different observers
            @db_observer.query(table="users")
            def get_user():
                return "user"

            @api_observer.http_call(method="GET")
            def call_api():
                return "response"

            # Execute functions
            get_user()
            call_api()

            # Verify both traces were executed
            assert mock_client._tracer.trace_execution.call_count == 2

            # Check span names
            call_args_list = mock_client._tracer.trace_execution.call_args_list
            span_names = [call[0][4] for call in call_args_list]  # span_name is 5th argument
            assert "ai.database.query" in span_names
            assert "ai.api.http" in span_names

    def test_custom_observer_docstring_generation(self):
        """Test custom methods have helpful docstrings."""
        observer = create_observer("test")
        observer.add_method(
            "query", "ai.database.query", operation_type="database.query", table="default"
        )

        query_method = getattr(observer, "query")
        docstring = query_method.__doc__

        assert "Convenience decorator for query operations" in docstring
        assert "ai.database.query" in docstring
        assert "database.query" in docstring

    def test_function_span_names_allowed_in_custom_observers(self):
        """Test custom observers can use function.* span names."""
        observer = create_observer("test")
        observer.add_method("process", "function.process_data")

        assert hasattr(observer, "process")

        # Should not raise validation error
        @observer.process()
        def test_function():
            return "result"
