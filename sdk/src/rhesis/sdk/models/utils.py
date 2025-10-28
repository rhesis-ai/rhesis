from typing import Union

import jsonschema
from pydantic import BaseModel


def validate_llm_response(data: dict, schema: Union[BaseModel, dict]) -> dict:
    """Validate the response from the LLM. Schema should be a Pydantic model or JSON schema (wrapped or plain)"""
    # Check if it's a Pydantic model class
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        schema.model_validate(data)
    elif isinstance(schema, dict):
        # Handle both plain JSON schema and OpenAI-wrapped format
        if "json_schema" in schema:
            # OpenAI format: {"type": "json_schema", "json_schema": {"name": "...", "schema": {...}, "strict": true}}
            jsonschema.validate(data, schema["json_schema"]["schema"])
        else:
            # Plain JSON schema format
            jsonschema.validate(data, schema)
