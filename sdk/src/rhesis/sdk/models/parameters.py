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
from typing import Annotated, Any, ClassVar, Iterator, Literal, Union
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
# Built-in environments                                                      #
# --------------------------------------------------------------------------- #


class BuiltInEnvironment:
    """Namespace for the environment names the platform always recognises.

    SDK-side vendor of
    :class:`rhesis.backend.app.schemas.parameters.BuiltInEnvironment`.
    The JSON-schema parity test keeps the value list in lockstep with
    the backend; this class just lets SDK callers refer to the members
    symbolically rather than typing string literals.

    Environment names themselves remain free-form strings — any value
    matching the backend's ``ENVIRONMENT_NAME_PATTERN`` is creatable.
    This class is *not* a type, just a centrally defined set of literals.

    :attr:`DEFAULT` is the resolver's implicit fallback — calling
    :meth:`Parameters.get` without ``environment``, ``experiment_id``,
    or ``version`` resolves against it.
    """

    DEFAULT: ClassVar[str] = "default"
    DEVELOPMENT: ClassVar[str] = "development"
    STAGING: ClassVar[str] = "staging"
    PRODUCTION: ClassVar[str] = "production"

    #: Ordered tuple of every built-in environment name. Iterate when
    #: you need the full set; compare against individual members
    #: otherwise.
    ALL: ClassVar[tuple[str, ...]] = (
        DEFAULT,
        DEVELOPMENT,
        STAGING,
        PRODUCTION,
    )


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

    @model_validator(mode="before")
    @classmethod
    def _coerce_bare_default(cls, data: Any) -> Any:
        """Accept bare Python values as ``default`` and wrap them.

        When the ``type`` field is known, a bare value like ``0.7`` is
        automatically wrapped into ``{"type": "number", "value": 0.7}``.
        This lets callers write::

            ParameterField(name="temp", type="number", default=0.7)

        instead of the verbose::

            ParameterField(name="temp", type="number",
                           default=NumberValue(value=0.7))
        """
        if not isinstance(data, dict):
            return data
        default = data.get("default")
        ptype = data.get("type")
        if default is None or ptype is None:
            return data
        if isinstance(default, _ParameterValueBase):
            return data
        if isinstance(default, dict) and "type" in default and "value" in default:
            return data
        data = dict(data)
        data["default"] = {"type": ptype, "value": default}
        return data


class ParameterSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fields: list[ParameterField] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_names_and_options(self) -> "ParameterSchema":
        seen: set[str] = set()
        for f in self.fields:
            if not _NAME_RE.match(f.name):
                raise ValueError(
                    f"Parameter name {f.name!r} is not snake_case (must match [a-z][a-z0-9_]*)"
                )
            if f.name in seen:
                raise ValueError(f"Duplicate parameter name: {f.name!r}")
            seen.add(f.name)

            if f.type == "enum":
                if not f.options:
                    raise ValueError(f"Enum parameter {f.name!r} must have options")
                if f.default is not None:
                    if f.default.type != "enum":
                        raise ValueError(
                            f"Default for {f.name!r} does not match parameter type"
                            f" 'enum' (got {f.default.type!r})"
                        )
                    if f.default.value not in f.options:
                        raise ValueError(
                            f"Default value {f.default.value!r} not in options for enum {f.name!r}"
                        )
            else:
                if f.options is not None:
                    raise ValueError(f"Parameter {f.name!r} of type {f.type!r} cannot have options")
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


class EnvironmentPointer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    experiment_id: UUID4
    version: str


class ProjectEnvironments(BaseModel):
    """Mirror of the backend ``ProjectEnvironments`` schema.

    Values are nullable: ``None`` means the user has registered a custom
    environment name without binding an experiment onto it yet. Callers
    that only care about resolvable environments should filter ``None``
    out before use.
    """

    model_config = ConfigDict(extra="ignore")

    environments: dict[str, EnvironmentPointer | None] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _default_and_legacy(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "environments" not in data and "labels" in data:
                data = {**data, "environments": data["labels"]}
            data.setdefault("environments", {})
        return data


ResolveSource = Literal["environment", "experiment_id", "version"]


class ResolveResponse(BaseModel):
    """Wire shape of ``GET /projects/{id}/parameters/resolve``.

    The ``schema`` JSON key is mapped to the Python attribute
    ``schema_`` to avoid Pydantic's ``BaseModel.schema`` shadow warning
    while keeping the on-the-wire shape exactly what the backend emits.

    Legacy payloads may still use ``source == \"label\"`` and
    ``source_label``; a ``mode=\"before\"`` validator normalizes those to
    ``environment`` / ``source_environment``.
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
    source_environment: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _legacy_resolve_wire(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if data.get("source") == "label":
            data = {**data, "source": "environment"}
        if "source_environment" not in data and "source_label" in data:
            data = {**data, "source_environment": data.get("source_label")}
        return data


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
        raise ValueError(f"Type mismatch for {name!r}: expected {field.type!r}, got {typed.type!r}")

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
    serialized = {name: _dump_for_hash(value) for name, value in values.items()}
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

    Values are unwrapped to native Python types so you can use simple
    attribute or dict access::

        params = Parameters.get("My App")
        params.model          # "gpt-4o"
        params.temperature    # 0.7
        params["max_tokens"]  # 1024

    Typed accessors (``get_string``, ``get_number``, …) are still
    available when you want explicit runtime type checking.

    Provenance fields (``experiment_id``, ``version``, ``source``,
    ``source_environment``) carry the same shape the backend's
    :class:`ResolveResponse` exposes.
    """

    __slots__ = (
        "_typed",
        "experiment_id",
        "version",
        "source",
        "source_environment",
        "schema",
    )

    def __init__(
        self,
        *,
        values: dict[str, ParameterValue],
        experiment_id: UUID,
        version: str,
        source: ResolveSource,
        source_environment: str | None = None,
        schema: ParameterSchema | None = None,
    ) -> None:
        self._typed: dict[str, ParameterValue] = dict(values)
        self.experiment_id: UUID = experiment_id
        self.version: str = version
        self.source: ResolveSource = source
        self.source_environment: str | None = source_environment
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

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"No parameter named {name!r}") from None

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

    # --- Convenience typed getters --------------------------------------- #

    def _get_of_type(self, key: str, expected: str, default: Any = None) -> Any:
        pv = self._typed.get(key)
        if pv is None:
            return default
        if pv.type != expected:
            raise TypeError(f"Parameter {key!r} is {pv.type!r}, not {expected!r}")
        return pv.value

    def get_text(self, key: str, default: str | None = None) -> str | None:
        return self._get_of_type(key, "text", default)

    def get_string(self, key: str, default: str | None = None) -> str | None:
        return self._get_of_type(key, "string", default)

    def get_integer(self, key: str, default: int | None = None) -> int | None:
        return self._get_of_type(key, "integer", default)

    def get_number(self, key: str, default: float | None = None) -> float | None:
        return self._get_of_type(key, "number", default)

    def get_boolean(self, key: str, default: bool | None = None) -> bool | None:
        return self._get_of_type(key, "boolean", default)

    def get_enum(self, key: str, default: str | None = None) -> str | None:
        return self._get_of_type(key, "enum", default)

    def get_str(self, key: str, default: str | None = None) -> str | None:
        """Return a string value regardless of whether the type is ``text`` or ``string``.

        Raises :class:`TypeError` if the parameter exists but is neither
        ``text`` nor ``string``.
        """
        pv = self._typed.get(key)
        if pv is None:
            return default
        if pv.type not in ("text", "string"):
            raise TypeError(f"Parameter {key!r} is {pv.type!r}, not 'text' or 'string'")
        return pv.value

    def get_model_ref(self, key: str, default: UUID | None = None) -> UUID | None:
        return self._get_of_type(key, "model_ref", default)

    def get_secret_ref(self, key: str, default: UUID | None = None) -> UUID | None:
        return self._get_of_type(key, "secret_ref", default)

    # --- Constructors ---------------------------------------------------- #

    @classmethod
    def from_response(cls, response: ResolveResponse) -> "ResolvedParameters":
        """Build from a parsed :class:`ResolveResponse`."""
        return cls(
            values=response.values,
            experiment_id=response.experiment_id,
            version=response.version,
            source=response.source,
            source_environment=response.source_environment,
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
    "BuiltInEnvironment",
    "EnumValue",
    "EnvironmentPointer",
    "ExperimentVersion",
    "IntegerValue",
    "ModelRefValue",
    "NumberValue",
    "ParameterField",
    "ParameterSchema",
    "ParameterType",
    "ParameterValue",
    "ProjectEnvironments",
    "ResolveResponse",
    "ResolveSource",
    "ResolvedParameters",
    "SecretRefValue",
    "StringValue",
    "TextValue",
    "canonical_hash",
    "canonical_schema_fingerprint",
    "canonical_version",
    "validate_values_against_schema",
]
