from typing import Union

import jsonschema
from pydantic import BaseModel


def validate_llm_response(data: dict, schema: Union[BaseModel, dict]) -> dict:
    """Validate the response from the LLM. Schema should be a Pydantic model or an OpenAI schema"""
    if issubclass(schema, BaseModel):
        schema.model_validate(data)
    elif isinstance(schema, dict):
        jsonschema.validate(data, schema["json_schema"])
