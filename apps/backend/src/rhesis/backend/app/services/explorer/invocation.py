"""Concurrent endpoint invocation for Explorer.

Explorer invokes one endpoint many times in parallel — once per test, per suggestion, or
per pipeline item. Each invocation needs its own DB session, because the caller's request
session cannot be shared across concurrent tasks, and that session has to carry the
caller's tenant *and* project scope or the endpoint lookup inside it comes back empty.
"""

import asyncio
import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app.services.endpoint.result_processing import process_endpoint_result
from rhesis.backend.app.utils.response_extractor import (
    get_http_error_status_code,
    is_endpoint_failure,
)

logger = logging.getLogger(__name__)

# Endpoint output when the endpoint responded but said nothing. Callers treat this as
# "not worth evaluating" rather than as a failure.
NO_OUTPUT = "[no output]"


def _failure_message(processed: dict) -> str:
    """Describe a failed invocation for the caller's error slot."""
    message = processed.get("output") or processed.get("message") or "Endpoint invocation failed"
    status_code = get_http_error_status_code(processed)
    if status_code is not None and f"{status_code}" not in str(message):
        return f"HTTP {status_code}: {message}"
    return str(message)


class EndpointInvoker:
    """Invokes one endpoint concurrently, each call on its own tenant-scoped session.

    Captures the caller's project scope at construction, so the sessions opened per
    invocation inherit it. Owns the concurrency limit; ``max_concurrency`` must stay
    within the connection pool's budget (``pool_size=10``, ``max_overflow=20``), since
    every in-flight invocation holds a checked-out connection.

    Callers keep their own counters, logging and event emission — only the
    session/invoke/extract sequence is shared.
    """

    def __init__(
        self,
        db: Session,
        endpoint_id: str,
        organization_id: str,
        user_id: str,
        max_concurrency: int,
    ):
        # Imported here, not at module scope, so tests can patch the source modules
        # (rhesis.backend.app.database / .dependencies) and have it take effect. A
        # module-level import would bind these names at import time and silently
        # defeat those patches.
        from rhesis.backend.app.database import scope_project_id
        from rhesis.backend.app.dependencies import get_endpoint_service

        self._endpoint_id = endpoint_id
        self._organization_id = organization_id
        self._user_id = user_id
        # Propagate the active project scope to the inner sessions spawned per call.
        self._project_id = scope_project_id(db)
        self._svc = get_endpoint_service()
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def invoke(self, input_text: str) -> Tuple[str, Optional[str]]:
        """Invoke the endpoint once with ``input_text``.

        Returns
        -------
        tuple of (str, str or None)
            ``(output, None)`` on success, where output is :data:`NO_OUTPUT` if the
            endpoint returned nothing. ``("", error_message)`` on failure.
        """
        from rhesis.backend.app.database import get_db_with_tenant_variables

        async with self._semaphore:
            try:
                with get_db_with_tenant_variables(
                    self._organization_id, self._user_id, self._project_id
                ) as task_db:
                    raw = await self._svc.invoke_endpoint(
                        db=task_db,
                        endpoint_id=self._endpoint_id,
                        input_data={"input": input_text},
                        organization_id=self._organization_id,
                        user_id=self._user_id,
                    )
                processed = process_endpoint_result(raw)
                # An invoker failure comes back as a *return value*, not an exception, so
                # the handler below never sees it. Without this check the error text was
                # returned as a successful output: callers then persisted "HTTP 401 error
                # from endpoint" as a test's output and ran LLM judges over it.
                if is_endpoint_failure(processed):
                    return "", _failure_message(processed)
                return (processed.get("output") or "").strip() or NO_OUTPUT, None
            except Exception as e:  # noqa: BLE001
                return "", str(e)
