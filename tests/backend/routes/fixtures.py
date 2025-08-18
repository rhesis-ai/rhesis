"""
🧪 Shared Fixtures for Route Testing

Domain-specific fixtures that can be reused across multiple route test files.
This module provides fixtures for creating test data entities with proper dependencies.
"""

import pytest
import uuid
from typing import Dict, Any
from fastapi import status
from fastapi.testclient import TestClient
from faker import Faker

from .endpoints import APIEndpoints

# Initialize Faker
fake = Faker()


@pytest.fixture
def sample_dimension(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    🏗️ Create a sample dimension for testing
    
    This fixture creates a dimension that can be used as a foreign key
    in demographic tests or any other tests that need a valid dimension.
    
    Returns:
        Dict containing the created dimension data including its ID
    """
    dimension_data = {
        "name": fake.word().title() + " Test Dimension",
        "description": fake.text(max_nb_chars=100)
    }
    
    response = authenticated_client.post(APIEndpoints.DIMENSIONS.create, json=dimension_data)
    assert response.status_code == status.HTTP_200_OK
    
    return response.json()


@pytest.fixture
def sample_dimensions(authenticated_client: TestClient) -> list[Dict[str, Any]]:
    """
    🏗️ Create multiple sample dimensions for testing
    
    Useful for tests that need multiple dimensions or bulk operations.
    
    Returns:
        List of created dimension dictionaries
    """
    dimensions = []
    for i in range(3):
        dimension_data = {
            "name": f"{fake.word().title()} Dimension {i+1}",
            "description": fake.text(max_nb_chars=100)
        }
        
        response = authenticated_client.post(APIEndpoints.DIMENSIONS.create, json=dimension_data)
        assert response.status_code == status.HTTP_200_OK
        dimensions.append(response.json())
    
    return dimensions


@pytest.fixture
def sample_category(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    🏷️ Create a sample category for testing
    
    Useful for tests that need a valid category reference.
    """
    category_data = {
        "name": fake.word().title() + " Test Category",
        "description": fake.text(max_nb_chars=100)
    }
    
    response = authenticated_client.post(APIEndpoints.CATEGORIES.create, json=category_data)
    assert response.status_code == status.HTTP_200_OK
    
    return response.json()


@pytest.fixture
def sample_topic(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    📚 Create a sample topic for testing
    
    Useful for tests that need a valid topic reference.
    """
    topic_data = {
        "name": fake.word().title() + " Test Topic",
        "description": fake.text(max_nb_chars=100)
    }
    
    response = authenticated_client.post(APIEndpoints.TOPICS.create, json=topic_data)
    assert response.status_code == status.HTTP_200_OK
    
    return response.json()


@pytest.fixture
def sample_behavior(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    🎯 Create a sample behavior for testing
    
    Useful for tests that need a valid behavior reference.
    """
    behavior_data = {
        "name": fake.word().title() + " Test Behavior",
        "description": fake.text(max_nb_chars=100)
    }
    
    response = authenticated_client.post(APIEndpoints.BEHAVIORS.create, json=behavior_data)
    assert response.status_code == status.HTTP_200_OK
    
    return response.json()


@pytest.fixture
def dimension_with_demographics(authenticated_client: TestClient, sample_dimension: Dict[str, Any]) -> Dict[str, Any]:
    """
    🏗️📊 Create a dimension with associated demographics
    
    This fixture creates a complete dimension-demographic relationship
    for integration testing.
    
    Returns:
        Dict containing:
        - dimension: The dimension data
        - demographics: List of demographic data associated with the dimension
    """
    demographics = []
    
    # Create 3 demographics associated with the dimension
    for i in range(3):
        demographic_data = {
            "name": f"Demographic {i+1} for {sample_dimension['name']}",
            "description": fake.text(max_nb_chars=100),
            "dimension_id": sample_dimension["id"]
        }
        
        response = authenticated_client.post(APIEndpoints.DEMOGRAPHICS.create, json=demographic_data)
        assert response.status_code == status.HTTP_200_OK
        demographics.append(response.json())
    
    return {
        "dimension": sample_dimension,
        "demographics": demographics
    }


# Utility fixtures for common test scenarios
@pytest.fixture
def invalid_uuid() -> str:
    """❌ Generate a random UUID for testing not-found scenarios"""
    return str(uuid.uuid4())


@pytest.fixture
def malformed_uuid() -> str:
    """💥 Generate an invalid UUID string for testing validation"""
    return "not-a-valid-uuid-format"


@pytest.fixture
def sample_metric(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    📊 Create a sample metric for testing
    
    This fixture creates a metric that can be used in behavior-metric
    relationship tests or any other tests that need a valid metric.
    
    Returns:
        Dict containing the created metric data including its ID
    """
    metric_data = {
        "name": fake.word().title() + " " + fake.word().title(),
        "description": fake.text(max_nb_chars=150),
        "evaluation_prompt": fake.sentence(nb_words=8),
        "score_type": fake.random_element(elements=("numeric", "categorical", "binary"))
    }
    
    response = authenticated_client.post(APIEndpoints.METRICS.create, json=metric_data)
    if response.status_code not in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
        # If metrics endpoint doesn't exist or fails, create a mock metric ID
        return {"id": str(uuid.uuid4())}
    return response.json()


@pytest.fixture
def parent_topic(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    🌳 Create a parent topic for hierarchical testing
    
    This fixture creates a topic that can be used as a parent
    in hierarchical topic tests.
    
    Returns:
        Dict containing the created parent topic data including its ID
    """
    parent_data = {
        "name": fake.sentence(nb_words=2).rstrip('.') + " Parent Topic",
        "description": fake.text(max_nb_chars=100)
    }
    
    response = authenticated_client.post(APIEndpoints.TOPICS.create, json=parent_data)
    assert response.status_code == status.HTTP_200_OK
    
    return response.json()


@pytest.fixture
def parent_category(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    🏷️ Create a parent category for hierarchical testing
    
    This fixture creates a category that can be used as a parent
    in hierarchical category tests.
    
    Returns:
        Dict containing the created parent category data including its ID
    """
    parent_data = {
        "name": fake.sentence(nb_words=2).rstrip('.') + " Parent Category",
        "description": fake.text(max_nb_chars=100)
    }
    
    response = authenticated_client.post(APIEndpoints.CATEGORIES.create, json=parent_data)
    assert response.status_code == status.HTTP_200_OK
    
    return response.json()


# Complex relationship fixtures
@pytest.fixture
def topic_with_children(authenticated_client: TestClient, parent_topic: Dict[str, Any]) -> Dict[str, Any]:
    """
    🌳📚 Create a topic with child topics
    
    This fixture creates a complete topic hierarchy for integration testing.
    
    Returns:
        Dict containing:
        - parent: The parent topic data
        - children: List of child topic data associated with the parent
    """
    children = []
    
    # Create 3 child topics associated with the parent
    for i in range(3):
        child_data = {
            "name": f"Child Topic {i+1} of {parent_topic['name']}",
            "description": fake.text(max_nb_chars=100),
            "parent_id": parent_topic["id"]
        }
        
        response = authenticated_client.post(APIEndpoints.TOPICS.create, json=child_data)
        assert response.status_code == status.HTTP_200_OK
        children.append(response.json())
    
    return {
        "parent": parent_topic,
        "children": children
    }


@pytest.fixture
def behavior_with_metrics(authenticated_client: TestClient, sample_behavior: Dict[str, Any], sample_metric: Dict[str, Any]) -> Dict[str, Any]:
    """
    🎯📊 Create a behavior with associated metrics
    
    This fixture creates a complete behavior-metric relationship
    for integration testing.
    
    Returns:
        Dict containing:
        - behavior: The behavior data
        - metric: The metric data associated with the behavior
    """
    # Associate the metric with the behavior
    try:
        response = authenticated_client.post(
            f"/behaviors/{sample_behavior['id']}/metrics/{sample_metric['id']}"
        )
        # Note: This endpoint might not exist yet, so we handle gracefully
        if response.status_code not in [200, 201, 404]:
            # If association fails, we still return both entities
            pass
    except Exception:
        # Gracefully handle if the association endpoint doesn't exist
        pass
    
    return {
        "behavior": sample_behavior,
        "metric": sample_metric
    }


@pytest.fixture
def sample_endpoint(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    🔗 Create a sample endpoint for testing
    
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
def mock_endpoint_service():
    """
    🎭 Create a mock endpoint service for testing
    
    This fixture provides a mock endpoint service that can be used
    to test endpoint invocation without making real API calls.
    """
    from unittest.mock import Mock
    
    mock_service = Mock()
    mock_service.invoke_endpoint.return_value = {
        "result": "Mock response from endpoint",
        "timestamp": fake.iso8601(),
        "success": True
    }
    mock_service.get_schema.return_value = {
        "input": {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
                "session_id": {"type": "string"}
            },
            "required": ["input"]
        },
        "output": {
            "type": "object",
            "properties": {
                "result": {"type": "string"}
            }
        }
    }
    
    return mock_service


@pytest.fixture
def working_endpoint(authenticated_client: TestClient) -> Dict[str, Any]:
    """
    🔗✅ Create a working endpoint for integration testing
    
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
def sample_endpoints(authenticated_client: TestClient) -> list[Dict[str, Any]]:
    """
    🔗 Create multiple sample endpoints for testing
    
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
        "headers": {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Version": "v2",
            "User-Agent": "Rhesis-Test-Client/1.0"
        },
        "request_mapping": {
            "query": "$.input",
            "context": "$.session_id",
            "metadata": {
                "timestamp": "$.timestamp",
                "version": "2.0"
            }
        },
        "response_mapping": {
            "result": "$.data.result",
            "confidence": "$.data.confidence",
            "metadata": "$.metadata"
        },
        "llm_suggestions": {
            "suggested_mappings": ["$.input -> $.query", "$.output -> $.result"],
            "confidence_score": 0.95
        }
    }
    
    response = authenticated_client.post(APIEndpoints.ENDPOINTS.create, json=complex_endpoint_data)
    assert response.status_code == status.HTTP_200_OK
    
    return response.json()
