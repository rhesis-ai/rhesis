"""Core endpoint service with basic operations."""

import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import (
    EndpointAuthType,
    EndpointConfigSource,
    EndpointConnectionType,
    EndpointEnvironment,
    EndpointResponseFormat,
)
from rhesis.backend.app.schemas.endpoint import EndpointTestRequest
from rhesis.backend.app.services.invokers import create_invoker

# Import sdk_sync at module level to avoid circular imports
from . import sdk_sync

logger = logging.getLogger(__name__)


class EndpointService:
    """Service for managing and invoking endpoints."""

    def __init__(self, schema_path: str = None):
        """
        Initialize the endpoint service.

        Args:
            schema_path: Optional path to the endpoint schema file. If not provided,
                       defaults to endpoint_schema.json in the parent services directory.
        """
        if schema_path:
            self.schema_path = schema_path
        else:
            # Look for endpoint_schema.json in the parent services directory
            services_dir = os.path.dirname(os.path.dirname(__file__))
            self.schema_path = os.path.join(services_dir, "endpoint_schema.json")

    async def invoke_endpoint(
        self,
        db: Session,
        endpoint_id: str,
        input_data: Dict[str, Any],
        organization_id: str = None,
        user_id: str = None,
        test_execution_context: Optional[Dict[str, str]] = None,
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
            test_execution_context: Optional dict with test_run_id, test_result_id, test_id
                                   for linking traces to test executions

        Returns:
            Dict containing the mapped response from the endpoint

        Raises:
            HTTPException: If endpoint is not found or invocation fails
        """
        # Fetch endpoint configuration with organization filtering (SECURITY CRITICAL)
        endpoint = self._get_endpoint(db, endpoint_id, organization_id)
        logger.debug(f"Invoking endpoint {endpoint.name} ({endpoint.connection_type})")

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

            # Check if invoker needs manual tracing (REST/WebSocket)
            if not invoker.automatic_tracing and test_execution_context:
                # Import here to avoid circular imports
                from rhesis.backend.app.services.invokers.manual_tracing import (
                    create_manual_invocation_trace,
                )

                # Wrap invocation with manual trace creation
                async with create_manual_invocation_trace(
                    db, endpoint, test_execution_context, organization_id
                ) as trace_ctx:
                    result = await invoker.invoke(
                        db, endpoint, enriched_input_data, test_execution_context
                    )
                    trace_ctx["result"] = result
            else:
                # SDK invoker or no test context - invoke directly
                result = await invoker.invoke(
                    db, endpoint, enriched_input_data, test_execution_context
                )

            logger.debug(f"Endpoint invocation completed: {endpoint.name}")
            return result
        except ValueError as e:
            logger.error(f"ValueError invoking endpoint: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Exception invoking endpoint: {e}", exc_info=True)
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

    async def test_endpoint(
        self,
        db: Session,
        test_config: EndpointTestRequest,
        organization_id: str = None,
        user_id: str = None,
    ) -> Dict[str, Any]:
        """
        Test an endpoint configuration without saving it to the database.

        Args:
            db: Database session (required for invoker, but no writes occur)
            test_config: Endpoint test configuration
            organization_id: Organization ID for context injection (CRITICAL)
            user_id: User ID for context injection (CRITICAL - injected into
                headers, not from user input)

        Returns:
            Dict containing the mapped response from the endpoint

        Raises:
            HTTPException: If configuration is invalid or invocation fails
        """

        # Validate connection_type and auth_type (schema validation should catch this,
        # but double-check for safety)
        # Helper function to safely get enum value
        def get_enum_value(enum_or_str, expected_enum_class):
            """Safely extract value from enum or return string."""
            if hasattr(enum_or_str, "value"):
                return enum_or_str.value
            return str(enum_or_str)

        connection_type_str = get_enum_value(test_config.connection_type, EndpointConnectionType)
        auth_type_str = get_enum_value(test_config.auth_type, EndpointAuthType)
        response_format_str = get_enum_value(test_config.response_format, EndpointResponseFormat)

        if connection_type_str != EndpointConnectionType.REST.value:
            raise HTTPException(
                status_code=400,
                detail=f"Only REST endpoints are supported for testing. Got: {connection_type_str}",
            )

        if auth_type_str != EndpointAuthType.BEARER_TOKEN.value:
            raise HTTPException(
                status_code=400,
                detail=f"Only BEARER_TOKEN authentication is supported for testing. Got: {auth_type_str}",
            )

        logger.debug(f"Testing endpoint configuration: {test_config.url} ({connection_type_str})")

        try:
            # Create a temporary Endpoint object (not saved to DB)
            # Set required fields from test_config and defaults for non-test fields
            endpoint = Endpoint(
                name="test",  # Temporary name for testing
                connection_type=connection_type_str,
                url=test_config.url,
                method=test_config.method,
                endpoint_path=test_config.endpoint_path,
                request_headers=test_config.request_headers,
                query_params=test_config.query_params,
                request_mapping=test_config.request_mapping,
                response_mapping=test_config.response_mapping,
                response_format=response_format_str,
                auth_type=auth_type_str,
                auth_token=test_config.auth_token,
                environment=EndpointEnvironment.DEVELOPMENT.value,
                config_source=EndpointConfigSource.MANUAL.value,
            )

            # Create appropriate invoker based on connection_type
            invoker = create_invoker(endpoint)

            # Inject organization_id and user_id into input_data for context
            # These are injected by the backend, NOT from user input (SECURITY CRITICAL)
            enriched_input_data = test_config.input_data.copy()
            if organization_id:
                enriched_input_data["organization_id"] = organization_id
            if user_id:
                enriched_input_data["user_id"] = user_id

            # Invoke the endpoint
            result = await invoker.invoke(db, endpoint, enriched_input_data)
            logger.debug("Endpoint test invocation completed")
            return result
        except ValueError as e:
            logger.error(f"ValueError testing endpoint: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Exception testing endpoint: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    async def sync_sdk_endpoints(
        self,
        db: Session,
        project_id: str,
        environment: str,
        functions_data: list,
        organization_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Sync SDK endpoints - create/update/mark inactive as needed.

        This is a convenience method that delegates to the sdk_sync module.

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
        return await sdk_sync.sync_sdk_endpoints(
            db=db,
            project_id=project_id,
            environment=environment,
            functions_data=functions_data,
            organization_id=organization_id,
            user_id=user_id,
        )
