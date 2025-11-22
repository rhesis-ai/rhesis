"""
Tests for connector router in rhesis.backend.app.routers.connector

This module tests the WebSocket connector endpoints including:
- WebSocket connection lifecycle
- Authentication and validation
- Message handling
- HTTP endpoints (trigger, status, trace)
"""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestConnectorWebSocket:
    """Test WebSocket connector functionality"""

    @pytest.fixture
    def mock_connection_manager(self):
        """Mock the connection_manager"""
        with patch("rhesis.backend.app.routers.connector.connection_manager") as mock_mgr:
            mock_mgr.connect = AsyncMock()
            mock_mgr.disconnect = Mock()
            mock_mgr.handle_message = AsyncMock(return_value={"type": "ack", "status": "ok"})
            mock_mgr.is_connected = Mock(return_value=True)
            mock_mgr.send_test_request = AsyncMock(return_value=True)
            mock_mgr.get_connection_status = Mock()
            yield mock_mgr

    @pytest.fixture
    def mock_authenticate_websocket(self):
        """Mock WebSocket authentication"""
        with patch("rhesis.backend.app.routers.connector.authenticate_websocket") as mock_auth:
            # Create a mock user
            mock_user = Mock()
            mock_user.id = uuid.uuid4()
            mock_user.organization_id = uuid.uuid4()
            mock_user.email = "test@example.com"
            mock_auth.return_value = mock_user
            yield mock_auth

    @pytest.fixture
    def mock_db_context(self):
        """Mock database context manager"""
        with patch("rhesis.backend.app.routers.connector.get_db_with_tenant_variables") as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__ = Mock(return_value=mock_session)
            mock_db.return_value.__exit__ = Mock(return_value=None)
            yield mock_db

    def test_websocket_connection_missing_project_id(
        self,
        authenticated_client: TestClient,
        mock_authenticate_websocket,
        mock_connection_manager,
        mock_db_context,
    ):
        """Test WebSocket connection without project_id header"""
        from starlette.websockets import WebSocketDisconnect

        # Should close connection due to missing project_id
        with pytest.raises(WebSocketDisconnect):
            with authenticated_client.websocket_connect(
                "/connector/ws", headers={"x-rhesis-environment": "development"}
            ) as websocket:
                pass

    def test_websocket_connection_authentication_failure(self, authenticated_client: TestClient):
        """Test WebSocket connection with authentication failure"""
        with patch("rhesis.backend.app.routers.connector.authenticate_websocket") as mock_auth:
            mock_auth.side_effect = HTTPException(status_code=401, detail="Invalid token")

            with pytest.raises(Exception):  # WebSocket will raise on auth failure
                with authenticated_client.websocket_connect(
                    "/connector/ws",
                    headers={
                        "x-rhesis-project": "test-project",
                        "x-rhesis-environment": "development",
                    },
                ):
                    pass


@pytest.mark.integration
class TestConnectorHTTPEndpoints:
    """Test HTTP connector endpoints"""

    def test_trigger_test_success(self, authenticated_client: TestClient):
        """Test successful test trigger"""
        with patch("rhesis.backend.app.routers.connector.connection_manager") as mock_mgr:
            mock_mgr.is_connected = Mock(return_value=True)
            mock_mgr.send_test_request = AsyncMock(return_value=True)

            response = authenticated_client.post(
                "/connector/trigger",
                json={
                    "project_id": "test-project",
                    "environment": "development",
                    "function_name": "test_func",
                    "inputs": {"param": "value"},
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "test_run_id" in data
            assert data["test_run_id"].startswith("test_")
            assert "test_func" in data["message"]

    def test_trigger_test_not_connected(self, authenticated_client: TestClient):
        """Test test trigger when project not connected"""
        with patch("rhesis.backend.app.routers.connector.connection_manager") as mock_mgr:
            mock_mgr.is_connected = Mock(return_value=False)

            response = authenticated_client.post(
                "/connector/trigger",
                json={
                    "project_id": "not-connected",
                    "environment": "development",
                    "function_name": "test_func",
                    "inputs": {},
                },
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            data = response.json()
            assert "not connected" in data["detail"].lower()

    def test_trigger_test_send_failure(self, authenticated_client: TestClient):
        """Test test trigger when sending fails"""
        with patch("rhesis.backend.app.routers.connector.connection_manager") as mock_mgr:
            mock_mgr.is_connected = Mock(return_value=True)
            mock_mgr.send_test_request = AsyncMock(return_value=False)

            response = authenticated_client.post(
                "/connector/trigger",
                json={
                    "project_id": "test-project",
                    "environment": "development",
                    "function_name": "test_func",
                    "inputs": {},
                },
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "failed" in data["detail"].lower()

    def test_get_status_success(self, authenticated_client: TestClient):
        """Test getting connection status"""
        from rhesis.backend.app.services.connector.schemas import ConnectionStatus, FunctionMetadata

        mock_status = ConnectionStatus(
            project_id="test-project",
            environment="development",
            connected=True,
            functions=[
                FunctionMetadata(
                    name="test_func",
                    parameters={"param1": {"type": "string"}},
                    return_type="string",
                    metadata={},
                )
            ],
        )

        with patch("rhesis.backend.app.routers.connector.connection_manager") as mock_mgr:
            mock_mgr.get_connection_status = Mock(return_value=mock_status)

            response = authenticated_client.get(
                "/connector/status/test-project", params={"environment": "development"}
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["project_id"] == "test-project"
            assert data["environment"] == "development"
            assert data["connected"] is True
            assert len(data["functions"]) == 1
            assert data["functions"][0]["name"] == "test_func"

    def test_get_status_default_environment(self, authenticated_client: TestClient):
        """Test getting connection status with default environment"""
        from rhesis.backend.app.services.connector.schemas import ConnectionStatus

        mock_status = ConnectionStatus(
            project_id="test-project",
            environment="development",
            connected=False,
            functions=[],
        )

        with patch("rhesis.backend.app.routers.connector.connection_manager") as mock_mgr:
            mock_mgr.get_connection_status = Mock(return_value=mock_status)

            response = authenticated_client.get("/connector/status/test-project")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["environment"] == "development"  # Default environment

    def test_receive_trace_success(self, authenticated_client: TestClient):
        """Test receiving execution trace"""
        trace_data = {
            "project_id": "test-project",
            "environment": "development",
            "function_name": "test_func",
            "status": "success",
            "duration_ms": 123.45,
            "inputs": {"param": "value"},
            "output": "success result",
            "error": None,
            "timestamp": 1704067200.0,  # Unix timestamp
        }

        response = authenticated_client.post("/connector/trace", json=trace_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"

    def test_receive_trace_with_error(self, authenticated_client: TestClient):
        """Test receiving execution trace with error"""
        trace_data = {
            "project_id": "test-project",
            "environment": "development",
            "function_name": "test_func",
            "status": "error",
            "duration_ms": 100.0,
            "inputs": {"param": "value"},
            "output": None,
            "error": "Something went wrong",
            "timestamp": 1704067200.0,  # Unix timestamp
        }

        response = authenticated_client.post("/connector/trace", json=trace_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"

    def test_receive_trace_with_long_output(self, authenticated_client: TestClient):
        """Test receiving execution trace with long output"""
        trace_data = {
            "project_id": "test-project",
            "environment": "development",
            "function_name": "test_func",
            "status": "success",
            "duration_ms": 50.0,
            "inputs": {},
            "output": "x" * 1000,  # Long output
            "error": None,
            "timestamp": 1704067200.0,  # Unix timestamp
        }

        response = authenticated_client.post("/connector/trace", json=trace_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"


@pytest.mark.integration
class TestConnectorIntegration:
    """Integration tests for connector functionality"""

    def test_full_trigger_flow(self, authenticated_client: TestClient):
        """Test complete flow: check status, trigger test, check status again"""
        from rhesis.backend.app.services.connector.schemas import ConnectionStatus

        project_id = "integration-test-project"
        environment = "development"

        with patch("rhesis.backend.app.routers.connector.connection_manager") as mock_mgr:
            # Initially not connected
            mock_mgr.is_connected = Mock(return_value=False)
            mock_mgr.get_connection_status = Mock(
                return_value=ConnectionStatus(
                    project_id=project_id,
                    environment=environment,
                    connected=False,
                    functions=[],
                )
            )

            # Check initial status
            response = authenticated_client.get(
                f"/connector/status/{project_id}", params={"environment": environment}
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["connected"] is False

            # Try to trigger test (should fail - not connected)
            response = authenticated_client.post(
                "/connector/trigger",
                json={
                    "project_id": project_id,
                    "environment": environment,
                    "function_name": "test_func",
                    "inputs": {},
                },
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND

            # Simulate connection
            mock_mgr.is_connected = Mock(return_value=True)
            mock_mgr.get_connection_status = Mock(
                return_value=ConnectionStatus(
                    project_id=project_id,
                    environment=environment,
                    connected=True,
                    functions=[],
                )
            )
            mock_mgr.send_test_request = AsyncMock(return_value=True)

            # Check status again
            response = authenticated_client.get(
                f"/connector/status/{project_id}", params={"environment": environment}
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["connected"] is True

            # Trigger test (should succeed now)
            response = authenticated_client.post(
                "/connector/trigger",
                json={
                    "project_id": project_id,
                    "environment": environment,
                    "function_name": "test_func",
                    "inputs": {"test": "data"},
                },
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["success"] is True


@pytest.mark.unit
class TestConnectorEdgeCases:
    """Test edge cases and error scenarios"""

    def test_trigger_with_missing_fields(self, authenticated_client: TestClient):
        """Test trigger request with missing required fields"""
        response = authenticated_client.post(
            "/connector/trigger",
            json={
                "project_id": "test-project",
                # Missing environment, function_name, inputs
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_trace_with_invalid_data(self, authenticated_client: TestClient):
        """Test trace endpoint with invalid data"""
        response = authenticated_client.post(
            "/connector/trace",
            json={
                "invalid": "data",
                # Missing required fields
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_status_nonexistent_project(self, authenticated_client: TestClient):
        """Test getting status for nonexistent project"""
        from rhesis.backend.app.services.connector.schemas import ConnectionStatus

        mock_status = ConnectionStatus(
            project_id="nonexistent",
            environment="development",
            connected=False,
            functions=[],
        )

        with patch("rhesis.backend.app.routers.connector.connection_manager") as mock_mgr:
            mock_mgr.get_connection_status = Mock(return_value=mock_status)

            response = authenticated_client.get("/connector/status/nonexistent")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["connected"] is False
