"""SDK endpoint synchronization logic."""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.models.enums import (
    EndpointConfigSource,
    EndpointConnectionType,
    EndpointEnvironment,
)
from rhesis.backend.app.utils.status import get_or_create_status
from rhesis.backend.logging import logger

from .mapper import generate_and_apply_mappings
from .validation import validate_and_update_status


async def sync_sdk_endpoints(
    db: Session,
    project_id: str,
    environment: str,
    functions_data: list,
    organization_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """
    Sync SDK endpoints - create/update/mark inactive as needed.

    Creates one endpoint per function registered by the SDK.
    Includes auto-mapping generation and validation.

    Args:
        db: Database session
        project_id: Project identifier
        environment: Environment name
        functions_data: List of function metadata from SDK
        organization_id: Organization ID
        user_id: User ID

    Returns:
        Dict with sync statistics (created, updated, marked_inactive counts)
    """
    logger.info("=== SYNC SDK ENDPOINTS ===")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Environment: {environment}")
    logger.info(f"Functions to sync: {len(functions_data)}")

    # Get user for LLM model access
    user = crud.get_user_by_id(db, user_id)
    if not user:
        logger.error(f"User {user_id} not found for mapping generation")
        return {"created": 0, "updated": 0, "marked_inactive": 0, "errors": ["User not found"]}

    # Get project name for endpoint naming - with organization validation for security
    project = (
        db.query(models.Project)
        .filter(
            models.Project.id == project_id,
            models.Project.organization_id == organization_id,
        )
        .first()
    )

    if not project:
        error_msg = (
            f"Project {project_id} not found or not accessible in organization "
            f"{organization_id}. Cannot create endpoints without valid project."
        )
        logger.error(error_msg)
        return {
            "created": 0,
            "updated": 0,
            "marked_inactive": 0,
            "errors": [error_msg],
        }

    project_name = project.name
    logger.info(f"Project validated: {project_name} ({project_id})")

    # Get all existing SDK endpoints for this project/environment
    existing_endpoints = (
        db.query(models.Endpoint)
        .filter(
            models.Endpoint.project_id == project_id,
            models.Endpoint.environment == environment,
            models.Endpoint.connection_type == EndpointConnectionType.SDK.value,
            models.Endpoint.organization_id == organization_id,
        )
        .all()
    )

    # Map existing endpoints by function name
    existing_by_function = {}
    for ep in existing_endpoints:
        logger.debug(f"Checking endpoint {ep.id} ({ep.name}), metadata: {ep.endpoint_metadata}")
        if ep.endpoint_metadata and ep.endpoint_metadata.get("sdk_connection"):
            func_name = ep.endpoint_metadata["sdk_connection"].get("function_name")
            if func_name:
                existing_by_function[func_name] = ep
                logger.debug(f"Mapped function '{func_name}' to endpoint {ep.id}")
        else:
            logger.warning(
                f"Endpoint {ep.id} ({ep.name}) has no sdk_connection in metadata: "
                f"{ep.endpoint_metadata}"
            )

    logger.info(f"Found {len(existing_by_function)} existing SDK function endpoints")
    logger.info(f"Existing function names: {list(existing_by_function.keys())}")

    # Track registered function names
    registered_functions = set()
    stats = {"created": 0, "updated": 0, "marked_inactive": 0, "errors": []}

    # Create or update endpoints for each function
    for func_data in functions_data:
        function_name = func_data.get("name")
        if not function_name:
            logger.warning(f"Skipping function without name: {func_data}")
            continue

        registered_functions.add(function_name)

        try:
            if function_name in existing_by_function:
                # Update existing endpoint
                endpoint = existing_by_function[function_name]

                # Update metadata - preserve existing fields like mapping_info
                existing_metadata = endpoint.endpoint_metadata or {}
                endpoint.endpoint_metadata = {
                    **existing_metadata,  # Preserve existing fields (e.g., mapping_info)
                    "sdk_connection": {
                        "project_id": project_id,
                        "environment": environment,
                        "function_name": function_name,
                    },
                    "function_schema": {
                        "parameters": func_data.get("parameters", {}),
                        "return_type": func_data.get("return_type", "any"),
                        "description": func_data.get("metadata", {}).get("description", ""),
                    },
                    "last_registered": datetime.utcnow().isoformat(),
                }

                # Update description if changed
                func_description = func_data.get("metadata", {}).get("description", "")
                if func_description:
                    endpoint.description = func_description

                flag_modified(endpoint, "endpoint_metadata")

                # Generate or use existing mappings
                generate_and_apply_mappings(
                    db=db,
                    user=user,
                    endpoint=endpoint,
                    function_name=function_name,
                    function_data=func_data,
                    is_new_endpoint=False,
                )

                # Validate mappings and update status
                await validate_and_update_status(
                    db=db,
                    endpoint=endpoint,
                    project_id=project_id,
                    environment=environment,
                    function_name=function_name,
                    organization_id=organization_id,
                    user_id=user_id,
                )

                stats["updated"] += 1
                logger.info(f"Updated endpoint for function: {function_name}")

            else:
                # Create new endpoint for this function
                # Get or create Active status (tentative, will be updated after validation)
                active_status = get_or_create_status(
                    db, "Active", "General", organization_id, user_id
                )

                # Create endpoint with metadata first
                endpoint_data = schemas.EndpointCreate(
                    name=f"{project_name} ({function_name})",
                    description=func_data.get("metadata", {}).get("description", ""),
                    connection_type=EndpointConnectionType.SDK,
                    url="",  # Empty for SDK
                    environment=EndpointEnvironment(environment),
                    project_id=project_id,
                    config_source=EndpointConfigSource.SDK,
                    status_id=active_status.id if active_status else None,
                    endpoint_metadata={
                        "sdk_connection": {
                            "project_id": project_id,
                            "environment": environment,
                            "function_name": function_name,
                        },
                        "function_schema": {
                            "parameters": func_data.get("parameters", {}),
                            "return_type": func_data.get("return_type", "any"),
                            "description": func_data.get("metadata", {}).get("description", ""),
                        },
                        "created_at": datetime.utcnow().isoformat(),
                        "last_registered": datetime.utcnow().isoformat(),
                    },
                )

                endpoint = crud.create_endpoint(db, endpoint_data, organization_id, user_id)
                db.flush()  # Flush to get endpoint ID but don't commit yet

                # Generate mappings for new endpoint
                generate_and_apply_mappings(
                    db=db,
                    user=user,
                    endpoint=endpoint,
                    function_name=function_name,
                    function_data=func_data,
                    is_new_endpoint=True,
                )

                # Validate mappings and update status
                await validate_and_update_status(
                    db=db,
                    endpoint=endpoint,
                    project_id=project_id,
                    environment=environment,
                    function_name=function_name,
                    organization_id=organization_id,
                    user_id=user_id,
                )

                stats["created"] += 1
                logger.info(f"Created endpoint for function: {function_name}")

        except Exception as e:
            logger.error(f"Error syncing function {function_name}: {e}", exc_info=True)
            stats["errors"].append({"function": function_name, "error": str(e)})

    # Mark endpoints as inactive for functions that are no longer registered
    logger.info(f"Registered functions: {registered_functions}")
    logger.info("Checking for removed functions to mark inactive...")

    for function_name, endpoint in existing_by_function.items():
        if function_name not in registered_functions:
            logger.info(
                f"Function '{function_name}' no longer registered, "
                f"marking endpoint {endpoint.id} as inactive"
            )
            try:
                inactive_status = get_or_create_status(
                    db, "Inactive", "General", organization_id, user_id
                )
                if inactive_status:
                    endpoint.status_id = inactive_status.id
                    stats["marked_inactive"] += 1
                    logger.info(
                        f"✓ Marked endpoint {endpoint.id} ({endpoint.name}) inactive "
                        f"for removed function: {function_name}"
                    )
                else:
                    logger.error("Could not find/create Inactive status")
            except Exception as e:
                logger.error(
                    f"Error marking function {function_name} as inactive: {e}", exc_info=True
                )
                stats["errors"].append({"function": function_name, "error": str(e)})

    db.commit()

    logger.info(f"Sync complete: {stats}")
    logger.info("=== END SYNC SDK ENDPOINTS ===")

    return stats
