import pytest
from uuid import uuid4
from datetime import datetime

from rhesis.backend.app.schemas.parameters import (
    ParameterSchema,
    ParameterField,
    TextValue,
    StringValue,
    IntegerValue,
    NumberValue,
    BooleanValue,
    EnumValue,
    ModelRefValue,
    SecretRefValue,
    validate_values_against_schema,
    canonical_hash,
    canonical_schema_fingerprint,
    ExperimentVersion,
)
from pydantic import ValidationError

def test_discriminator_parsing():
    field = ParameterField(name="test", type="string")
    assert field.name == "test"
    
    # Check that we can create union values correctly
    text_val = TextValue(type="text", value="hello")
    assert text_val.value == "hello"

def test_schema_validation():
    # Should fail if name is duplicated
    with pytest.raises(ValidationError) as exc_info:
        ParameterSchema(fields=[
            ParameterField(name="a", type="string"),
            ParameterField(name="a", type="integer"),
        ])
    assert "Duplicate parameter name" in str(exc_info.value)
    
    # Should fail if enum has no options
    with pytest.raises(ValidationError) as exc_info:
        ParameterSchema(fields=[
            ParameterField(name="e", type="enum"),
        ])
    assert "must have options" in str(exc_info.value)

    # Should fail if non-enum has options
    with pytest.raises(ValidationError) as exc_info:
        ParameterSchema(fields=[
            ParameterField(name="e", type="string", options=["a", "b"]),
        ])
    assert "cannot have options" in str(exc_info.value)
    
    # Should fail if default doesn't match type
    with pytest.raises(ValidationError) as exc_info:
        ParameterSchema(fields=[
            ParameterField(
                name="e", 
                type="string", 
                default=IntegerValue(type="integer", value=1)
            ),
        ])
    assert "does not match parameter type" in str(exc_info.value)
    
    # Should fail if default enum is not in options
    with pytest.raises(ValidationError) as exc_info:
        ParameterSchema(fields=[
            ParameterField(
                name="e", 
                type="enum", 
                options=["a", "b"],
                default=EnumValue(type="enum", value="c")
            ),
        ])
    assert "not in options for enum" in str(exc_info.value)

def test_validate_values_against_schema():
    schema = ParameterSchema(fields=[
        ParameterField(name="str_val", type="string", required=True),
        ParameterField(name="int_val", type="integer", required=False, default=IntegerValue(type="integer", value=42)),
        ParameterField(name="enum_val", type="enum", options=["yes", "no"]),
    ])
    
    # Valid raw dict
    raw = {
        "str_val": "hello",
        "enum_val": "yes"
    }
    
    result = validate_values_against_schema(raw, schema)
    assert result["str_val"].type == "string"
    assert result["str_val"].value == "hello"
    assert result["int_val"].type == "integer"
    assert result["int_val"].value == 42
    assert result["enum_val"].type == "enum"
    assert result["enum_val"].value == "yes"
    
    # Valid dict with discriminator types
    raw2 = {
        "str_val": {"type": "string", "value": "world"},
    }
    result2 = validate_values_against_schema(raw2, schema)
    assert result2["str_val"].value == "world"
    
    # Missing required
    with pytest.raises(ValueError, match="Missing required parameter"):
        validate_values_against_schema({}, schema)
        
    # Invalid enum
    with pytest.raises(ValueError, match="not in options for enum"):
        validate_values_against_schema({"str_val": "a", "enum_val": "maybe"}, schema)
        
    # Extra fields are ignored
    raw_extra = {
        "str_val": "hello",
        "extra": "ignored"
    }
    result3 = validate_values_against_schema(raw_extra, schema)
    assert "extra" not in result3

def test_canonical_hash_determinism():
    schema = ParameterSchema(fields=[
        ParameterField(name="a", type="string"),
        ParameterField(name="b", type="integer")
    ])
    
    fingerprint = canonical_schema_fingerprint(schema)
    
    # Same values constructed in different order
    val1 = {
        "a": StringValue(type="string", value="test"),
        "b": IntegerValue(type="integer", value=1),
    }
    val2 = {
        "b": IntegerValue(type="integer", value=1),
        "a": StringValue(type="string", value="test"),
    }
    
    hash1 = canonical_hash(fingerprint, val1)
    hash2 = canonical_hash(fingerprint, val2)
    assert hash1 == hash2

def test_experiment_version_forward_compat():
    # Should fill parent_version with None if missing
    user_id = uuid4()
    data = {
        "version": "v1",
        "schema_fingerprint": "f1",
        "values": {"a": {"type": "string", "value": "test"}},
        "created_at": datetime.now().isoformat(),
        "created_by_user_id": str(user_id)
    }
    
    version = ExperimentVersion.model_validate(data)
    assert version.parent_version is None
