"""Custom observer builders for domain-specific observability patterns."""

from typing import Optional

from .observe import ObserveDecorator


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
