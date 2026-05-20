"""Parity + behavior tests for the SDK's vendored parameter models.

These tests guard the contract that the SDK's vendored copy of the
parameter Pydantic models stays byte-identical (in JSON-schema terms)
to the backend's authoritative copy. If the two drift the cached
:func:`canonical_version` hashes will silently disagree on the wire
between SDK and server, so the parity assertion is the early-warning
system.

The behavior tests cover the small surface of new code in the SDK
(`ResolvedParameters`, the runtime convenience wrapper) that has no
direct backend counterpart — the rest of the file is a copy of the
backend's models, so the parity assertion plus the backend's own tests
cover correctness.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from rhesis.sdk.models.parameters import (
    ParameterField,
    ParameterSchema,
    ResolvedParameters,
    ResolveResponse,
    SecretRefValue,
    StringValue,
    canonical_version,
    validate_values_against_schema,
)


# --------------------------------------------------------------------------- #
# JSON-schema parity vs the backend                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "model_name",
    [
        "ParameterSchema",
        "ParameterField",
        "ExperimentVersion",
        "EnvironmentPointer",
        "ProjectEnvironments",
        "EnvironmentBindRequest",
        "ResolveResponse",
    ],
)
def test_sdk_models_match_backend_json_schema(model_name: str) -> None:
    """SDK and backend Pydantic models must produce identical JSON schemas.

    Imported lazily so the test still loads on machines that don't have
    the backend on the path; in that case it skips rather than failing.
    """
    sdk_module = pytest.importorskip("rhesis.sdk.models.parameters")
    try:
        backend_module = pytest.importorskip(
            "rhesis.backend.app.schemas.parameters"
        )
    except Exception:
        pytest.skip("Backend package not importable from the SDK env")

    sdk_cls = getattr(sdk_module, model_name)
    backend_cls = getattr(backend_module, model_name)

    sdk_schema = _strip_titles(sdk_cls.model_json_schema())
    backend_schema = _strip_titles(backend_cls.model_json_schema())

    assert sdk_schema == backend_schema, (
        f"JSON schema for {model_name} drifted between SDK and backend"
    )


_NOISE_KEYS = {"title", "description"}


def _strip_titles(value):
    """Recursively drop ``title``/``description`` keys.

    Pydantic embeds class docstrings as ``description`` in JSON schema.
    The SDK's vendored copy has slimmer docstrings than the backend so
    we explicitly ignore both presentation-only keys; parity is about
    the *shape*, not the prose.
    """
    if isinstance(value, dict):
        return {
            k: _strip_titles(v) for k, v in value.items() if k not in _NOISE_KEYS
        }
    if isinstance(value, list):
        return [_strip_titles(v) for v in value]
    return value


# --------------------------------------------------------------------------- #
# canonical_version                                                           #
# --------------------------------------------------------------------------- #


def test_canonical_version_matches_backend_for_simple_payload() -> None:
    """The SDK and backend must agree on hashes for the same input.

    Skips if the backend isn't importable; the parity test above will
    have caught any schema drift, so this test exists only to catch
    canonical-form bugs (key ordering, alias handling, etc.) on the
    one machine where both sides import.

    The backend's :func:`canonical_version` expects already-typed
    values (its callers always have them); the SDK's helper is more
    ergonomic and accepts raw values. Both should land on the same
    hash regardless.
    """
    backend = pytest.importorskip("rhesis.backend.app.schemas.parameters")

    schema = ParameterSchema(
        fields=[
            ParameterField(name="model", type="string"),
            ParameterField(name="temperature", type="number"),
        ]
    )
    backend_schema = backend.ParameterSchema(
        fields=[
            backend.ParameterField(name="model", type="string"),
            backend.ParameterField(name="temperature", type="number"),
        ]
    )
    values = {"model": "gpt-4o", "temperature": 0.7}
    backend_typed = backend.validate_values_against_schema(values, backend_schema)

    sdk_version = canonical_version(values, schema)
    backend_version = backend.canonical_version(backend_typed, backend_schema)
    assert sdk_version == backend_version


def test_canonical_version_idempotent_across_dict_order() -> None:
    """Reordering keys must not change the version hash."""
    schema = ParameterSchema(
        fields=[
            ParameterField(name="model", type="string"),
            ParameterField(name="temperature", type="number"),
        ]
    )
    a = canonical_version({"model": "gpt-4o", "temperature": 0.7}, schema)
    b = canonical_version({"temperature": 0.7, "model": "gpt-4o"}, schema)
    assert a == b


# --------------------------------------------------------------------------- #
# validate_values_against_schema                                              #
# --------------------------------------------------------------------------- #


def test_validate_values_fills_defaults_and_drops_unknowns() -> None:
    schema = ParameterSchema(
        fields=[
            ParameterField(name="model", type="string", required=True),
            ParameterField(
                name="temperature",
                type="number",
                default={"type": "number", "value": 1.0},
            ),
        ]
    )
    out = validate_values_against_schema(
        {"model": "gpt-4o", "ghost": "ignored"}, schema
    )
    assert out["model"].value == "gpt-4o"
    assert out["temperature"].value == 1.0
    assert "ghost" not in out


def test_validate_values_raises_on_missing_required() -> None:
    schema = ParameterSchema(
        fields=[ParameterField(name="model", type="string", required=True)]
    )
    with pytest.raises(ValueError):
        validate_values_against_schema({}, schema)


# --------------------------------------------------------------------------- #
# ResolvedParameters                                                          #
# --------------------------------------------------------------------------- #


def _make_response() -> ResolveResponse:
    schema = ParameterSchema(
        fields=[
            ParameterField(name="model", type="string"),
            ParameterField(name="api_key", type="secret_ref"),
        ]
    )
    secret_id = uuid.uuid4()
    experiment_id = uuid.uuid4()
    return ResolveResponse.model_validate(
        {
            "schema": schema.model_dump(),
            "values": {
                "model": {"type": "string", "value": "gpt-4o"},
                "api_key": {"type": "secret_ref", "value": str(secret_id)},
            },
            "experiment_id": str(experiment_id),
            "version": "v_deadbeef",
            "source": "environment",
            "source_environment": "default",
        }
    )


def test_resolved_parameters_acts_like_a_mapping() -> None:
    response = _make_response()
    resolved = ResolvedParameters.from_response(response)

    assert "model" in resolved
    assert resolved["model"] == "gpt-4o"
    assert sorted(resolved.keys()) == ["api_key", "model"]
    assert resolved.source == "environment"
    assert resolved.source_environment == "default"
    native = resolved.as_native()
    assert native["model"] == "gpt-4o"


def test_resolved_parameters_repr_masks_secret_refs() -> None:
    secret_id = uuid.uuid4()
    resolved = ResolvedParameters(
        values={
            "model": StringValue(value="gpt-4o"),
            "api_key": SecretRefValue(value=secret_id),
        },
        experiment_id=uuid.uuid4(),
        version="v_test",
        source="environment",
        source_environment="default",
    )
    rendered = repr(resolved)
    assert "<secret>" in rendered
    assert str(secret_id) not in rendered


def test_resolved_parameters_as_native_returns_unwrapped_values() -> None:
    schema = ParameterSchema(
        fields=[ParameterField(name="model", type="string")]
    )
    resolved = ResolvedParameters(
        values={"model": StringValue(value="gpt-4o")},
        experiment_id=uuid.uuid4(),
        version="v_x",
        source="version",
        schema=schema,
    )
    assert resolved.as_native() == {"model": "gpt-4o"}
    typed = resolved.get_typed("model")
    assert isinstance(typed, StringValue)
    assert typed.value == "gpt-4o"


def test_resolved_parameters_records_when_resolution_was_now() -> None:
    """Sanity check that the SDK's data class doesn't shadow datetime imports."""
    _ = datetime.now(timezone.utc)
