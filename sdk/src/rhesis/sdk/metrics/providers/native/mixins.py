"""Mixins for native judge metrics.

This module provides common functionality for judge metrics through mixins:
- SerializationMixin: Methods for serialization (to_config, from_config, etc.)
- BackendSyncMixin: Methods for backend synchronization (push, pull)
"""

import inspect
from dataclasses import asdict
from typing import Any, Dict, Optional, TypeVar

from rhesis.sdk.client import Client, Endpoints, Methods
from rhesis.sdk.metrics.base import MetricConfig
from rhesis.sdk.metrics.utils import backend_config_to_sdk_config, sdk_config_to_backend_config

T = TypeVar("T")


class SerializationMixin:
    """Mixin providing serialization methods for judge metrics."""

    config: MetricConfig  # Expected to be set by the class using this mixin

    def __repr__(self) -> str:
        """String representation of the metric."""
        return str(self.to_config())

    def to_config(self) -> MetricConfig:
        """
        Convert the metric to a MetricConfig.

        Note: Subclasses should override this method to add their own parameters.

        Returns:
            MetricConfig: The metric configuration
        """
        return self.config

    @classmethod
    def from_config(cls: type[T], config: MetricConfig) -> T:
        """
        Create a metric from a config object.

        Args:
            config: Metric configuration

        Returns:
            T: Metric instance

        Raises:
            ValueError: If config is invalid
        """
        # Get __init__ parameter names automatically
        init_params = inspect.signature(cls.__init__).parameters
        config_dict = asdict(config)

        # Only pass parameters that __init__ accepts
        filtered_params = {k: v for k, v in config_dict.items() if k in init_params}

        return cls(**filtered_params)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the metric to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the metric
        """
        return asdict(self.to_config())

    @classmethod
    def from_dict(cls: type[T], config: Dict[str, Any]) -> T:
        """
        Create a metric from a dictionary.

        Note: Subclasses should override this method to handle their specific config types.

        Args:
            config: Dictionary configuration

        Returns:
            T: Metric instance

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses should override this method")


class BackendSyncMixin:
    """Mixin providing backend sync methods for judge metrics."""

    config: MetricConfig  # Expected to be set by the class using this mixin

    def push(self) -> None:
        """
        Push the metric to the backend.

        Raises:
            Exception: If push fails
        """
        client = Client()
        config = asdict(self.to_config())
        config = sdk_config_to_backend_config(config)

        client.send_request(Endpoints.METRICS, Methods.POST, config)

    @classmethod
    def pull(cls: type[T], name: Optional[str] = None, nano_id: Optional[str] = None) -> T:
        """
        Pull the metric from the backend.

        Either 'name' or 'nano_id' must be provided to pull a metric from the backend.
        If 'name' is not unique (i.e., multiple metrics share the same name), an error
        will be raised and you will be asked to use 'nano_id' instead for disambiguation.

        Args:
            name: The name of the metric
            nano_id: The nano_id of the metric

        Returns:
            T: The metric instance

        Raises:
            ValueError: If neither name nor nano_id is provided
            ValueError: If no metric found or multiple metrics found with same name
            ValueError: If metric class doesn't match
        """
        if not name and not nano_id:
            raise ValueError("Either name or nano_id must be provided")

        client = Client()

        # Build filter based on provided parameter
        filter_field = "nano_id" if nano_id else "name"
        filter_value = nano_id or name

        config = client.send_request(
            Endpoints.METRICS,
            Methods.GET,
            params={"$filter": f"{filter_field} eq '{filter_value}'"},
        )

        if not config:
            raise ValueError(f"No metric found with {filter_field} {filter_value}")

        if len(config) > 1:
            raise ValueError(f"Multiple metrics found with name {name}, please use nano_id")

        config = config[0]
        if config["class_name"] != cls.__name__:
            raise ValueError(f"Metric {config.get('id')} is not a {cls.__name__}")

        config = backend_config_to_sdk_config(config)
        return cls.from_dict(config)

    def to_config(self) -> MetricConfig:
        """
        Convert to config (must be implemented by the class using this mixin).

        Returns:
            MetricConfig: The metric configuration
        """
        raise NotImplementedError("Must be implemented by the class using this mixin")
