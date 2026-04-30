"""Pluggable target implementations for agent tools.

Targets in this module implement Penelope's ``Target`` interface using
injectable callables, so they work in any execution context (SDK client,
backend Celery worker, tests) without hard-coding transport or auth.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from rhesis.sdk.targets import Target, TargetResponse

logger = logging.getLogger(__name__)

InvokeFn = Callable[..., Dict[str, Any]]
"""Signature: (endpoint_id, input_data, **kwargs) -> dict with 'output' key."""


class LocalEndpointTarget(Target):
    """Target that invokes endpoints via a caller-supplied function.

    Instead of going through the SDK REST client, the actual invocation
    is delegated to ``invoke_fn``.  The backend passes
    ``EndpointService.invoke_endpoint`` (wrapped to provide DB/tenant
    context); SDK callers can pass ``Endpoint.invoke`` or any other
    function with the same shape.

    Args:
        endpoint_id: UUID of the endpoint.
        invoke_fn: ``(endpoint_id, input_data, **kw) -> dict``.
            Must return a dict with at least an ``output`` key.
        name: Human-readable endpoint name (for descriptions).
        endpoint_description: Optional endpoint description.

    Example (backend worker)::

        from rhesis.backend.app.services.endpoint.service import EndpointService

        svc = EndpointService()
        target = LocalEndpointTarget(
            endpoint_id="abc",
            invoke_fn=lambda eid, data, **kw: asyncio.run(
                svc.invoke_endpoint(db, eid, data, org_id=org, user_id=uid)
            ),
            name="File Chatbot",
        )
    """

    def __init__(
        self,
        endpoint_id: str,
        invoke_fn: InvokeFn,
        name: Optional[str] = None,
        endpoint_description: Optional[str] = None,
    ):
        self._endpoint_id = endpoint_id
        self._invoke_fn = invoke_fn
        self._name = name or endpoint_id
        self._endpoint_description = endpoint_description or ""

    @property
    def target_type(self) -> str:
        return "endpoint"

    @property
    def target_id(self) -> str:
        return self._endpoint_id

    @property
    def description(self) -> str:
        desc = f"Rhesis Endpoint: {self._name}"
        if self._endpoint_description:
            desc += f" — {self._endpoint_description}"
        return desc

    def validate_configuration(self) -> tuple[bool, Optional[str]]:
        if not self._endpoint_id:
            return False, "Endpoint ID is missing"
        if not callable(self._invoke_fn):
            return False, "invoke_fn is not callable"
        return True, None

    def send_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        files: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> TargetResponse:
        if not message or not message.strip():
            return TargetResponse(
                success=False,
                content="",
                error="Message cannot be empty",
            )

        input_data: Dict[str, Any] = {"input": message}
        if conversation_id is not None:
            input_data["conversation_id"] = conversation_id

        try:
            result = self._invoke_fn(self._endpoint_id, input_data)

            if result is None:
                return TargetResponse(
                    success=False,
                    content="",
                    error="Endpoint invocation returned None",
                )

            response_text = result.get("output", "")
            response_cid = result.get("conversation_id", conversation_id)

            return TargetResponse(
                success=True,
                content=str(response_text),
                conversation_id=response_cid,
                metadata={"raw_response": result},
            )

        except Exception as e:
            logger.error("LocalEndpointTarget invoke failed: %s", e, exc_info=True)
            return TargetResponse(
                success=False,
                content="",
                error=f"Endpoint invocation failed: {e}",
            )

    def get_tool_documentation(self) -> str:
        doc = f"""
Target Type: Rhesis Endpoint (local)
Name: {self._name}
Endpoint ID: {self._endpoint_id}
"""
        if self._endpoint_description:
            doc += f"\nDescription: {self._endpoint_description}\n"

        doc += """
Interface:
  Input:  message (string), optional conversation_id
  Output: output text, conversation_id, metadata

Send messages using send_message_to_target(message, conversation_id).
Maintain conversation_id across turns for conversation continuity.
"""
        return doc
