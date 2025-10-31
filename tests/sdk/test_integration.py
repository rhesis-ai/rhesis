from rhesis.sdk.client import Endpoints, Methods


def test_integration_client_works(integration_client):
    response = integration_client.send_request(endpoint=Endpoints.HEALTH, method=Methods.GET)
    assert response["status"] == "ok"
