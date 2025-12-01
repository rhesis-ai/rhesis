"""
Database exception handling utilities.

This module provides centralized handling for database constraint violations
and other common database errors to avoid repetition across router files.
"""

import asyncio
import functools
from typing import Callable, Dict, Optional

from fastapi import HTTPException


class DatabaseExceptionHandler:
    """
    Centralized handler for database constraint violations and errors.

    This class provides methods to handle common database errors in a consistent
    way across all routers, reducing code duplication and improving maintainability.
    """

    # Default error messages for common constraint types
    DEFAULT_FOREIGN_KEY_MESSAGE = "Invalid reference in request data"
    DEFAULT_UNIQUE_CONSTRAINT_MESSAGE = "Resource with this identifier already exists"
    DEFAULT_INTERNAL_ERROR_MESSAGE = "Internal server error"

    # Common foreign key field mappings to user-friendly messages
    FOREIGN_KEY_FIELD_MESSAGES = {
        "dimension_id": "Invalid dimension reference",
        "parent_id": "Invalid parent reference",
        "status_id": "Invalid status reference",
        "entity_type_id": "Invalid entity type reference",
        "organization_id": "Invalid organization reference",
        "user_id": "Invalid user reference",
        "model_id": "Invalid model reference",
        "endpoint_id": "Invalid endpoint reference",
        "project_id": "Invalid project reference",
        "test_set_id": "Invalid test set reference",
        "test_id": "Invalid test reference",
        "behavior_id": "Invalid behavior reference",
        "metric_id": "Invalid metric reference",
        "category_id": "Invalid category reference",
        "topic_id": "Invalid topic reference",
        "tag_id": "Invalid tag reference",
    }

    @classmethod
    def handle_database_error(
        self,
        error: Exception,
        entity_name: str = "resource",
        custom_field_messages: Optional[Dict[str, str]] = None,
        custom_unique_message: Optional[str] = None,
    ) -> None:
        """
        Handle database constraint violations and other database errors.

        Args:
            error: The exception that was raised
            entity_name: Name of the entity being operated on (e.g., "demographic", "category")
            custom_field_messages: Custom field-specific error messages
            custom_unique_message: Custom message for unique constraint violations

        Raises:
            HTTPException: With appropriate status code and error message
        """
        error_msg = str(error).lower()

        # Log the original error for debugging
        from rhesis.backend.logging import logger
        logger.error(f"Database error in {entity_name}: {error}", exc_info=True)
        
        # Handle foreign key constraint violations
        if "foreign key constraint" in error_msg or "violates foreign key" in error_msg:
            # Merge custom field messages with defaults
            field_messages = {**self.FOREIGN_KEY_FIELD_MESSAGES}
            if custom_field_messages:
                field_messages.update(custom_field_messages)

            # Check for specific field references in the error message
            for field, message in field_messages.items():
                if field in error_msg:
                    logger.warning(f"Foreign key constraint violation for {field} in {entity_name}")
                    raise HTTPException(status_code=400, detail=message)

            # Generic foreign key error if no specific field found
            logger.warning(f"Generic foreign key constraint violation in {entity_name}")
            raise HTTPException(status_code=400, detail=f"Invalid reference in {entity_name} data")

        # Handle unique constraint violations
        if "unique constraint" in error_msg or "already exists" in error_msg:
            message = (
                custom_unique_message
                or f"{entity_name.capitalize()} with this identifier already exists"
            )
            logger.warning(f"Unique constraint violation in {entity_name}: {message}")
            raise HTTPException(status_code=400, detail=message)

        # Log the original error for debugging
        from rhesis.backend.logging import logger
        logger.error(f"Unhandled database error in {entity_name}: {error}", exc_info=True)
        
        # Handle other database errors as internal server errors
        raise HTTPException(status_code=500, detail=self.DEFAULT_INTERNAL_ERROR_MESSAGE)

    @classmethod
    def handle_crud_operation(
        self,
        operation: Callable,
        entity_name: str = "resource",
        custom_field_messages: Optional[Dict[str, str]] = None,
        custom_unique_message: Optional[str] = None,
        handle_value_error: bool = True,
    ) -> Callable:
        """
        Decorator to wrap CRUD operations with standardized error handling.

        Args:
            operation: The CRUD operation function to wrap
            entity_name: Name of the entity being operated on
            custom_field_messages: Custom field-specific error messages
            custom_unique_message: Custom message for unique constraint violations
            handle_value_error: Whether to handle ValueError exceptions

        Returns:
            The wrapped operation with error handling
        """

        def wrapper(*args, **kwargs):
            try:
                return operation(*args, **kwargs)
            except ValueError as e:
                if handle_value_error:
                    raise HTTPException(status_code=400, detail=str(e))
                raise
            except HTTPException:
                # Re-raise HTTPExceptions (like 404s) without modification
                raise
            except Exception as e:
                self.handle_database_error(
                    e,
                    entity_name=entity_name,
                    custom_field_messages=custom_field_messages,
                    custom_unique_message=custom_unique_message,
                )

        return wrapper


def handle_database_exceptions(
    entity_name: str = "resource",
    custom_field_messages: Optional[Dict[str, str]] = None,
    custom_unique_message: Optional[str] = None,
    handle_value_error: bool = True,
):
    """
    Decorator for handling database exceptions in router endpoints.

    This decorator wraps router endpoint functions to automatically handle
    common database constraint violations and errors. It supports both
    synchronous and asynchronous functions.

    Args:
        entity_name: Name of the entity being operated on (e.g., "demographic")
        custom_field_messages: Custom field-specific error messages
        custom_unique_message: Custom message for unique constraint violations
        handle_value_error: Whether to handle ValueError exceptions

    Usage:
        @handle_database_exceptions(entity_name="demographic")
        def create_demographic(...):
            return crud.create_demographic(...)

        @handle_database_exceptions(entity_name="organization")
        async def create_organization(...):
            return crud.create_organization(...)
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except ValueError as e:
                    if handle_value_error:
                        raise HTTPException(status_code=400, detail=str(e))
                    raise
                except HTTPException:
                    # Re-raise HTTPExceptions (like 404s) without modification
                    raise
                except Exception as e:
                    DatabaseExceptionHandler.handle_database_error(
                        e,
                        entity_name=entity_name,
                        custom_field_messages=custom_field_messages,
                        custom_unique_message=custom_unique_message,
                    )

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except ValueError as e:
                    if handle_value_error:
                        raise HTTPException(status_code=400, detail=str(e))
                    raise
                except HTTPException:
                    # Re-raise HTTPExceptions (like 404s) without modification
                    raise
                except Exception as e:
                    DatabaseExceptionHandler.handle_database_error(
                        e,
                        entity_name=entity_name,
                        custom_field_messages=custom_field_messages,
                        custom_unique_message=custom_unique_message,
                    )

            return sync_wrapper

    return decorator


def with_database_error_handling(
    entity_name: str = "resource",
    custom_field_messages: Optional[Dict[str, str]] = None,
    custom_unique_message: Optional[str] = None,
):
    """
    Context manager for handling database exceptions.

    This can be used as a context manager within router functions for
    more granular control over error handling.

    Args:
        entity_name: Name of the entity being operated on
        custom_field_messages: Custom field-specific error messages
        custom_unique_message: Custom message for unique constraint violations

    Usage:
        with with_database_error_handling(entity_name="demographic"):
            return crud.create_demographic(...)
    """

    class DatabaseErrorContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                return False

            if issubclass(exc_type, ValueError):
                raise HTTPException(status_code=400, detail=str(exc_val))
            elif issubclass(exc_type, HTTPException):
                # Re-raise HTTPExceptions without modification
                return False
            elif issubclass(exc_type, Exception):
                DatabaseExceptionHandler.handle_database_error(
                    exc_val,
                    entity_name=entity_name,
                    custom_field_messages=custom_field_messages,
                    custom_unique_message=custom_unique_message,
                )

            return False

    return DatabaseErrorContext()


class ItemDeletedException(Exception):
    """Raised when trying to access a soft-deleted item."""

    def __init__(
        self, model_name: str, item_id: str, table_name: str = None, item_name: str = None
    ):
        self.model_name = model_name
        self.item_id = item_id
        self.table_name = table_name or model_name.lower()
        self.item_name = item_name
        super().__init__(f"{model_name} with ID {item_id} has been deleted")


class ItemNotFoundException(Exception):
    """Raised when trying to access an item that doesn't exist."""

    def __init__(self, model_name: str, item_id: str, table_name: str = None):
        self.model_name = model_name
        self.item_id = item_id
        self.table_name = table_name or model_name.lower()
        super().__init__(f"{model_name} with ID {item_id} not found")
