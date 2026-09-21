"""Shared field validators and builders used by more than one manifest."""

from __future__ import annotations

from rhesis.backend.app.services.tool.azure_devops import normalize_azure_devops_org
from rhesis.backend.app.services.tool.providers.spec import (
    ApiTokenAuth,
    FieldStore,
    ProviderField,
)
from rhesis.backend.app.services.tool.url_validation import validate_base_url


def api_token_field(
    key: str,
    *,
    label: str = "API token",
    required: bool = True,
    preserve_on_update: bool = False,
    help_url: str = "",
) -> ProviderField:
    """The single secret most providers authenticate with."""
    return ProviderField(
        key=key,
        label=label,
        store=FieldStore.CREDENTIALS,
        required=required,
        secret=True,
        preserve_on_update=preserve_on_update,
        help_url=help_url,
    )


def base_url_field(key: str, label: str, *, required: bool = False) -> ProviderField:
    """A user-supplied instance URL, checked against the SSRF blocklist.

    ``validate_base_url`` raises ``ValueError``; the validation layer converts
    that to the 400 the router used to raise inline.
    """
    return ProviderField(
        key=key,
        label=label,
        store=FieldStore.CREDENTIALS,
        required=required,
        preserve_on_update=True,
        validate=lambda value, _field=key: validate_base_url(value, _field),
    )


def must_be_namespace(value: str) -> None:
    """A ``group/project`` path, not a bare name."""
    if "/" not in value.strip():
        raise ValueError("GitLab 'namespace' must be a non-empty group/project path")


def azure_devops_org(value: str) -> str:
    return normalize_azure_devops_org(value)


__all__ = [
    "ApiTokenAuth",
    "api_token_field",
    "azure_devops_org",
    "base_url_field",
    "must_be_namespace",
]
