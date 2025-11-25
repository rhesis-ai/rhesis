"""Function registry for collaborative testing."""

import inspect
import logging
from collections.abc import Callable
from typing import Any

from rhesis.sdk.connector.schemas import FunctionMetadata

logger = logging.getLogger(__name__)


class FunctionRegistry:
    """Manages registered functions and their metadata."""

    def __init__(self):
        """Initialize function registry."""
        self._functions: dict[str, Callable] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    def register(self, name: str, func: Callable, metadata: dict[str, Any]) -> None:
        """
        Register a function.

        Args:
            name: Function name
            func: Function callable
            metadata: Additional metadata
        """
        self._functions[name] = func
        self._metadata[name] = metadata
        logger.info(f"Registered function: {name}")

    def get(self, name: str) -> Callable | None:
        """
        Get a registered function.

        Args:
            name: Function name

        Returns:
            Function callable or None if not found
        """
        return self._functions.get(name)

    def has(self, name: str) -> bool:
        """
        Check if a function is registered.

        Args:
            name: Function name

        Returns:
            True if registered, False otherwise
        """
        return name in self._functions

    def get_all_metadata(self) -> list[FunctionMetadata]:
        """
        Get metadata for all registered functions.

        Returns:
            List of function metadata
        """
        metadata_list = []
        for name, func in self._functions.items():
            signature = self._get_signature(func)
            metadata_list.append(
                FunctionMetadata(
                    name=name,
                    parameters=signature["parameters"],
                    return_type=signature["return_type"],
                    metadata=self._metadata.get(name, {}),
                )
            )
        return metadata_list

    def count(self) -> int:
        """
        Get count of registered functions.

        Returns:
            Number of registered functions
        """
        return len(self._functions)

    def _get_signature(self, func: Callable) -> dict[str, Any]:
        """
        Extract function signature.

        Args:
            func: Function to inspect

        Returns:
            Dictionary with parameters and return type
        """
        sig = inspect.signature(func)

        return {
            "parameters": {
                name: {
                    "type": (
                        str(param.annotation)
                        if param.annotation != inspect.Parameter.empty
                        else "Any"
                    ),
                    "default": (
                        str(param.default) if param.default != inspect.Parameter.empty else None
                    ),
                }
                for name, param in sig.parameters.items()
            },
            "return_type": (
                str(sig.return_annotation)
                if sig.return_annotation != inspect.Signature.empty
                else "Any"
            ),
        }
