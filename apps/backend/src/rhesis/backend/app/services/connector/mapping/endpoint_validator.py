"""Endpoint validation service for SDK endpoints."""

import asyncio
import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.endpoint.validation import validate_and_update_status_async

logger = logging.getLogger(__name__)


class EndpointValidationService:
    """Service for handling async endpoint validation after registration."""

    async def start_validation(
        self,
        db: Session,
        project_id: str,
        environment: str,
        functions_data: List[Dict[str, Any]],
        organization_id: str,
        user_id: str,
    ) -> None:
        """
        Start async validation for all registered endpoints.

        This runs after registration completes to avoid blocking WebSocket processing.
        """
        # Start validation in background - don't await it
        asyncio.create_task(
            self._validate_endpoints_async(
                db=db,
                project_id=project_id,
                environment=environment,
                functions_data=functions_data,
                organization_id=organization_id,
                user_id=user_id,
            )
        )
        logger.info("Async validation task started in background")

    async def _validate_endpoints_async(
        self,
        db: Session,
        project_id: str,
        environment: str,
        functions_data: List[Dict[str, Any]],
        organization_id: str,
        user_id: str,
    ) -> None:
        """
        Validate endpoints asynchronously without blocking registration.
        """
        try:
            # Small delay to ensure registration response is sent first
            await asyncio.sleep(0.1)

            logger.info(f"Starting async validation for {len(functions_data)} functions")

            # Get all endpoints for this project/environment
            endpoints = (
                db.query(Endpoint)
                .filter(
                    Endpoint.project_id == project_id,
                    Endpoint.environment == environment,
                    Endpoint.connection_type == "SDK",
                )
                .all()
            )

            # Validate each endpoint
            for endpoint in endpoints:
                function_name = endpoint.endpoint_metadata.get("sdk_connection", {}).get(
                    "function_name"
                )
                if function_name:
                    logger.info(f"Validating {function_name} asynchronously...")

                    # Validate without blocking
                    await validate_and_update_status_async(
                        db=db,
                        endpoint=endpoint,
                        project_id=project_id,
                        environment=environment,
                        function_name=function_name,
                        organization_id=organization_id,
                        user_id=user_id,
                    )

                    # Commit after each validation
                    db.commit()

        except Exception as e:
            logger.error(f"Error in async validation: {e}", exc_info=True)


# Global endpoint validation service instance
endpoint_validation_service = EndpointValidationService()
