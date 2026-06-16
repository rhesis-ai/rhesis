"""Base protocol for REST provider clients."""

from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class RestClient(Protocol):
    async def health_check(
        self, tool_metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]: ...
