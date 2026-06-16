import logging
from typing import Type, Union

import jsonschema
import requests
from pydantic import BaseModel
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def validate_llm_response(data: dict, schema: Union[Type[BaseModel], dict]) -> dict:
    """
    Validate the response from the LLM.
    Schema should be a Pydantic model or OpenAI-wrapped JSON schema.
    """
    # Check if it's a Pydantic model class
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        schema.model_validate(data)
    elif isinstance(schema, dict):
        # OpenAI format: {"type": "json_schema", "json_schema": {...}}
        jsonschema.validate(data, schema["json_schema"]["schema"])


def _is_retryable_exception(exc: BaseException) -> bool:
    """Check if exception is a transient error worth retrying.

    Retries on:
    - Connection errors and timeouts
    - HTTP 429 (rate limit), 500, 502, 503, 504 (server errors), regardless of
      whether the error comes from ``requests`` or from an LLM SDK
      (litellm/openai ``RateLimitError``, ``APIStatusError``, …), which expose
      the HTTP status via a ``status_code`` attribute rather than a ``response``.

    Does NOT retry on:
    - Client errors (400, 401, 403, 404)
    - Non-HTTP exceptions
    """
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    # litellm / openai errors (e.g. RateLimitError -> 429) are not `requests`
    # exceptions but carry the HTTP status on `status_code`.
    return getattr(exc, "status_code", None) in RETRYABLE_STATUS_CODES


llm_retry = retry(
    retry=retry_if_exception(_is_retryable_exception),
    stop=stop_after_attempt(4),  # 1 initial + 3 retries
    wait=wait_exponential_jitter(initial=1, max=60, jitter=2),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
