"""Integration tests for SDK client functionality."""

from rhesis.sdk.client import Client, Endpoints, Methods


def test_integration_client_works(docker_compose_test_env, db_cleanup):
    """Test that the SDK client can connect to the backend."""
    client = Client()
    response = client.send_request(endpoint=Endpoints.HEALTH, method=Methods.GET)
    assert response["status"] == "ok"
