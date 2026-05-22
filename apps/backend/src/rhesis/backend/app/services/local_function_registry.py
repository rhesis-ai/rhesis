"""In-process registry for backend-resident @endpoint functions.

Functions registered here are called directly by SdkEndpointInvoker
without a WebSocket round-trip. Add an entry after each @endpoint
definition in endpoint_operations.py (or equivalent).
"""

registry: dict[str, callable] = {}
