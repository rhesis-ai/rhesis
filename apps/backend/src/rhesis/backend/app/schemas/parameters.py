"""Pydantic 2 models and helpers for project parameter management.

These models are the single source of truth for parameter shapes across
the database (JSONB columns wrapped by :class:`PydanticColumn`), the REST
API (request/response bodies), the resolver, and the SDK (vendored copy
kept in sync via a JSON-schema parity test).

The discriminated-union ``ParameterValue`` removes ``if/else`` branching
on field type: validation, serialization, and IDE hints all flow from
the ``type`` discriminator. ``validate_values_against_schema`` is the
one canonical validator used by the REST handler, the resolver, and any
future bulk-import path.

Hashing is canonical and process-stable: dicts are emitted with sorted
keys, no whitespace, no trailing nulls. Equality of input bytes implies
equality of hash, regardless of dict-construction order, Python version,
or platform.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Annotated, Any, Literal, Union
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
# Well-known environments                                                    #
# --------------------------------------------------------------------------- #

#: Environments rendered in the project UI even when unbound. Custom
#: environment names are still freely user-creatable; this tuple is the
#: closed set of names the frontend overlays for first-class display.
WELL_KNOWN_ENVIRONMENTS: tuple[str, ...] = ("default", "production", "staging")


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
    """Base for every value variant. Forbids extras so future fields fail loudly."""

    model_config = ConfigDict(extra="forbid")


class TextValue(_ParameterValueBase):
    """Free-form multiline string (e.g. a system prompt)."""

    type: Literal["text"] = "text"
    value: str


class StringValue(_ParameterValueBase):
    """Single-line string identifier (e.g. a model name)."""

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
    """One of a closed set of strings; the field declares the allowed options."""

    type: Literal["enum"] = "enum"
    value: str


class ModelRefValue(_ParameterValueBase):
    """Reference to a Model row by id; consumers hydrate via Model.pull()."""

    type: Literal["model_ref"] = "model_ref"
    value: UUID4


class SecretRefValue(_ParameterValueBase):
    """Reference to a secret record by id; consumers hydrate via the secrets API."""

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


# Cached adapter so repeated validation doesn't re-build the discriminator graph.
_PARAMETER_VALUE_ADAPTER: TypeAdapter[ParameterValue] = TypeAdapter(ParameterValue)


# Snake-case identifier: starts with a letter, then letters/digits/underscores.
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# --------------------------------------------------------------------------- #
# Schema model                                                                #
# --------------------------------------------------------------------------- #


class ParameterField(BaseModel):
    """One named slot in a project's parameter schema."""

    model_config = ConfigDict(extra="ignore")

    name: str
    type: ParameterType
    description: str | None = None
    required: bool = False
    default: ParameterValue | None = None
    options: list[str] | None = None
    display_order: int = 0


class ParameterSchema(BaseModel):
    """A project's typed parameter contract.

    Declares what knobs the project supports; experiments fill in the
    values. Renaming or removing a field is a schema-level change and is
    not auto-migrated for existing experiments.
    """

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
    """An immutable snapshot of an experiment's values at a moment in time.

    The ``version`` is a content hash; saving identical values is
    idempotent (the server returns the existing version rather than
    appending a duplicate). ``schema_fingerprint`` records the exact
    schema shape at commit time so the version can still be interpreted
    after the project schema has evolved.
    """

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
        """Lift older rows that pre-date optional fields onto the current shape.

        Adding a new optional field to ExperimentVersion must remain a
        code-only change: existing JSONB rows are not rewritten, they
        adapt on read. This validator centralizes the defaulting so each
        new field added below picks up sensible defaults without callers
        seeing ``KeyError`` from the underlying dict.
        """
        if isinstance(data, dict):
            data.setdefault("parent_version", None)
            data.setdefault("message", None)
            data.setdefault("values", {})
        return data


class EnvironmentPointer(BaseModel):
    """Resolves an environment name to a single ``(experiment, version)`` pair."""

    model_config = ConfigDict(extra="ignore")

    experiment_id: UUID4
    version: str


class ProjectEnvironments(BaseModel):
    """Project-scoped, mutable map of environment name -> :class:`EnvironmentPointer`.

    Only *bound* environments appear in this map. Well-known environments that have
    not yet been promoted are not stored; the frontend overlays them
    client-side from a shared constants file.

    Legacy rows may still use the ``{"labels": {...}}`` JSON shape; the
    ``mode="before"`` validator lifts that onto ``environments`` on read.
    """

    model_config = ConfigDict(extra="ignore")

    environments: dict[str, EnvironmentPointer] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _default_and_legacy(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "environments" not in data and "labels" in data:
                data = {**data, "environments": data["labels"]}
            data.setdefault("environments", {})
        return data


class ResolveResponse(BaseModel):
    """Result of ``GET /projects/{id}/parameters/resolve``.

    Carries the resolved values plus the provenance the SDK and the run
    snapshot need to faithfully record where the values came from. The
    ``source_environment`` is populated only when ``source == 'environment'``; for
    direct ``experiment_id`` / ``version`` lookups it stays ``None`` so
    consumers can tell the two cases apart without ambiguity.

    The ``schema`` JSON key is mapped to the Python attribute ``schema_``
    to dodge Pydantic's ``BaseModel.schema`` shadow warning while keeping
    the on-the-wire shape exactly what the plan and the SDK expect.

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
    source: Literal["environment", "experiment_id", "version"]
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
# Validation helper                                                           #
# --------------------------------------------------------------------------- #


def unwrap_parameter_values_for_wire(values: dict[str, ParameterValue]) -> dict[str, Any]:
    """Strip discriminator wrappers for connector payloads and JSONB storage.

    Maps each slot to its primitive Python value (``str``, ``int``, ``float``,
    ``bool``). ``model_ref`` / ``secret_ref`` become UUID strings so the wire
    shape is JSON-safe and stable across processes.
    """
    out: dict[str, Any] = {}
    for name, pv in values.items():
        inner = pv.value
        if isinstance(inner, UUID):
            out[name] = str(inner)
        else:
            out[name] = inner
    return out


def validate_values_against_schema(
    values: dict[str, Any],
    schema: ParameterSchema,
) -> dict[str, ParameterValue]:
    """Validate raw ``values`` against ``schema`` and return typed values.

    Accepts both bare values (``{"temperature": 0.7}``) and discriminator
    dicts (``{"temperature": {"type": "number", "value": 0.7}}``). Bare
    values are wrapped using the field's declared type. Unknown fields
    are silently dropped — consumers ignoring extras keeps schema removal
    a non-breaking edit (existing experiments still load, the orphaned
    value just becomes invisible).

    Required fields without a default raise ``ValueError``; required
    fields with a default fall through to the default. Defaults are
    materialized into the result so downstream consumers see a complete
    typed dict regardless of the input.

    Raises:
        ValueError: on missing required fields, type mismatches, or enum
            values outside the declared options.
    """
    fields_by_name = {f.name: f for f in schema.fields}
    out: dict[str, ParameterValue] = {}

    for name, raw in values.items():
        field = fields_by_name.get(name)
        if field is None:
            # Drop unknown keys: see docstring rationale.
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
    """Coerce ``raw`` into the correctly-typed :data:`ParameterValue`."""
    if isinstance(raw, _ParameterValueBase):
        typed: ParameterValue = raw  # type: ignore[assignment]
    elif isinstance(raw, dict) and "type" in raw and "value" in raw:
        try:
            typed = _PARAMETER_VALUE_ADAPTER.validate_python(raw)
        except ValidationError as exc:  # pragma: no cover - exercised via tests
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
# Canonical hashing                                                           #
# --------------------------------------------------------------------------- #


def _canonicalize(value: Any) -> Any:
    """Recursively sort dict keys so JSON serialization is order-independent."""
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(v) for v in value]
    return value


def _canonical_json(payload: Any) -> str:
    """Stable JSON serialization for hashing.

    The plan-locked rule: ``model_dump(mode="json", by_alias=True,
    exclude_none=True)`` then sort all dict keys then use the most
    compact separators. Two identical inputs produce byte-identical
    outputs across processes, Python versions, and platforms.
    """
    return json.dumps(
        _canonicalize(payload),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _dump_for_hash(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def canonical_schema_fingerprint(schema: ParameterSchema) -> str:
    """Hex SHA-256 of the canonical JSON of ``schema``.

    Identifies the exact shape used at commit time so an
    :class:`ExperimentVersion` written against an older schema can be
    distinguished from one written against a newer one even when both
    happen to share value names.
    """
    canon = _canonical_json(_dump_for_hash(schema))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def canonical_hash(
    schema_fingerprint: str,
    values: dict[str, ParameterValue],
) -> str:
    """Return the canonical version identifier for ``(values, schema)``.

    The result is ``"v_" + sha256_hex`` so it's directly usable as the
    public-facing ``version`` string (the UI shortens it to ``v_<6 chars>``
    for chips). Computed off the schema fingerprint plus the typed value
    dump so two value sets that hash identically were produced under the
    same schema interpretation.
    """
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
    values: dict[str, ParameterValue],
    schema: ParameterSchema,
) -> str:
    """Convenience wrapper: fingerprint the schema then hash the values.

    Mirrors the SDK's ``canonical_version`` so the algorithm has one
    callable name when read end-to-end. The two-step form
    (:func:`canonical_schema_fingerprint` + :func:`canonical_hash`) stays
    available for callers that already have the fingerprint cached.
    """
    return canonical_hash(canonical_schema_fingerprint(schema), values)


# --------------------------------------------------------------------------- #
# Experiment API request / response shapes                                    #
# --------------------------------------------------------------------------- #


class ExperimentBase(BaseModel):
    """Common fields shared by Experiment Create / Update / Read shapes."""

    model_config = ConfigDict(extra="ignore", from_attributes=True)

    name: str
    description: str | None = None
    visibility: Literal["private", "shared"] = "private"


class ExperimentCreate(ExperimentBase):
    """Request body for ``POST /projects/{project_id}/experiments``.

    The new experiment's ``project_id`` comes from the path; the
    ``owner_user_id`` is set server-side from the authenticated user.
    Initial visibility defaults to ``private`` per the plan-locked
    decision so accidental exposure is impossible.
    """


class ExperimentUpdate(BaseModel):
    """Request body for ``PATCH /experiments/{id}``.

    All fields optional — only the keys present in the body are
    applied. ``visibility`` flips honor the "environments point only at
    shared experiments" invariant: unsharing while an environment points at
    this experiment is rejected with 409.
    """

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    description: str | None = None
    visibility: Literal["private", "shared"] | None = None


class ExperimentRead(ExperimentBase):
    """Response body for experiment endpoints (single + list).

    Carries enough surface for the list page (identity, ownership,
    visibility, version stats) without forcing a second round-trip per
    row. The full ``versions`` list is exposed on the detail endpoint
    only — list responses include only the latest version pointer to
    keep payloads bounded for large experiment counts.
    """

    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID4
    project_id: UUID4
    owner_user_id: UUID4
    organization_id: UUID4 | None = None
    versions_count: int = 0
    latest_version: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExperimentDetail(ExperimentRead):
    """Detail response that also includes the inline ``versions`` array."""

    versions: list[ExperimentVersion] = Field(default_factory=list)


class ExperimentVersionCreate(BaseModel):
    """Request body for ``POST /experiments/{id}/versions``.

    The values are validated against the project's current schema; the
    server computes the content hash, sets ``schema_fingerprint`` to
    the hash of that schema at commit time, and returns the resulting
    immutable :class:`ExperimentVersion`. If the latest version's hash
    matches the new one the response is the existing entry and no new
    row is appended (idempotent commit).
    """

    model_config = ConfigDict(extra="ignore")

    values: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
    parent_version: str | None = None


class EnvironmentBindRequest(BaseModel):
    """Request body for ``PUT /projects/{id}/parameters/environments/{name}``.

    Carries the ``(experiment_id, version)`` pair the environment should
    point at. The server validates that the experiment is shared and
    that the version exists before persisting.
    """

    model_config = ConfigDict(extra="ignore")

    experiment_id: UUID4
    version: str


class ExperimentSummary(BaseModel):
    """Compact experiment shape returned inline on a TestRun.

    Lets the run detail page render an Experiment card in one
    backend round-trip instead of two. Same shape used in the list
    response so the TestRuns table can render the column without
    fan-out.
    """

    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID4
    name: str
    version: str
    source_environment: str | None = None
    visibility: Literal["private", "shared"]


__all__ = [
    "BooleanValue",
    "EnumValue",
    "EnvironmentBindRequest",
    "EnvironmentPointer",
    "ExperimentBase",
    "ExperimentCreate",
    "ExperimentDetail",
    "ExperimentRead",
    "ExperimentSummary",
    "ExperimentUpdate",
    "ExperimentVersion",
    "ExperimentVersionCreate",
    "IntegerValue",
    "ModelRefValue",
    "NumberValue",
    "ParameterField",
    "ParameterSchema",
    "ParameterType",
    "ParameterValue",
    "ProjectEnvironments",
    "ResolveResponse",
    "SecretRefValue",
    "StringValue",
    "TextValue",
    "WELL_KNOWN_ENVIRONMENTS",
    "canonical_hash",
    "canonical_schema_fingerprint",
    "canonical_version",
    "unwrap_parameter_values_for_wire",
    "validate_values_against_schema",
]
