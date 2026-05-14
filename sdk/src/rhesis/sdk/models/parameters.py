"""SDK-side mirror of the backend's parameter-management Pydantic models.

These models are *vendored* from
``apps/backend/src/rhesis/backend/app/schemas/parameters.py`` so the SDK
runs without a backend dependency. A JSON-schema parity test
(``tests/sdk/test_parameters_models.py``) compares the schemas of both
copies and fails loudly if they drift, making this file the SDK's
faithful copy of the wire format.

In addition to the wire shapes, this module exposes a runtime-only
:class:`ResolvedParameters` (a ``Mapping`` with typed accessors and
provenance) and a ``canonical_version`` helper that mirrors the
backend's deterministic content hash so consumers can predict a
version's identity before sending it.

The discriminated-union ``ParameterValue`` removes ``if/else`` branching
on field type: validation, serialization, and IDE hints all flow from
the ``type`` discriminator. Hashing is canonical and process-stable:
dicts are emitted with sorted keys, no whitespace, no trailing nulls.
Equality of input bytes implies equality of hash, regardless of
dict-construction order, Python version, or platform.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, Iterator, Literal, Union
from uuid import UUID

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)

# --------------------------------------------------------------------------- #
# Well-known labels                                                           #
# --------------------------------------------------------------------------- #

WELL_KNOWN_LABELS: tuple[str, ...] = ("default", "production", "staging")


# --------------------------------------------------------------------------- #
# Type discriminators                                                         #
# --------------------------------------------------------------------------- #

ParameterType = Literal[
    "text",
    "string",
    "integer",
    "number",
    "boolean",
    "enum",
    "model_ref",
    "secret_ref",
]


class _ParameterValueBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextValue(_ParameterValueBase):
    type: Literal["text"] = "text"
    value: str


class StringValue(_ParameterValueBase):
    type: Literal["string"] = "string"
    value: str


class IntegerValue(_ParameterValueBase):
    type: Literal["integer"] = "integer"
    value: int


class NumberValue(_ParameterValueBase):
    type: Literal["number"] = "number"
    value: float


class BooleanValue(_ParameterValueBase):
    type: Literal["boolean"] = "boolean"
    value: bool


class EnumValue(_ParameterValueBase):
    type: Literal["enum"] = "enum"
    value: str


class ModelRefValue(_ParameterValueBase):
    type: Literal["model_ref"] = "model_ref"
    value: UUID4


class SecretRefValue(_ParameterValueBase):
    type: Literal["secret_ref"] = "secret_ref"
    value: UUID4


ParameterValue = Annotated[
    Union[
        TextValue,
        StringValue,
        IntegerValue,
        NumberValue,
        BooleanValue,
        EnumValue,
        ModelRefValue,
        SecretRefValue,
    ],
    Field(discriminator="type"),
]


_PARAMETER_VALUE_ADAPTER: TypeAdapter[ParameterValue] = TypeAdapter(ParameterValue)

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# --------------------------------------------------------------------------- #
# Schema model                                                                #
# --------------------------------------------------------------------------- #


class ParameterField(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    type: ParameterType
    description: str | None = None
    required: bool = False
    default: ParameterValue | None = None
    options: list[str] | None = None
    display_order: int = 0


class ParameterSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fields: list[ParameterField] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_names_and_options(self) -> "ParameterSchema":
        seen: set[str] = set()
        for f in self.fields:
            if not _NAME_RE.match(f.name):
                raise ValueError(
                    f"Parameter name {f.name!r} is not snake_case"
                    " (must match [a-z][a-z0-9_]*)"
                )
            if f.name in seen:
                raise ValueError(f"Duplicate parameter name: {f.name!r}")
            seen.add(f.name)

            if f.type == "enum":
                if not f.options:
                    raise ValueError(
                        f"Enum parameter {f.name!r} must have options"
                    )
                if f.default is not None:
                    if f.default.type != "enum":
                        raise ValueError(
                            f"Default for {f.name!r} does not match parameter type"
                            f" 'enum' (got {f.default.type!r})"
                        )
                    if f.default.value not in f.options:
                        raise ValueError(
                            f"Default value {f.default.value!r} not in options"
                            f" for enum {f.name!r}"
                        )
            else:
                if f.options is not None:
                    raise ValueError(
                        f"Parameter {f.name!r} of type {f.type!r} cannot have options"
                    )
                if f.default is not None and f.default.type != f.type:
                    raise ValueError(
                        f"Default for {f.name!r} does not match parameter type"
                        f" {f.type!r} (got {f.default.type!r})"
                    )
        return self


# --------------------------------------------------------------------------- #
# Experiment / version models                                                 #
# --------------------------------------------------------------------------- #


class ExperimentVersion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str
    schema_fingerprint: str
    values: dict[str, ParameterValue] = Field(default_factory=dict)
    parent_version: str | None = None
    message: str | None = None
    created_at: datetime
    created_by_user_id: UUID4

    @model_validator(mode="before")
    @classmethod
    def _backfill_optionals(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data.setdefault("parent_version", None)
            data.setdefault("message", None)
            data.setdefault("values", {})
        return data


class LabelPointer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    experiment_id: UUID4
    version: str


class ProjectLabels(BaseModel):
    model_config = ConfigDict(extra="ignore")

    labels: dict[str, LabelPointer] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _default_labels(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data.setdefault("labels", {})
        return data


ResolveSource = Literal["label", "experiment_id", "version"]


class ResolveResponse(BaseModel):
    """Wire shape of ``GET /projects/{id}/parameters/resolve``.

    The ``schema`` JSON key is mapped to the Python attribute
    ``schema_`` to avoid Pydantic's ``BaseModel.schema`` shadow warning
    while keeping the on-the-wire shape exactly what the backend emits.
    """

    model_config = ConfigDict(
        extra="ignore",
        protected_namespaces=(),
        populate_by_name=True,
    )

    schema_: ParameterSchema = Field(alias="schema")
    values: dict[str, ParameterValue]
    experiment_id: UUID4
    version: str
    source: ResolveSource
    source_label: str | None = None


# --------------------------------------------------------------------------- #
# Validation helper (mirror of the backend implementation)                    #
# --------------------------------------------------------------------------- #


def validate_values_against_schema(
    values: dict[str, Any],
    schema: ParameterSchema,
) -> dict[str, ParameterValue]:
    """Validate raw ``values`` against ``schema`` and return typed values.

    Mirrors the backend implementation byte-for-byte so client-side
    validation matches whatever the server would do, letting SDK
    callers fail at author time instead of at PUT time.
    """
    fields_by_name = {f.name: f for f in schema.fields}
    out: dict[str, ParameterValue] = {}

    for name, raw in values.items():
        field = fields_by_name.get(name)
        if field is None:
            continue
        out[name] = _coerce_value(name, raw, field)

    for field in schema.fields:
        if field.name in out:
            continue
        if field.default is not None:
            out[field.name] = field.default
            continue
        if field.required:
            raise ValueError(f"Missing required parameter: {field.name!r}")

    return out


def _coerce_value(
    name: str,
    raw: Any,
    field: ParameterField,
) -> ParameterValue:
    if isinstance(raw, _ParameterValueBase):
        typed: ParameterValue = raw  # type: ignore[assignment]
    elif isinstance(raw, dict) and "type" in raw and "value" in raw:
        try:
            typed = _PARAMETER_VALUE_ADAPTER.validate_python(raw)
        except ValidationError as exc:
            raise ValueError(f"Invalid value for {name!r}: {exc}") from exc
    else:
        wrapped = {"type": field.type, "value": raw}
        try:
            typed = _PARAMETER_VALUE_ADAPTER.validate_python(wrapped)
        except ValidationError as exc:
            raise ValueError(
                f"Value for {name!r} does not match parameter type {field.type!r}"
            ) from exc

    if typed.type != field.type:
        raise ValueError(
            f"Type mismatch for {name!r}: expected {field.type!r},"
            f" got {typed.type!r}"
        )

    if field.type == "enum" and field.options is not None:
        if typed.value not in field.options:
            raise ValueError(
                f"Value {typed.value!r} for {name!r} is not in options for enum"
                f" (allowed: {field.options})"
            )

    return typed


# --------------------------------------------------------------------------- #
# Canonical hashing (mirror of the backend implementation)                    #
# --------------------------------------------------------------------------- #


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(v) for v in value]
    return value


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        _canonicalize(payload),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _dump_for_hash(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def canonical_schema_fingerprint(schema: ParameterSchema) -> str:
    canon = _canonical_json(_dump_for_hash(schema))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def canonical_hash(
    schema_fingerprint: str,
    values: dict[str, ParameterValue],
) -> str:
    serialized = {
        name: _dump_for_hash(value)
        for name, value in values.items()
    }
    payload = {
        "schema_fingerprint": schema_fingerprint,
        "values": serialized,
    }
    canon = _canonical_json(payload)
    return "v_" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def canonical_version(
    values: dict[str, ParameterValue] | dict[str, Any],
    schema: ParameterSchema,
) -> str:
    """Return the canonical version identifier for ``(values, schema)``.

    Accepts both raw and typed values for ergonomic SDK use. Raw values
    are coerced through :func:`validate_values_against_schema` first so
    the hash is computed off the *typed* form (matching what the server
    will store).
    """
    typed = validate_values_against_schema(values, schema)
    return canonical_hash(canonical_schema_fingerprint(schema), typed)


# --------------------------------------------------------------------------- #
# Runtime ResolvedParameters                                                  #
# --------------------------------------------------------------------------- #


class ResolvedParameters(Mapping[str, Any]):
    """Read-only mapping of resolved parameter values with provenance.

    Behaves like a regular ``Mapping`` so callers can do
    ``params["temperature"]`` or ``params.get("system_prompt", "...")``.
    The values returned by ``__getitem__`` are *unwrapped* native
    Python objects (a string for ``text``/``string``/``enum``, an
    ``int`` / ``float`` / ``bool``, a ``UUID`` for ref types) — the
    typed :class:`ParameterValue` objects are still available via
    :meth:`get_typed`.

    Provenance fields (``experiment_id``, ``version``, ``source``,
    ``source_label``) carry the same shape the backend's
    :class:`ResolveResponse` exposes, so resolved parameters survive
    round-trips intact whether they came from the SDK fetch path or
    the connector wire.
    """

    __slots__ = (
        "_typed",
        "experiment_id",
        "version",
        "source",
        "source_label",
        "schema",
    )

    def __init__(
        self,
        *,
        values: dict[str, ParameterValue],
        experiment_id: UUID,
        version: str,
        source: ResolveSource,
        source_label: str | None = None,
        schema: ParameterSchema | None = None,
    ) -> None:
        self._typed: dict[str, ParameterValue] = dict(values)
        self.experiment_id: UUID = experiment_id
        self.version: str = version
        self.source: ResolveSource = source
        self.source_label: str | None = source_label
        self.schema: ParameterSchema | None = schema

    # --- Mapping protocol ------------------------------------------------ #

    def __getitem__(self, key: str) -> Any:
        typed = self._typed[key]
        return typed.value

    def __iter__(self) -> Iterator[str]:
        return iter(self._typed)

    def __len__(self) -> int:
        return len(self._typed)

    def __contains__(self, key: object) -> bool:
        return key in self._typed

    def __repr__(self) -> str:
        # Mask secret refs in repr so logs don't leak credentials by sight.
        safe = {
            name: ("<secret>" if v.type == "secret_ref" else v.value)
            for name, v in self._typed.items()
        }
        return (
            f"ResolvedParameters(experiment_id={self.experiment_id!s},"
            f" version={self.version!r}, source={self.source!r},"
            f" values={safe!r})"
        )

    # --- Typed accessors ------------------------------------------------- #

    def get_typed(self, key: str) -> ParameterValue:
        """Return the typed :class:`ParameterValue` for ``key``."""
        return self._typed[key]

    def as_typed(self) -> dict[str, ParameterValue]:
        """Return a shallow copy of the underlying typed value map."""
        return dict(self._typed)

    def as_native(self) -> dict[str, Any]:
        """Return a shallow copy of the unwrapped native value map.

        Useful for constructing kwargs to inject into user functions
        (the connector's ``parameters=True`` mode does exactly this).
        """
        return {name: v.value for name, v in self._typed.items()}

    # --- Constructors ---------------------------------------------------- #

    @classmethod
    def from_response(cls, response: ResolveResponse) -> "ResolvedParameters":
        """Build from a parsed :class:`ResolveResponse`."""
        return cls(
            values=response.values,
            experiment_id=response.experiment_id,
            version=response.version,
            source=response.source,
            source_label=response.source_label,
            schema=response.schema_,
        )

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> "ResolvedParameters":
        """Build from a raw JSON dict (e.g. an ExecuteTestMessage field).

        Tolerates both the ``ResolveResponse`` shape and the leaner
        connector-wire shape, where ``schema`` may be absent.
        """
        return cls.from_response(ResolveResponse.model_validate(payload))


__all__ = [
    "BooleanValue",
    "EnumValue",
    "ExperimentVersion",
    "IntegerValue",
    "LabelPointer",
    "ModelRefValue",
    "NumberValue",
    "ParameterField",
    "ParameterSchema",
    "ParameterType",
    "ParameterValue",
    "ProjectLabels",
    "ResolveResponse",
    "ResolveSource",
    "ResolvedParameters",
    "SecretRefValue",
    "StringValue",
    "TextValue",
    "WELL_KNOWN_LABELS",
    "canonical_hash",
    "canonical_schema_fingerprint",
    "canonical_version",
    "validate_values_against_schema",
]
