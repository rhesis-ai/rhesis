from typing import Union

import jsonschema
from pydantic import BaseModel


def validate_llm_response(data: dict, schema: Union[BaseModel, dict]) -> dict:
    if issubclass(schema, BaseModel):
        schema.model_validate(data)
    elif isinstance(schema, dict):
        jsonschema.validate(data, schema["json_schema"])
