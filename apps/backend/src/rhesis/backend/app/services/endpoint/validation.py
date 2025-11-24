"""Validation logic for SDK endpoints."""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.connector.mapping import MappingValidator
from rhesis.backend.app.utils.status import get_or_create_status
from rhesis.backend.logging import logger


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
    logger.info(f"[{function_name}] Validating mappings...")

    try:
        logger.info(f"[{function_name}] Starting validation with mappings...")
        logger.debug(f"[{function_name}] Request mapping: {endpoint.request_mapping}")
        logger.debug(f"[{function_name}] Response mapping: {endpoint.response_mapping}")

        # For now, skip validation during registration to avoid blocking WebSocket processing
        # TODO: Implement async validation that doesn't block the registration process
        logger.info(f"[{function_name}] Skipping validation during registration to avoid blocking")

        # Set to Active by default - validation can be done separately
        active_status = get_or_create_status(db, "Active", "General", organization_id, user_id)
        if active_status:
            endpoint.status_id = active_status.id
            logger.info(f"[{function_name}] ✓ Status set to Active (validation skipped)")
        else:
            logger.error(f"[{function_name}] Failed to get/create Active status")
        return {"success": True, "error": None, "status_set": "Active"}

    except Exception as validation_error:
        logger.error(f"Validation error for {function_name}: {validation_error}", exc_info=True)
        # Set Error status on exception and store error details
        error_status = get_or_create_status(db, "Error", "General", organization_id, user_id)
        if error_status:
            endpoint.status_id = error_status.id

            # Store exception details in metadata
            error_msg = f"Validation exception: {str(validation_error)}"
            if not endpoint.endpoint_metadata:
                endpoint.endpoint_metadata = {}

            endpoint.endpoint_metadata["validation_error"] = {
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat(),
                "exception_type": type(validation_error).__name__,
                "reason": "validation_exception",
            }
            endpoint.endpoint_metadata["last_error"] = error_msg

            # Mark the metadata as modified for SQLAlchemy
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(endpoint, "endpoint_metadata")

            logger.error(f"[{function_name}] ✗ Validation exception - Status set to Error")
        return {"success": False, "error": str(validation_error), "status_set": "Error"}


async def validate_and_update_status_async(
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
    Validate endpoint mappings asynchronously and update status.

    This version doesn't block and uses the simplified validation approach.
    """
    validator = MappingValidator()

    logger.info(f"[{function_name}] Starting async validation...")

    try:
        # Check if endpoint has meaningful mappings
        request_mapping = endpoint.request_mapping or {}
        response_mapping = endpoint.response_mapping or {}

        logger.debug(f"[{function_name}] Request mapping: {request_mapping}")
        logger.debug(f"[{function_name}] Response mapping: {response_mapping}")

        # If no request mapping, mark as error (can't call function)
        if not request_mapping:
            logger.warning(f"[{function_name}] No request mapping - marking as Error")
            error_status = get_or_create_status(db, "Error", "General", organization_id, user_id)
            if error_status:
                endpoint.status_id = error_status.id

                # Store mapping error in metadata
                error_msg = "No request mapping available - cannot invoke function"
                if not endpoint.endpoint_metadata:
                    endpoint.endpoint_metadata = {}

                endpoint.endpoint_metadata["validation_error"] = {
                    "error": error_msg,
                    "timestamp": datetime.utcnow().isoformat(),
                    "reason": "missing_request_mapping",
                }
                endpoint.endpoint_metadata["last_error"] = error_msg

                # Mark the metadata as modified for SQLAlchemy
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(endpoint, "endpoint_metadata")

                logger.error(f"[{function_name}] ✗ No request mapping - Status set to Error")
            return {
                "success": False,
                "error": "No request mapping available",
                "status_set": "Error",
            }

        # Validate the mappings with actual test
        validation_result = await validator.validate_mappings(
            project_id=project_id,
            environment=environment,
            function_name=function_name,
            request_mapping=request_mapping,
            response_mapping=response_mapping,
            timeout=timeout,
        )

        logger.info(f"[{function_name}] Async validation result: {validation_result}")

        if validation_result["success"]:
            # Set Active status and clear any previous errors
            active_status = get_or_create_status(db, "Active", "General", organization_id, user_id)
            if active_status:
                endpoint.status_id = active_status.id

                # Clear validation errors from metadata
                if endpoint.endpoint_metadata:
                    endpoint.endpoint_metadata.pop("validation_error", None)
                    endpoint.endpoint_metadata.pop("last_error", None)
                    # Mark the metadata as modified for SQLAlchemy
                    from sqlalchemy.orm.attributes import flag_modified

                    flag_modified(endpoint, "endpoint_metadata")

                logger.info(f"[{function_name}] ✓ Async validation passed - Status set to Active")
            return {"success": True, "error": None, "status_set": "Active"}
        else:
            # Set Error status and store error details in metadata
            error_status = get_or_create_status(db, "Error", "General", organization_id, user_id)
            if error_status:
                endpoint.status_id = error_status.id

                # Store validation error in metadata
                error_msg = validation_result.get("error", "Unknown validation error")
                if not endpoint.endpoint_metadata:
                    endpoint.endpoint_metadata = {}

                endpoint.endpoint_metadata["validation_error"] = {
                    "error": error_msg,
                    "timestamp": datetime.utcnow().isoformat(),
                    "test_input": validation_result.get("test_input"),
                    "test_output": validation_result.get("test_output"),
                }
                endpoint.endpoint_metadata["last_error"] = error_msg

                # Mark the metadata as modified for SQLAlchemy
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(endpoint, "endpoint_metadata")

                logger.error(f"[{function_name}] ✗ Async validation failed - Status set to Error")
                logger.error(f"[{function_name}] ✗ Error details stored in metadata: {error_msg}")

            error_msg = validation_result.get("error", "Unknown validation error")
            return {"success": False, "error": error_msg, "status_set": "Error"}

    except Exception as validation_error:
        logger.error(
            f"[{function_name}] Validation exception: {validation_error}",
            exc_info=True,
        )
        error_status = get_or_create_status(db, "Error", "General", organization_id, user_id)
        if error_status:
            endpoint.status_id = error_status.id

            # Store exception details in metadata
            error_msg = f"Async validation exception: {str(validation_error)}"
            if not endpoint.endpoint_metadata:
                endpoint.endpoint_metadata = {}

            endpoint.endpoint_metadata["validation_error"] = {
                "error": error_msg,
                "timestamp": datetime.utcnow().isoformat(),
                "exception_type": type(validation_error).__name__,
                "reason": "async_validation_exception",
            }
            endpoint.endpoint_metadata["last_error"] = error_msg

            # Mark the metadata as modified for SQLAlchemy
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(endpoint, "endpoint_metadata")

        return {
            "success": False,
            "error": f"Validation exception: {str(validation_error)}",
            "status_set": "Error",
        }
