"""Status handling for SDK endpoints.

Registration used to invoke the agent with a synthetic payload to verify its
mappings. That produced a real, traced turn on every reconnect — and because
the backend closes idle SDK sockets after ``WS_IDLE_TIMEOUT`` (300s), the SDK
reconnects on a loop, so every connected agent was invoked every 5 minutes.
Mappings are now exercised by the first genuine invocation instead.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.utils.crud_utils import get_or_create_status

logger = logging.getLogger(__name__)


def _clear_stale_validation_errors(endpoint: Endpoint) -> None:
    """Drop error metadata written by the removed registration-time validation.

    Endpoints marked Error before this flow was removed keep that metadata
    forever otherwise, so the SDK connection panel would show a validation
    error on an endpoint whose status now reads Active.
    """
    metadata = endpoint.endpoint_metadata
    if not metadata:
        return

    cleared = [metadata.pop(key, None) for key in ("validation_error", "last_error")]
    if any(value is not None for value in cleared):
        flag_modified(endpoint, "endpoint_metadata")


async def validate_and_update_status(
    db: Session,
    endpoint: Endpoint,
    project_id: str,
    environment: str,
    function_name: str,
    organization_id: str,
    user_id: str,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """
    Mark a freshly registered SDK endpoint as Active.

    No request is sent to the agent — see the module docstring. Mapping
    problems surface on the first real invocation.

    Args:
        db: Database session
        endpoint: Endpoint to update
        project_id: Project identifier
        environment: Environment name
        function_name: Function name for logging
        organization_id: Organization ID
        user_id: User ID
        timeout: Unused; kept for call-site compatibility

    Returns:
        Dict with result {
            "success": bool,
            "error": Optional[str],
            "status_set": str
        }
    """
    try:
        active_status = get_or_create_status(
            db=db,
            name="Active",
            entity_type="General",
            organization_id=organization_id,
            user_id=user_id,
        )
        if active_status:
            endpoint.status_id = active_status.id
            _clear_stale_validation_errors(endpoint)
            logger.info(f"[{function_name}] ✓ Status set to Active")
        else:
            logger.error(f"[{function_name}] Failed to get/create Active status")
        return {"success": True, "error": None, "status_set": "Active"}

    except Exception as validation_error:
        logger.error(f"Status update failed for {function_name}: {validation_error}", exc_info=True)
        error_status = get_or_create_status(
            db=db,
            name="Error",
            entity_type="General",
            organization_id=organization_id,
            user_id=user_id,
        )
        if error_status:
            endpoint.status_id = error_status.id

            error_msg = f"Status update exception: {str(validation_error)}"
            if not endpoint.endpoint_metadata:
                endpoint.endpoint_metadata = {}

            endpoint.endpoint_metadata["validation_error"] = {
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "exception_type": type(validation_error).__name__,
                "reason": "status_update_exception",
            }
            endpoint.endpoint_metadata["last_error"] = error_msg
            flag_modified(endpoint, "endpoint_metadata")

            logger.error(f"[{function_name}] ✗ Status update exception - Status set to Error")
        return {"success": False, "error": str(validation_error), "status_set": "Error"}
