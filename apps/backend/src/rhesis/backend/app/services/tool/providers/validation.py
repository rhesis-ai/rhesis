"""Manifest-driven validation, normalization and merging of tool fields.

Replaces the per-provider ``_validate_*`` functions that used to live in
``app/routers/tools.py`` and the per-provider ``merge_*`` functions in
``app/services/tool/credential_merge.py``. Each of those was the same three
steps with a different key: read a value, complain if it is blank, and on an
update fall back to what is already stored.

Error text is unchanged. Sentences are generated from the field's provider and
key, and a field overrides the wording only where the old hand-written string
differed from the generated form.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Mapping, MutableMapping, Optional

from rhesis.backend.app.services.tool.providers.spec import (
    FieldStore,
    ProviderField,
    ProviderFieldError,
    ProviderManifest,
)


def _missing_detail(manifest: ProviderManifest, field: ProviderField) -> str:
    if field.messages.missing:
        return field.messages.missing
    return f"{manifest.display_name} integrations require '{field.leaf}'"


def _invalid_detail(manifest: ProviderManifest, field: ProviderField) -> str:
    if field.messages.invalid:
        return field.messages.invalid
    return f"{manifest.display_name} '{field.leaf}' must be a non-empty string"


class FieldState(str, Enum):
    """Where a dotted lookup landed.

    ``ABSENT`` and ``MALFORMED`` are deliberately distinct. An optional field
    that simply is not there is fine; one whose parent is present but is not an
    object is a shape bug, and treating the two alike would let a typo in a
    nested payload pass silently.
    """

    #: The key, or one of its ancestors, is not present.
    ABSENT = "absent"
    #: An ancestor is present but is not an object, so the key cannot exist.
    MALFORMED = "malformed"
    #: The containing object exists; the value may still be ``None``.
    PRESENT = "present"


def _read(source: Mapping[str, Any] | None, field: ProviderField) -> tuple[FieldState, Any]:
    """Walk a dotted key. Returns ``(state, value)``.

    The distinction matters for error wording as well as correctness: GitLab
    says "require project metadata" when ``project`` is missing, and names
    ``namespace`` when the object is there but the leaf is not.
    """
    current: Any = source or {}
    for segment in field.path[:-1]:
        if not isinstance(current, Mapping):
            return FieldState.MALFORMED, None
        if segment not in current:
            return FieldState.ABSENT, None
        current = current[segment]
    if not isinstance(current, Mapping):
        return FieldState.MALFORMED, None
    return FieldState.PRESENT, current.get(field.path[-1])


def _write(target: MutableMapping[str, Any], field: ProviderField, value: Any) -> None:
    current: MutableMapping[str, Any] = target
    segments = field.path
    for segment in segments[:-1]:
        nested = current.get(segment)
        if not isinstance(nested, MutableMapping):
            nested = {}
            current[segment] = nested
        current = nested
    current[segments[-1]] = value


def read_field(
    source: Mapping[str, Any] | None,
    field: ProviderField,
) -> tuple[bool, Any]:
    """Public wrapper over the dotted-key walk, collapsed to ``(found, value)``.

    Callers that only need "is there a usable value here" do not want the
    three-state distinction; :func:`validate_field` is where it matters.
    """
    state, value = _read(source, field)
    return state is FieldState.PRESENT, value


def validate_field(
    manifest: ProviderManifest,
    field: ProviderField,
    source: Mapping[str, Any] | None,
) -> None:
    """Check one field against a credentials or metadata mapping."""
    state, value = _read(source, field)

    if state is FieldState.MALFORMED:
        # The parent is there but is not an object, so this is a shape bug
        # whether or not the field is optional.
        detail = field.messages.container_missing or _missing_detail(manifest, field)
        raise ProviderFieldError(detail)

    if state is FieldState.ABSENT:
        if not field.required:
            return
        detail = field.messages.container_missing or _missing_detail(manifest, field)
        raise ProviderFieldError(detail)

    if value is None:
        if not field.required:
            return
        raise ProviderFieldError(_missing_detail(manifest, field))

    if not isinstance(value, str):
        # Always an error. "Blank means not provided" below is about empty
        # strings from a form, and must not extend to a list or a number.
        raise ProviderFieldError(_invalid_detail(manifest, field))

    if not value.strip():
        # A generic form posts "" for every field the user left empty, so for an
        # optional field blank means "not provided", not "invalid".
        if not field.required:
            return
        raise ProviderFieldError(_invalid_detail(manifest, field))

    if field.validate is not None:
        try:
            field.validate(value)
        except ValueError as exc:
            raise ProviderFieldError(str(exc)) from exc


def validate_store(
    manifest: ProviderManifest,
    store: FieldStore,
    source: Mapping[str, Any] | None,
) -> None:
    """Check every field a provider keeps in one store."""
    for field in manifest.fields_in(store):
        validate_field(manifest, field, source)


def normalize(
    manifest: ProviderManifest,
    store: FieldStore,
    source: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Apply each field's ``normalize`` hook, leaving everything else intact.

    Replaces ``prepare_azure_devops_credentials``: the org-name extraction is
    now that field's ``normalize``, and the surrounding copy-and-strip is here.
    """
    prepared: dict[str, Any] = dict(source or {})
    for field in manifest.fields_in(store):
        state, value = _read(prepared, field)
        if state is not FieldState.PRESENT or not isinstance(value, str):
            continue
        try:
            normalized = field.normalize(value) if field.normalize else value.strip()
        except ValueError as exc:
            # A normalize hook rejects input it cannot make sense of (an Azure
            # DevOps "org" that is really a URL). That is a field error, not a
            # crash: without this the ValueError escapes to a 500 on create.
            raise ProviderFieldError(str(exc)) from exc
        _write(prepared, field, normalized)
    return prepared


def _decode(existing_json: str | None) -> dict[str, Any]:
    try:
        decoded = json.loads(existing_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def merge_credentials(
    manifest: ProviderManifest,
    existing_credentials_json: str | None,
    incoming: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Fill blank ``preserve_on_update`` fields from the stored credentials.

    This is what stops a PATCH that carries only a new token from wiping the
    instance URL, the org name, or the other half of a two-part credential.
    Only fields the manifest marks ``preserve_on_update`` are carried over, so
    an omitted secret is still an omitted secret.

    A blank incoming value means "not supplied" and restores the stored one, so
    there is currently no way to clear a preserved field back to its default --
    blanking ``GITLAB_API_URL`` will not move a tool from a self-managed
    instance to gitlab.com. That predates the manifests: the merge functions
    this replaced behaved the same way. Expressing "clear" needs a sentinel the
    schema cannot carry today, because ``ToolUpdate.credentials`` is typed
    ``Dict[str, str]`` and rejects a null value.
    """
    merged: dict[str, Any] = dict(incoming or {})
    existing = _decode(existing_credentials_json)
    if not existing:
        return merged

    for field in manifest.fields_in(FieldStore.CREDENTIALS):
        if not field.preserve_on_update:
            continue
        _, incoming_value = _read(merged, field)
        if isinstance(incoming_value, str) and incoming_value.strip():
            continue
        _, stored = _read(existing, field)
        if isinstance(stored, str) and stored.strip():
            _write(merged, field, stored.strip())

    return merged


def prepare_credentials(
    manifest: ProviderManifest,
    incoming: Mapping[str, Any] | None,
    *,
    existing_credentials_json: Optional[str] = None,
) -> dict[str, Any]:
    """Merge (when updating), then normalize. The order matters.

    A preserved value has already been normalized once on the way in, but a
    caller can also supply a raw value for a preserved field, so normalization
    runs last and covers both.
    """
    merged = (
        merge_credentials(manifest, existing_credentials_json, incoming)
        if existing_credentials_json is not None
        else dict(incoming or {})
    )
    return normalize(manifest, FieldStore.CREDENTIALS, merged)
