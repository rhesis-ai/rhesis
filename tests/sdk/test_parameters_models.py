"""Unit tests for SDK parameter models.

Covers:
- Discriminated-union round-trip (all 8 types)
- Canonical hashing determinism
- validate_values_against_schema
- ResolvedParameters typed accessors
- JSON-schema parity with backend (structure check)
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from rhesis.sdk.models.parameters import (
    BooleanValue,
    EnumValue,
    IntegerValue,
    ModelRefValue,
    NumberValue,
    ParameterField,
    ParameterSchema,
    ParameterValue,
    ResolvedParameters,
    ResolveResponse,
    SecretRefValue,
    StringValue,
    TextValue,
    canonical_hash,
    canonical_schema_fingerprint,
    canonical_version,
    validate_values_against_schema,
)


# ------------------------------------------------------------------ #
# Discriminated union round-trip                                      #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "model,expected_type,expected_value",
    [
        (TextValue(value="hello"), "text", "hello"),
        (StringValue(value="world"), "string", "world"),
        (IntegerValue(value=42), "integer", 42),
        (NumberValue(value=3.14), "number", 3.14),
        (BooleanValue(value=True), "boolean", True),
        (EnumValue(value="option_a"), "enum", "option_a"),
    ],
)
def test_discriminated_union_round_trip(model, expected_type, expected_value):
    """Each typed value round-trips through JSON and back."""
    dumped = model.model_dump(mode="json")
    assert dumped == {"type": expected_type, "value": expected_value}

    # Re-validate as the union via model_validate
    from pydantic import TypeAdapter

    adapter = TypeAdapter(ParameterValue)
    restored = adapter.validate_python(dumped)
    assert restored.type == expected_type
    assert restored.value == expected_value


def test_model_ref_round_trip():
    uid = uuid4()
    m = ModelRefValue(value=uid)
    dumped = m.model_dump(mode="json")
    assert dumped["type"] == "model_ref"
    assert dumped["value"] == str(uid)


def test_secret_ref_round_trip():
    uid = uuid4()
    m = SecretRefValue(value=uid)
    dumped = m.model_dump(mode="json")
    assert dumped["type"] == "secret_ref"
    assert dumped["value"] == str(uid)


# ------------------------------------------------------------------ #
# Schema validation                                                   #
# ------------------------------------------------------------------ #


def _make_schema(*fields: ParameterField) -> ParameterSchema:
    return ParameterSchema(fields=list(fields))


def test_validate_values_coerces_bare_values():
    schema = _make_schema(
        ParameterField(name="temp", type="number"),
        ParameterField(name="model", type="string"),
    )
    result = validate_values_against_schema(
        {"temp": 0.7, "model": "gpt-4o"}, schema
    )
    assert result["temp"].type == "number"
    assert result["temp"].value == 0.7
    assert result["model"].type == "string"
    assert result["model"].value == "gpt-4o"


def test_validate_values_fills_defaults():
    schema = _make_schema(
        ParameterField(
            name="temp",
            type="number",
            default=NumberValue(value=0.5),
        ),
    )
    result = validate_values_against_schema({}, schema)
    assert result["temp"].value == 0.5


def test_validate_values_drops_unknown():
    schema = _make_schema(
        ParameterField(name="temp", type="number"),
    )
    result = validate_values_against_schema(
        {"temp": 1.0, "unknown": "ignored"}, schema
    )
    assert "unknown" not in result
    assert result["temp"].value == 1.0


def test_validate_values_raises_on_missing_required():
    schema = _make_schema(
        ParameterField(name="temp", type="number", required=True),
    )
    with pytest.raises(ValueError, match="Missing required"):
        validate_values_against_schema({}, schema)


def test_validate_values_raises_on_type_mismatch():
    schema = _make_schema(
        ParameterField(name="temp", type="number"),
    )
    with pytest.raises(ValueError, match="Type mismatch"):
        validate_values_against_schema(
            {"temp": {"type": "string", "value": "oops"}}, schema
        )


def test_validate_enum_checks_options():
    schema = _make_schema(
        ParameterField(
            name="mode", type="enum", options=["a", "b"],
        ),
    )
    with pytest.raises(ValueError, match="not in options"):
        validate_values_against_schema({"mode": "c"}, schema)


def test_schema_rejects_duplicate_names():
    with pytest.raises(ValueError, match="Duplicate"):
        _make_schema(
            ParameterField(name="foo", type="string"),
            ParameterField(name="foo", type="string"),
        )


def test_schema_rejects_non_snake_case():
    with pytest.raises(ValueError, match="snake_case"):
        _make_schema(ParameterField(name="CamelCase", type="string"))


def test_schema_rejects_enum_without_options():
    with pytest.raises(ValueError, match="must have options"):
        _make_schema(ParameterField(name="mode", type="enum"))


# ------------------------------------------------------------------ #
# Canonical hashing                                                   #
# ------------------------------------------------------------------ #


def test_hash_determinism():
    """Same input must produce the same hash regardless of dict order."""
    schema = _make_schema(
        ParameterField(name="a", type="string"),
        ParameterField(name="b", type="integer"),
    )
    values_1 = {"a": "hello", "b": 42}
    values_2 = {"b": 42, "a": "hello"}  # reversed order

    h1 = canonical_version(values_1, schema)
    h2 = canonical_version(values_2, schema)
    assert h1 == h2
    assert h1.startswith("v_")


def test_hash_changes_on_value_change():
    schema = _make_schema(
        ParameterField(name="a", type="string"),
    )
    h1 = canonical_version({"a": "hello"}, schema)
    h2 = canonical_version({"a": "world"}, schema)
    assert h1 != h2


def test_fingerprint_changes_on_schema_change():
    s1 = _make_schema(ParameterField(name="a", type="string"))
    s2 = _make_schema(
        ParameterField(name="a", type="string"),
        ParameterField(name="b", type="integer"),
    )
    assert canonical_schema_fingerprint(s1) != canonical_schema_fingerprint(s2)


# ------------------------------------------------------------------ #
# ResolvedParameters                                                  #
# ------------------------------------------------------------------ #


def _make_resolved(**overrides) -> ResolvedParameters:
    defaults = dict(
        values={
            "temp": NumberValue(value=0.7),
            "model": StringValue(value="gpt-4o"),
            "enabled": BooleanValue(value=True),
            "prompt": TextValue(value="be helpful"),
            "mode": EnumValue(value="text"),
            "count": IntegerValue(value=10),
        },
        experiment_id=uuid4(),
        version="v_abc123",
        source="label",
        source_label="default",
    )
    defaults.update(overrides)
    return ResolvedParameters(**defaults)


def test_resolved_mapping_protocol():
    r = _make_resolved()
    assert r["temp"] == 0.7
    assert r["model"] == "gpt-4o"
    assert len(r) == 6
    assert "temp" in r
    assert "missing" not in r
    assert set(r) == {"temp", "model", "enabled", "prompt", "mode", "count"}


def test_resolved_get_with_default():
    r = _make_resolved()
    assert r.get("missing", "fallback") == "fallback"
    assert r.get("temp") == 0.7


def test_resolved_typed_accessors():
    r = _make_resolved()
    assert r.get_number("temp") == 0.7
    assert r.get_string("model") == "gpt-4o"
    assert r.get_boolean("enabled") is True
    assert r.get_text("prompt") == "be helpful"
    assert r.get_enum("mode") == "text"
    assert r.get_integer("count") == 10


def test_resolved_typed_accessor_missing_returns_default():
    r = _make_resolved()
    assert r.get_string("missing") is None
    assert r.get_string("missing", "fallback") == "fallback"


def test_resolved_typed_accessor_type_mismatch_raises():
    r = _make_resolved()
    with pytest.raises(TypeError, match="'number', not 'string'"):
        r.get_string("temp")


def test_resolved_as_native():
    r = _make_resolved()
    native = r.as_native()
    assert native["temp"] == 0.7
    assert native["model"] == "gpt-4o"
    assert isinstance(native, dict)


def test_resolved_repr_masks_secrets():
    r = ResolvedParameters(
        values={"api_key": SecretRefValue(value=uuid4())},
        experiment_id=uuid4(),
        version="v_x",
        source="label",
    )
    rep = repr(r)
    assert "<secret>" in rep
    assert str(r._typed["api_key"].value) not in rep


def test_resolved_from_response():
    resp = ResolveResponse(
        schema=_make_schema(ParameterField(name="a", type="string")),
        values={"a": StringValue(value="hello")},
        experiment_id=uuid4(),
        version="v_test",
        source="label",
        source_label="default",
    )
    r = ResolvedParameters.from_response(resp)
    assert r["a"] == "hello"
    assert r.version == "v_test"
    assert r.source_label == "default"


def test_resolved_provenance_fields():
    eid = uuid4()
    r = _make_resolved(
        experiment_id=eid,
        version="v_abc",
        source="label",
        source_label="production",
    )
    assert r.experiment_id == eid
    assert r.version == "v_abc"
    assert r.source == "label"
    assert r.source_label == "production"


# ------------------------------------------------------------------ #
# Option A: Bare default coercion in ParameterField                   #
# ------------------------------------------------------------------ #


def test_parameter_field_bare_default_number():
    f = ParameterField(name="temp", type="number", default=0.7)
    assert f.default is not None
    assert f.default.type == "number"
    assert f.default.value == 0.7


def test_parameter_field_bare_default_string():
    f = ParameterField(name="name", type="string", default="hello")
    assert f.default.type == "string"
    assert f.default.value == "hello"


def test_parameter_field_bare_default_integer():
    f = ParameterField(name="count", type="integer", default=42)
    assert f.default.type == "integer"
    assert f.default.value == 42


def test_parameter_field_bare_default_boolean():
    f = ParameterField(name="flag", type="boolean", default=True)
    assert f.default.type == "boolean"
    assert f.default.value is True


def test_parameter_field_bare_default_enum():
    f = ParameterField(
        name="mode", type="enum", default="fast", options=["fast", "slow"]
    )
    assert f.default.type == "enum"
    assert f.default.value == "fast"


def test_parameter_field_typed_default_still_works():
    """Explicit typed dict should still work (backwards compat)."""
    f = ParameterField(
        name="temp", type="number",
        default={"type": "number", "value": 0.5},
    )
    assert f.default.type == "number"
    assert f.default.value == 0.5


def test_parameter_field_pydantic_model_default_still_works():
    """Passing a Pydantic model instance should still work."""
    f = ParameterField(
        name="temp", type="number",
        default=NumberValue(value=0.9),
    )
    assert f.default.type == "number"
    assert f.default.value == 0.9


def test_parameter_field_none_default_untouched():
    f = ParameterField(name="temp", type="number")
    assert f.default is None


def test_bare_default_in_schema_validation():
    """Bare defaults should work through full schema validation."""
    schema = _make_schema(
        ParameterField(name="temp", type="number", default=0.7),
    )
    result = validate_values_against_schema({}, schema)
    assert result["temp"].value == 0.7


# ------------------------------------------------------------------ #
# Option B: get_str() accessor                                        #
# ------------------------------------------------------------------ #


def test_get_str_on_text():
    r = _make_resolved()
    assert r.get_str("prompt") == "be helpful"


def test_get_str_on_string():
    r = _make_resolved()
    assert r.get_str("model") == "gpt-4o"


def test_get_str_missing_returns_default():
    r = _make_resolved()
    assert r.get_str("missing") is None
    assert r.get_str("missing", "fallback") == "fallback"


def test_get_str_type_mismatch_raises():
    r = _make_resolved()
    with pytest.raises(TypeError, match="not 'text' or 'string'"):
        r.get_str("temp")
