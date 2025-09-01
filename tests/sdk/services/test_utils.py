import pytest
from jsonschema import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from rhesis.sdk.services.utils import validate_llm_response


def test_validate_llm_response():
    print("test")
    # schmema need to contains json_schema key, as it is OpenAI json schema format
    json_schema = {
        "json_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
            "required": ["name", "age"],
        }
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
