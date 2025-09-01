from typing import Union

import jsonschema
from pydantic import BaseModel


def validate_llm_response(data: dict, schema: Union[BaseModel, dict]) -> dict:
    if isinstance(schema, BaseModel):
        data = schema.model_validate(data)
    elif isinstance(schema, dict):
        data = jsonschema.validate(data, schema["json_schema"])
    return data
