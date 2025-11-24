"""Main message handler for SDK WebSocket connections."""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.services.connector.handlers import (
    pong_handler,
    registration_handler,
    test_result_handler,
)

logger = logging.getLogger(__name__)


class SDKMessageHandler:
    """Main handler that delegates to specialized handlers."""

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

        Delegates to RegistrationHandler for processing.
        """
        return await registration_handler.handle_register_message(
            project_id=project_id,
            environment=environment,
            message=message,
            db=db,
            organization_id=organization_id,
            user_id=user_id,
        )

    async def handle_test_result_message(
        self,
        project_id: str,
        environment: str,
        message: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> None:
        """
        Handle test result message from SDK.

        Delegates to TestResultHandler for processing.
        """
        await test_result_handler.handle_test_result_message(
            project_id=project_id,
            environment=environment,
            message=message,
            db=db,
        )

    async def handle_pong_message(self, project_id: str, environment: str) -> None:
        """
        Handle pong message from SDK.

        Delegates to PongHandler for processing.
        """
        await pong_handler.handle_pong_message(project_id, environment)


# Global message handler instance
message_handler = SDKMessageHandler()
