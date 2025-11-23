from typing import Dict, Type

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointConnectionType

from .base import BaseEndpointInvoker
from .rest_invoker import RestEndpointInvoker
from .sdk_invoker import SdkEndpointInvoker
from .websocket_invoker import WebSocketEndpointInvoker

# Registry of invokers by connection_type
INVOKERS: Dict[str, Type[BaseEndpointInvoker]] = {
    EndpointConnectionType.REST.value: RestEndpointInvoker,
    EndpointConnectionType.WEBSOCKET.value: WebSocketEndpointInvoker,
    EndpointConnectionType.SDK.value: SdkEndpointInvoker,
}


def create_invoker(endpoint: Endpoint) -> BaseEndpointInvoker:
    """
    Create an appropriate invoker instance based on the endpoint's connection_type.

    Args:
        endpoint: The endpoint configuration

    Returns:
        An instance of the appropriate invoker

    Raises:
        ValueError: If no invoker is found for the endpoint's connection_type
    """
    invoker_class = INVOKERS.get(endpoint.connection_type)
    if not invoker_class:
        raise ValueError(f"No invoker found for connection_type: {endpoint.connection_type}")

    return invoker_class()
