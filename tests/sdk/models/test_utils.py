from unittest.mock import MagicMock

import aiohttp
import pytest
import requests
from jsonschema import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from rhesis.sdk.models.utils import _is_retryable_exception, validate_llm_response


def test_validate_llm_response():
    # Schema needs to be in OpenAI json_schema format
    json_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "TestSchema",
            "schema": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
                "required": ["name", "age"],
            },
            "strict": True,
        },
    }

    class PydanticSchema(BaseModel):
        name: str
        age: int

    # Validate json schema with correct data
    validate_llm_response(
        {"name": "John", "age": 30},
        json_schema,
    )
    # Validate with json shcema with incorrect data
    with pytest.raises(JsonSchemaValidationError):
        validate_llm_response(
            {"name": "John", "age": "thirty"},
            json_schema,
        )
    # Validate with pydantic schema with correct data
    validate_llm_response(
        {"name": "John", "age": 30},
        PydanticSchema,
    )
    # Validate with pydantic schema with incorrect data
    with pytest.raises(PydanticValidationError):
        validate_llm_response(
            {"name": "John", "age": "thirty"},
            PydanticSchema,
        )
    # with pytest.raises(Failed):
    #     )


class TestIsRetryableException:
    """_is_retryable_exception must recognise errors from both requests and aiohttp."""

    def test_requests_connection_error(self):
        assert _is_retryable_exception(requests.exceptions.ConnectionError()) is True

    def test_requests_timeout(self):
        assert _is_retryable_exception(requests.exceptions.Timeout()) is True

    def test_requests_http_504(self):
        resp = MagicMock()
        resp.status_code = 504
        exc = requests.exceptions.HTTPError(response=resp)
        assert _is_retryable_exception(exc) is True

    def test_requests_http_404_is_not_retryable(self):
        resp = MagicMock()
        resp.status_code = 404
        exc = requests.exceptions.HTTPError(response=resp)
        assert _is_retryable_exception(exc) is False

    def test_aiohttp_504(self):
        exc = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=504, message="Gateway Time-out"
        )
        assert _is_retryable_exception(exc) is True

    def test_aiohttp_502(self):
        exc = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=502, message="Bad Gateway"
        )
        assert _is_retryable_exception(exc) is True

    def test_aiohttp_429(self):
        exc = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=429, message="Too Many Requests"
        )
        assert _is_retryable_exception(exc) is True

    def test_aiohttp_404_is_not_retryable(self):
        exc = aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=404, message="Not Found"
        )
        assert _is_retryable_exception(exc) is False

    def test_litellm_status_code_attribute(self):
        exc = Exception("rate limit")
        exc.status_code = 429
        assert _is_retryable_exception(exc) is True

    def test_plain_exception_is_not_retryable(self):
        assert _is_retryable_exception(ValueError("bad value")) is False
