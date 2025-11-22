import json
import os
import uuid
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.invokers import create_invoker
from rhesis.backend.logging import logger


class EndpointService:
    """Service for managing and invoking endpoints."""

    def __init__(self, schema_path: str = None):
        """
        Initialize the endpoint service.

        Args:
            schema_path: Optional path to the endpoint schema file. If not provided,
                       defaults to endpoint_schema.json in the same directory.
        """
        self.schema_path = schema_path or os.path.join(
            os.path.dirname(__file__), "endpoint_schema.json"
        )

    def invoke_endpoint(
        self,
        db: Session,
        endpoint_id: str,
        input_data: Dict[str, Any],
        organization_id: str = None,
        user_id: str = None,
    ) -> Dict[str, Any]:
        """
        Invoke an endpoint with the given input data.

        Args:
            db: Database session
            endpoint_id: ID of the endpoint to invoke
            input_data: Input data to be mapped to the endpoint's request template
            organization_id: Organization ID for security filtering (CRITICAL)
            user_id: User ID for context injection (CRITICAL - injected into
                headers, not from user input)

        Returns:
            Dict containing the mapped response from the endpoint

        Raises:
            HTTPException: If endpoint is not found or invocation fails
        """
        # Fetch endpoint configuration with organization filtering (SECURITY CRITICAL)
        endpoint = self._get_endpoint(db, endpoint_id, organization_id)

        try:
            # Create appropriate invoker based on connection_type
            invoker = create_invoker(endpoint)

            # Inject organization_id and user_id into input_data for context
            # These are injected by the backend, NOT from user input (SECURITY CRITICAL)
            enriched_input_data = input_data.copy()
            if organization_id:
                enriched_input_data["organization_id"] = organization_id
            if user_id:
                enriched_input_data["user_id"] = user_id

            # Invoke the endpoint
            return invoker.invoke(db, endpoint, enriched_input_data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def _get_endpoint(self, db: Session, endpoint_id: str, organization_id: str = None) -> Endpoint:
        """
        Get an endpoint by ID with organization filtering.

        Args:
            db: Database session
            endpoint_id: ID of the endpoint to retrieve
            organization_id: Organization ID for security filtering (CRITICAL)

        Returns:
            The endpoint configuration

        Raises:
            HTTPException: If endpoint is not found or not accessible
        """
        query = db.query(Endpoint).filter(Endpoint.id == endpoint_id)

        # Apply organization filtering if provided (SECURITY CRITICAL)
        if organization_id:
            from uuid import UUID

            query = query.filter(Endpoint.organization_id == UUID(organization_id))

        endpoint = query.first()
        if not endpoint:
            raise HTTPException(status_code=404, detail="Endpoint not found or not accessible")
        return endpoint

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the endpoint schema definition.

        Returns:
            Dict containing the input and output schema definitions
        """
        with open(self.schema_path, "r") as f:
            return json.load(f)

    def sync_sdk_function_endpoints(
        self,
        db: Session,
        project_id: str,
        environment: str,
        functions_data: list,
        organization_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Sync SDK function endpoints - create/update/mark inactive as needed.

        Creates one endpoint per function registered by the SDK.

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
        from datetime import datetime

        from sqlalchemy.orm.attributes import flag_modified

        from rhesis.backend.app import crud, models, schemas
        from rhesis.backend.app.models.enums import (
            EndpointConfigSource,
            EndpointConnectionType,
            EndpointEnvironment,
        )
        from rhesis.backend.app.utils.status import get_or_create_status

        logger.info("=== SYNC SDK FUNCTION ENDPOINTS ===")
        logger.info(f"Project ID: {project_id}")
        logger.info(f"Environment: {environment}")
        logger.info(f"Functions to sync: {len(functions_data)}")

        # Get project name for endpoint naming
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        project_name = project.name if project else project_id

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

                    # Set status to Active (in case it was previously Inactive)
                    active_status = get_or_create_status(db, "Active", "General", organization_id)
                    if active_status:
                        endpoint.status_id = active_status.id

                    # Update metadata
                    endpoint.endpoint_metadata = {
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

                    stats["updated"] += 1
                    logger.info(f"Updated endpoint for function: {function_name}")

                else:
                    # Create new endpoint for this function
                    # Get or create Active status
                    active_status = get_or_create_status(db, "Active", "General", organization_id)

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

                    crud.create_endpoint(db, endpoint_data, organization_id, user_id)
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
                        db, "Inactive", "General", organization_id
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
        logger.info("=== END SYNC SDK FUNCTION ENDPOINTS ===")

        return stats


# Create a singleton instance of the service
endpoint_service = EndpointService()


def invoke(db: Session, endpoint_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function that uses the singleton EndpointService.

    Args:
        db: Database session
        endpoint_id: ID of the endpoint to invoke
        input_data: Input data to be mapped to the endpoint's request template

    Returns:
        Dict containing the mapped response from the endpoint
    """
    return endpoint_service.invoke_endpoint(db, endpoint_id, input_data)


def get_schema() -> Dict[str, Any]:
    """
    Convenience function that uses the singleton EndpointService.

    Returns:
        Dict containing the input and output schema definitions
    """
    return endpoint_service.get_schema()


# Add main section for command line testing
if __name__ == "__main__":
    import argparse

    from rhesis.backend.app.database import get_db

    parser = argparse.ArgumentParser(description="Test endpoint invocation")
    parser.add_argument("endpoint_id", help="ID of the endpoint to invoke")
    parser.add_argument(
        "--input", "-i", help="Input message", default="Hello, how can you help me?"
    )
    parser.add_argument("--session", "-s", help="Session ID", default=None)
    parser.add_argument("--org-id", "-o", help="Organization ID", required=True)
    parser.add_argument("--user-id", "-u", help="User ID", required=True)

    args = parser.parse_args()

    # Prepare input data
    input_data = {"input": args.input, "session_id": args.session or str(uuid.uuid4())}

    # Use simple get_db and pass tenant context directly to operations
    try:
        with get_db() as db:
            # Invoke endpoint
            # print(f"\nInvoking endpoint {args.endpoint_id} with input: {input_data}")
            # print(f"Using organization ID: {args.organization_id}")
            # print(f"Using user ID: {args.user_id}")
            result = invoke(db, args.endpoint_id, input_data)
            # print("\nResponse:")
            # print(json.dumps(result, indent=2))

            print(result.get("response", result))
    except Exception as e:
        print(f"\nError: {str(e)}")

"""
Usage examples:

1. Basic usage with required org and user IDs:
python -m rhesis.backend.app.services.endpoint "your-endpoint-id" \\
    --org-id "org-uuid" --user-id "user-uuid"

2. With custom input:
python -m rhesis.backend.app.services.endpoint "your-endpoint-id" \\
    -i "What's the weather like?" --org-id "org-uuid" --user-id "user-uuid"

3. With all parameters:
python -m rhesis.backend.app.services.endpoint "your-endpoint-id" \\
    -i "Hello" -s "custom-session-123" --org-id "org-uuid" --user-id "user-uuid"
"""
