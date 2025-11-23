"""Validation logic for SDK endpoints."""

import asyncio
from typing import Any, Dict

from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.connector.mapping import MappingValidator
from rhesis.backend.app.utils.status import get_or_create_status
from rhesis.backend.logging import logger


def validate_and_update_status(
    db: Session,
    endpoint: Endpoint,
    project_id: str,
    environment: str,
    function_name: str,
    organization_id: str,
    user_id: str,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    """
    Validate endpoint mappings and update status accordingly.

    Sends a synchronous test request to the SDK to verify the mappings work.
    Sets the endpoint status to "Active" on success or "Error" on failure.

    Args:
        db: Database session
        endpoint: Endpoint to validate
        project_id: Project identifier
        environment: Environment name
        function_name: Function name for logging
        organization_id: Organization ID
        user_id: User ID
        timeout: Validation timeout in seconds

    Returns:
        Dict with validation result {
            "success": bool,
            "error": Optional[str],
            "status_set": str
        }
    """
    validator = MappingValidator()

    logger.info(f"[{function_name}] Validating mappings...")

    try:
        validation_result = asyncio.run(
            validator.validate_mappings(
                project_id=project_id,
                environment=environment,
                function_name=function_name,
                request_template=endpoint.request_body_template,
                response_mappings=endpoint.response_mappings,
                timeout=timeout,
            )
        )

        if validation_result["success"]:
            # Set Active status
            active_status = get_or_create_status(db, "Active", "General", organization_id, user_id)
            if active_status:
                endpoint.status_id = active_status.id
            logger.info(f"[{function_name}] ✓ Validation passed")
            return {"success": True, "error": None, "status_set": "Active"}
        else:
            # Set Error status but keep endpoint
            error_status = get_or_create_status(db, "Error", "General", organization_id, user_id)
            if error_status:
                endpoint.status_id = error_status.id
            error_msg = validation_result.get("error", "Unknown validation error")
            logger.error(f"[{function_name}] ✗ Validation failed: {error_msg}")
            return {"success": False, "error": error_msg, "status_set": "Error"}

    except Exception as validation_error:
        logger.error(
            f"[{function_name}] Validation exception: {validation_error}",
            exc_info=True,
        )
        error_status = get_or_create_status(db, "Error", "General", organization_id, user_id)
        if error_status:
            endpoint.status_id = error_status.id
        return {
            "success": False,
            "error": f"Validation exception: {str(validation_error)}",
            "status_set": "Error",
        }
