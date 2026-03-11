"""
Shared fixtures for Polyphemus tests.
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from rhesis.polyphemus.schemas import GenerateRequest, Message


@pytest.fixture
def mock_user() -> MagicMock:
    """A fake authenticated user for dependency injection."""
    user = MagicMock()
    user.id = "00000000-0000-0000-0000-000000000001"
    user.email = "test@example.com"
    return user


@pytest.fixture
def patched_models() -> Dict[str, str]:
    """The model map that resolve_model reads — returns configured aliases."""
    return {
        "polyphemus-default": "projects/123/locations/us-central1/endpoints/default",
        "polyphemus-opus": "projects/123/locations/us-central1/endpoints/opus",
    }


@pytest.fixture
def vertex_ok_response() -> MagicMock:
    """A minimal successful Vertex AI HTTP response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "This is a test response."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    return resp


@pytest.fixture
def vertex_error_response() -> MagicMock:
    """A 500 error response from Vertex AI."""
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "Internal Server Error"
    return resp


@pytest.fixture
def basic_generate_request() -> GenerateRequest:
    """A minimal valid GenerateRequest."""
    return GenerateRequest(messages=[Message(role="user", content="Hello, world!")])


@pytest.fixture
def full_generate_request() -> GenerateRequest:
    """A GenerateRequest with all optional fields set."""
    return GenerateRequest(
        messages=[
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Tell me a joke."),
        ],
        model="polyphemus-default",
        temperature=0.8,
        max_tokens=512,
        top_p=0.95,
        top_k=40,
        json_schema={
            "type": "object",
            "properties": {"joke": {"type": "string"}},
            "required": ["joke"],
        },
    )


@pytest.fixture
def mock_vertex_post(vertex_ok_response: MagicMock) -> AsyncMock:
    """An AsyncMock for _http_client.post that returns a 200 response."""
    return AsyncMock(return_value=vertex_ok_response)


def make_vertex_response(
    content: str, prompt_tokens: int = 10, completion_tokens: int = 20
) -> Dict[str, Any]:
    """Helper to build a Vertex AI-style response dict."""
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }
