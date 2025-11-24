"""Registration message handler for SDK WebSocket connections."""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.services.connector.schemas import RegisterMessage

logger = logging.getLogger(__name__)


class RegistrationHandler:
    """Handles SDK registration messages and endpoint synchronization."""

    async def handle_register_message(
        self,
        project_id: str,
        environment: str,
        message: Dict[str, Any],
        db: Optional[Session] = None,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle registration message from SDK.

        Args:
            project_id: Project identifier
            environment: Environment name
            message: Registration message
            db: Optional database session for metadata updates
            organization_id: Optional organization ID for metadata updates
            user_id: Optional user ID for metadata updates

        Returns:
            Response message with sync stats
        """
        try:
            logger.info("=== HANDLE REGISTER MESSAGE ===")
            logger.info(f"Project ID: {project_id}")
            logger.info(f"Environment: {environment}")
            logger.info(f"Organization ID: {organization_id}")
            logger.info(f"User ID: {user_id}")
            logger.info(f"DB session provided: {db is not None}")
            logger.info(f"Raw message: {message}")

            reg_msg = RegisterMessage(**message)
            logger.info(
                f"Processed registration from {project_id}:{environment} "
                f"(SDK v{reg_msg.sdk_version}, {len(reg_msg.functions)} functions)"
            )

            # Sync function endpoints if database session provided
            if db and organization_id and user_id:
                functions_data = message.get("functions", [])
                logger.info(f"Calling sync_function_endpoints with {len(functions_data)} functions")
                logger.info(f"Functions data: {functions_data}")

                stats = await self._sync_function_endpoints(
                    db=db,
                    project_id=project_id,
                    environment=environment,
                    functions_data=functions_data,
                    organization_id=organization_id,
                    user_id=user_id,
                )
                logger.info(f"sync_function_endpoints returned: {stats}")

                # Start endpoint validation after registration completes
                logger.info("Starting endpoint validation for registered endpoints...")
                
                # Use lazy import to avoid circular import
                from rhesis.backend.app.services.connector.mapping import get_endpoint_validation_service
                endpoint_validation_service = get_endpoint_validation_service()
                
                await endpoint_validation_service.start_validation(
                    db=db,
                    project_id=project_id,
                    environment=environment,
                    functions_data=functions_data,
                    organization_id=organization_id,
                    user_id=user_id,
                )

                logger.info("=== END HANDLE REGISTER MESSAGE ===")
                return {"type": "registered", "status": "success", "sync_stats": stats}
            else:
                logger.warning(
                    f"Skipping endpoint sync - db: {db is not None}, "
                    f"org_id: {organization_id}, user_id: {user_id}"
                )

            logger.info("=== END HANDLE REGISTER MESSAGE ===")
            return {"type": "registered", "status": "success"}

        except Exception as e:
            logger.error(f"Error handling registration: {e}", exc_info=True)
            return {"type": "registered", "status": "error", "error": str(e)}

    async def _sync_function_endpoints(
        self,
        db: Session,
        project_id: str,
        environment: str,
        functions_data: List[Dict[str, Any]],
        organization_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Sync SDK function endpoints with registered functions.

        Args:
            db: Database session
            project_id: Project identifier
            environment: Environment name
            functions_data: List of function metadata
            organization_id: Organization ID
            user_id: User ID

        Returns:
            Stats dict with created, updated, marked_inactive counts
        """
        try:
            from rhesis.backend.app.services.endpoint import EndpointService

            endpoint_service = EndpointService()
            stats = await endpoint_service.sync_sdk_endpoints(
                db=db,
                project_id=project_id,
                environment=environment,
                functions_data=functions_data,
                organization_id=organization_id,
                user_id=user_id,
            )
            logger.info(f"Synced SDK endpoints for {project_id}:{environment}: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Failed to sync function endpoints: {e}", exc_info=True)
            return {"created": 0, "updated": 0, "marked_inactive": 0, "errors": [str(e)]}


# Global registration handler instance
registration_handler = RegistrationHandler()
