"""
Endpoint Fixtures

Fixtures for creating endpoint entities including complex configurations.
"""

import pytest
from typing import Dict, Any
from fastapi import status
from fastapi.testclient import TestClient
from faker import Faker
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from ...endpoints import APIEndpoints

fake = Faker()


@pytest.fixture
def sample_endpoint(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    Create a sample endpoint for testing

    This fixture creates an endpoint that can be used for testing
    endpoint functionality and invocation.

    Returns:
        Dict containing the created endpoint data including its ID
    """
    endpoint_data = {
        "name": fake.word().title() + " Test Endpoint",
        "description": fake.text(max_nb_chars=100),
        "protocol": "REST",  # Valid enum value
        "url": f"https://api.{fake.domain_name()}/v1/test",
        "environment": "development",  # Valid enum value
        "config_source": "manual"  # Valid enum value
    }

    response = authenticated_client.post(APIEndpoints.ENDPOINTS.create, json=endpoint_data)
    assert response.status_code == status.HTTP_200_OK

    return response.json()


@pytest.fixture
def sample_endpoints(authenticated_client: TestClient) -> list[Dict[str, Any]]:
    """
    Create multiple sample endpoints for testing

    Useful for tests that need multiple endpoints or bulk operations.

    Returns:
        List of created endpoint dictionaries
    """
    endpoints = []
    protocols = ["REST", "WebSocket", "GRPC"]
    environments = ["development", "staging", "production"]

    for i in range(3):
        endpoint_data = {
            "name": f"{fake.word().title()} Endpoint {i+1}",
            "description": fake.text(max_nb_chars=100),
            "protocol": protocols[i % len(protocols)],
            "url": f"https://api-{i}.{fake.domain_name()}/v1/endpoint{i}",
            "environment": environments[i % len(environments)],
            "config_source": "manual"
        }

        response = authenticated_client.post(APIEndpoints.ENDPOINTS.create, json=endpoint_data)
        assert response.status_code == status.HTTP_200_OK
        endpoints.append(response.json())

    return endpoints


@pytest.fixture
def working_endpoint(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    Create a working endpoint for integration testing

    This fixture creates an endpoint that's configured to work with
    mocked external services for realistic testing scenarios.

    Returns:
        Dict containing the created working endpoint data
    """
    working_endpoint_data = {
        "name": "Working Test Endpoint",
        "description": "A properly configured endpoint for testing invocation",
        "protocol": "REST",
        "url": "https://api.example.com/v1/process",  # Mock-friendly URL
        "environment": "development",
        "config_source": "manual",
        "method": "POST",
        "request_headers": {
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        "request_body_template": {
            "query": "{{input}}",
            "context": {
                "session_id": "{{session_id}}",
                "timestamp": "{{timestamp}}"
            }
        },
        "response_mappings": {
            "result": "$.data.response",
            "confidence": "$.data.confidence"
        },
        "validation_rules": {
            "required_fields": ["input"],
            "max_input_length": 1000
        }
    }

    response = authenticated_client.post(APIEndpoints.ENDPOINTS.create, json=working_endpoint_data)
    assert response.status_code == status.HTTP_200_OK

    return response.json()


@pytest.fixture
def endpoint_with_complex_config(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    🔗⚙️ Create an endpoint with complex configuration for integration testing

    This fixture creates an endpoint with comprehensive configuration
    including auth, headers, mappings, and OpenAPI spec.

    Returns:
        Dict containing the endpoint with full configuration
    """
    complex_endpoint_data = {
        "name": "Complex API Endpoint",
        "description": "Endpoint with full configuration for comprehensive testing",
        "protocol": "REST",
        "url": f"https://complex-api.{fake.domain_name()}/v2/process",
        "environment": "staging",
        "config_source": "openapi",
        "openapi_spec_url": f"https://complex-api.{fake.domain_name()}/openapi.json",
        "openapi_spec": {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/process": {
                    "post": {
                        "summary": "Process data",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object", "properties": {"input": {"type": "string"}}}
                                }
                            }
                        }
                    }
                }
            }
        },
        "auth": {
            "type": "oauth2",
            "client_id": fake.uuid4(),
            "client_secret": fake.uuid4(),
            "token_url": f"https://auth.{fake.domain_name()}/oauth/token"
        },
        "request_headers": {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Version": "v2",
            "User-Agent": "Rhesis-Test-Client/1.0"
        },
        "input_mappings": {
            "query": "$.input",
            "context": "$.session_id",
            "metadata": {
                "timestamp": "$.timestamp",
                "version": "2.0"
            }
        },
        "response_mappings": {
            "result": "$.data.result",
            "confidence": "$.data.confidence",
            "processing_time": "$.metadata.duration"
        },
        "llm_suggestions": {
            "suggested_mappings": ["$.input -> $.query", "$.output -> $.result"],
            "confidence_score": 0.95
        }
    }

    response = authenticated_client.post(APIEndpoints.ENDPOINTS.create, json=complex_endpoint_data)
    assert response.status_code == status.HTTP_200_OK

    return response.json()


# Database Fixtures for direct database access tests

@pytest.fixture
def db_endpoint(test_db: Session, test_organization, db_user, db_status) -> Endpoint:
    """
    Create an endpoint in the test database

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture
        db_status: Status fixture

    Returns:
        Endpoint: Real endpoint record in database
    """
    from tests.backend.routes.fixtures.data_factories import EndpointDataFactory

    endpoint_data = EndpointDataFactory.sample_data()
    endpoint = Endpoint(
        name=endpoint_data["name"],
        description=endpoint_data["description"],
        protocol=endpoint_data["protocol"],
        url=endpoint_data["url"],
        environment=endpoint_data["environment"],
        config_source=endpoint_data["config_source"],
        method=endpoint_data["method"],
        endpoint_path=endpoint_data["endpoint_path"],
        request_headers=endpoint_data["request_headers"],
        query_params=endpoint_data["query_params"],
        request_body_template=endpoint_data["request_body_template"],
        response_format=endpoint_data["response_format"],
        response_mappings=endpoint_data["response_mappings"],
        validation_rules=endpoint_data["validation_rules"],
        auth_type=endpoint_data["auth_type"],
        auth=endpoint_data["auth"],
        organization_id=test_organization.id,
        user_id=db_user.id,
        status_id=db_status.id
    )

    test_db.add(endpoint)
    test_db.flush()
    test_db.refresh(endpoint)
    return endpoint


@pytest.fixture
def db_endpoint_minimal(test_db: Session, test_organization, db_user) -> Endpoint:
    """
    Create a minimal endpoint in the test database

    Only includes required fields for basic testing.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture

    Returns:
        Endpoint: Minimal endpoint record in database
    """
    from tests.backend.routes.fixtures.data_factories import EndpointDataFactory

    endpoint_data = EndpointDataFactory.minimal_data()
    endpoint = Endpoint(
        name=endpoint_data["name"],
        protocol=endpoint_data["protocol"],
        url=endpoint_data["url"],
        organization_id=test_organization.id,
        user_id=db_user.id
    )

    test_db.add(endpoint)
    test_db.flush()
    test_db.refresh(endpoint)
    return endpoint


@pytest.fixture
def db_endpoint_rest(test_db: Session, test_organization, db_user, db_status) -> Endpoint:
    """
    Create a REST endpoint in the test database

    Specifically configured for REST API testing.

    Args:
        test_db: Database session fixture
        test_organization: Organization fixture
        db_user: User fixture
        db_status: Status fixture

    Returns:
        Endpoint: REST endpoint record in database
    """
    endpoint = Endpoint(
        name="Test REST API",
        description="REST endpoint for testing",
        protocol="REST",
        url="https://api.example.com/v1",
        method="GET",
        endpoint_path="/users",
        request_headers={"Content-Type": "application/json"},
        response_format="json",
        organization_id=test_organization.id,
        user_id=db_user.id,
        status_id=db_status.id
    )

    test_db.add(endpoint)
    test_db.flush()
    test_db.refresh(endpoint)
    return endpoint
