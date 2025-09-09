from typing import Dict, Type

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointProtocol

from .base import BaseEndpointInvoker
from .rest_invoker import RestEndpointInvoker
from .websocket_invoker import WebSocketEndpointInvoker

# Registry of invokers by protocol
INVOKERS: Dict[str, Type[BaseEndpointInvoker]] = {
    EndpointProtocol.REST.value: RestEndpointInvoker,
    EndpointProtocol.WEBSOCKET.value: WebSocketEndpointInvoker,
}


def create_invoker(endpoint: Endpoint) -> BaseEndpointInvoker:
    """
    Create an appropriate invoker instance based on the endpoint's protocol.

    Args:
        endpoint: The endpoint configuration

    Returns:
        An instance of the appropriate invoker

    Raises:
        ValueError: If no invoker is found for the endpoint's protocol
    """
    invoker_class = INVOKERS.get(endpoint.protocol)
    if not invoker_class:
        raise ValueError(f"No invoker found for protocol: {endpoint.protocol}")

    return invoker_class()
