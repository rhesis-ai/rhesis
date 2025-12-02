"""Fixtures for mapping tests."""

from typing import Any, Dict
from unittest.mock import Mock

import pytest


@pytest.fixture
def standard_function_signature() -> Dict[str, Any]:
    """Function with standard naming (should auto-map with high confidence)."""
    return {
        "name": "chat",
        "parameters": {
            "input": {"type": "string", "required": True},
            "session_id": {"type": "string", "required": False, "default": None},
            "context": {"type": "list", "required": False, "default": []},
        },
        "return_type": "dict",
        "metadata": {"description": "Standard chat function"},
    }


@pytest.fixture
def custom_function_signature() -> Dict[str, Any]:
    """Function with custom naming (should trigger LLM fallback)."""
    return {
        "name": "process_query",
        "parameters": {
            "user_message": {"type": "string", "required": True},
            "conv_id": {"type": "string", "required": False, "default": None},
            "docs": {"type": "list", "required": False, "default": []},
        },
        "return_type": "dict",
        "metadata": {"description": "Custom named chat function"},
    }


@pytest.fixture
def partial_match_function_signature() -> Dict[str, Any]:
    """Function with partial pattern matches."""
    return {
        "name": "analyze",
        "parameters": {
            "question": {"type": "string", "required": True},
            "conversation": {"type": "string", "required": False, "default": None},
        },
        "return_type": "dict",
        "metadata": {"description": "Analyze user question"},
    }


@pytest.fixture
def minimal_function_signature() -> Dict[str, Any]:
    """Function with only required input parameter."""
    return {
        "name": "echo",
        "parameters": {
            "text": {"type": "string", "required": True},
        },
        "return_type": "string",
        "metadata": {"description": "Echo the input"},
    }


@pytest.fixture
def mock_endpoint():
    """Mock endpoint for testing."""
    endpoint = Mock()
    endpoint.id = "endpoint-123"
    endpoint.request_mapping = None
    endpoint.response_mapping = None
    endpoint.endpoint_metadata = {}
    return endpoint


@pytest.fixture
def mock_endpoint_with_existing_mappings():
    """Mock endpoint with existing mappings (should be preserved)."""
    endpoint = Mock()
    endpoint.id = "endpoint-456"
    endpoint.request_mapping = {
        "custom_param": "{{ input }}",
        "session": "{{ session_id }}",
    }
    endpoint.response_mapping = {
        "output": "$.result.text",
        "session_id": "$.session_info.id",
    }
    endpoint.endpoint_metadata = {
        "mapping_info": {
            "source": "manual",
            "confidence": 1.0,
        }
    }
    return endpoint


@pytest.fixture
def sdk_metadata_with_manual_mappings() -> Dict[str, Any]:
    """SDK metadata with manual mappings from @collaborate decorator."""
    return {
        "description": "Chat function with manual mappings",
        "request_mapping": {
            "user_query": "{{ input }}",
            "conv_id": "{{ session_id }}",
            "docs": "{{ context }}",
        },
        "response_mapping": {
            "output": "{{ jsonpath('$.result.text') }}",
            "session_id": "$.conv_id",
            "context": "$.sources",
        },
    }


@pytest.fixture
def mock_user():
    """Mock user for LLM generation."""
    user = Mock()
    user.id = "user-789"
    user.user_settings = {
        "default_generation_model": "gpt-4",
    }
    return user


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    db = Mock()
    return db
