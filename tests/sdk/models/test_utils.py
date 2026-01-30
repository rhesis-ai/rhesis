import pytest
from jsonschema import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from rhesis.sdk.models.utils import validate_llm_response


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
