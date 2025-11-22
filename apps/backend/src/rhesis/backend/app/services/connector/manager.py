"""Connection manager for WebSocket connections with SDKs."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import WebSocket
from sqlalchemy.orm import Session

from rhesis.backend.app.services.connector.handler import message_handler
from rhesis.backend.app.services.connector.schemas import (
    ConnectionStatus,
    ExecuteTestMessage,
    FunctionMetadata,
    RegisterMessage,
)

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with SDK clients."""

    def __init__(self):
        """Initialize connection manager."""
        # Store active connections: {project_id:environment: WebSocket}
        self._connections: Dict[str, WebSocket] = {}

        # Store function registries: {project_id:environment: [FunctionMetadata]}
        self._registries: Dict[str, List[FunctionMetadata]] = {}

    def get_connection_key(self, project_id: str, environment: str) -> str:
        """
        Generate connection key.

        Args:
            project_id: Project identifier
            environment: Environment name

        Returns:
            Connection key string
        """
        return f"{project_id}:{environment}"

    async def connect(self, project_id: str, environment: str, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection.

        Args:
            project_id: Project identifier
            environment: Environment name
            websocket: WebSocket connection
        """
        key = self.get_connection_key(project_id, environment)
        self._connections[key] = websocket
        logger.info(f"Connected: {key}")

    def disconnect(self, project_id: str, environment: str) -> None:
        """
        Unregister a WebSocket connection.

        Args:
            project_id: Project identifier
            environment: Environment name
        """
        key = self.get_connection_key(project_id, environment)
        if key in self._connections:
            del self._connections[key]
        if key in self._registries:
            del self._registries[key]
        logger.info(f"Disconnected: {key}")

    def register_functions(
        self, project_id: str, environment: str, functions: List[FunctionMetadata]
    ) -> None:
        """
        Register functions for a project.

        Args:
            project_id: Project identifier
            environment: Environment name
            functions: List of function metadata
        """
        key = self.get_connection_key(project_id, environment)
        self._registries[key] = functions
        logger.info(f"Registered {len(functions)} function(s) for {key}")

    async def send_test_request(
        self,
        project_id: str,
        environment: str,
        test_run_id: str,
        function_name: str,
        inputs: Dict[str, Any],
    ) -> bool:
        """
        Send test execution request to SDK.

        Args:
            project_id: Project identifier
            environment: Environment name
            test_run_id: Test run identifier
            function_name: Function to execute
            inputs: Function inputs

        Returns:
            True if message sent successfully, False otherwise
        """
        key = self.get_connection_key(project_id, environment)

        if key not in self._connections:
            logger.error(f"No connection for {key}")
            return False

        websocket = self._connections[key]
        message = ExecuteTestMessage(
            test_run_id=test_run_id, function_name=function_name, inputs=inputs
        )

        try:
            await websocket.send_json(message.model_dump())
            logger.info(f"Sent test request to {key}: {function_name}")
            return True
        except Exception as e:
            logger.error(f"Error sending test request to {key}: {e}")
            return False

    def get_connection_status(self, project_id: str, environment: str) -> ConnectionStatus:
        """
        Get connection status for a project.

        Args:
            project_id: Project identifier
            environment: Environment name

        Returns:
            Connection status
        """
        key = self.get_connection_key(project_id, environment)
        connected = key in self._connections
        functions = self._registries.get(key, [])

        return ConnectionStatus(
            project_id=project_id,
            environment=environment,
            connected=connected,
            functions=functions,
        )

    def is_connected(self, project_id: str, environment: str) -> bool:
        """
        Check if project is connected.

        Args:
            project_id: Project identifier
            environment: Environment name

        Returns:
            True if connected, False otherwise
        """
        key = self.get_connection_key(project_id, environment)
        return key in self._connections

    async def handle_registration(
        self, project_id: str, environment: str, message: Dict[str, Any]
    ) -> None:
        """
        Handle registration message from SDK - update local function registry.

        Args:
            project_id: Project identifier
            environment: Environment name
            message: Registration message
        """
        try:
            reg_msg = RegisterMessage(**message)
            self.register_functions(project_id, environment, reg_msg.functions)
        except Exception as e:
            logger.error(f"Error handling registration: {e}")

    async def handle_message(
        self,
        project_id: str,
        environment: str,
        message: Dict[str, Any],
        db: Optional[Session] = None,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle incoming WebSocket message from SDK.

        Args:
            project_id: Project identifier
            environment: Environment name
            message: Message data
            db: Optional database session for registration
            organization_id: Optional organization ID for metadata updates
            user_id: Optional user ID for metadata updates

        Returns:
            Response message to send back, or None if no response needed
        """
        message_type = message.get("type")
        logger.info(f"Processing message type: {message_type} from {project_id}:{environment}")

        if message_type == "register":
            # Update local function registry
            await self.handle_registration(project_id, environment, message)
            # Handle registration via message handler (includes DB updates)
            return await message_handler.handle_register_message(
                project_id=project_id,
                environment=environment,
                message=message,
                db=db,
                organization_id=organization_id,
                user_id=user_id,
            )

        elif message_type == "test_result":
            # Handle test result via message handler
            await message_handler.handle_test_result_message(project_id, environment, message)
            return None

        elif message_type == "pong":
            # Handle pong via message handler
            await message_handler.handle_pong_message(project_id, environment)
            return None

        else:
            logger.warning(f"Unknown message type: {message_type}")
            return None


# Global connection manager instance
connection_manager = ConnectionManager()
