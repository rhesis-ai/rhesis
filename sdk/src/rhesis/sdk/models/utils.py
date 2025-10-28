from typing import Type, Union

import jsonschema
from pydantic import BaseModel


def validate_llm_response(data: dict, schema: Union[Type[BaseModel], dict]) -> dict:
    """Validate the response from the LLM. Schema should be a Pydantic model or OpenAI-wrapped JSON schema"""
    # Check if it's a Pydantic model class
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        schema.model_validate(data)
    elif isinstance(schema, dict):
        # OpenAI format: {"type": "json_schema", "json_schema": {"name": "...", "schema": {...}, "strict": true}}
        jsonschema.validate(data, schema["json_schema"]["schema"])
