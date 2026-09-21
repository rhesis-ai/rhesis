"""Registry of tool provider manifests.

One import site for every provider definition. Adding a provider means adding a
module here and listing it in :data:`_MODULES`; nothing else in the backend
needs to learn its name.

The registry is also the source of truth for the ``ToolProviderType`` rows in
``type_lookup``, so the seed data and the provider list served to the frontend
cannot drift apart.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from rhesis.backend.app.services.tool.providers import (
    asana,
    azure_devops,
    confluence,
    github,
    gitlab,
    jira,
    linear,
    notion,
    shortcut,
    trello,
)
from rhesis.backend.app.services.tool.providers.spec import (
    ApiTokenAuth,
    AuthKind,
    FieldMessages,
    FieldStore,
    ProviderField,
    ProviderFieldError,
    ProviderManifest,
)
from rhesis.backend.app.services.tool.providers.validation import (
    merge_credentials,
    normalize,
    prepare_credentials,
    read_field,
    validate_field,
    validate_store,
)

_MODULES = (
    notion,
    github,
    jira,
    confluence,
    gitlab,
    shortcut,
    asana,
    azure_devops,
    linear,
    trello,
)

MANIFESTS: Dict[str, ProviderManifest] = {
    module.MANIFEST.key: module.MANIFEST for module in _MODULES
}


def get_manifest(provider: str) -> Optional[ProviderManifest]:
    """Return the manifest for *provider*, or ``None`` if it is unknown.

    Callers that must tolerate an unknown provider (a tool row written by a
    newer release, say) check for ``None`` rather than raising, so an
    unrecognized provider degrades to no extra validation instead of a 500.
    """
    return MANIFESTS.get(provider)


def all_manifests() -> Tuple[ProviderManifest, ...]:
    """Every manifest, in the order providers were introduced."""
    return tuple(MANIFESTS.values())


def provider_keys() -> Tuple[str, ...]:
    return tuple(MANIFESTS)


__all__ = [
    "ApiTokenAuth",
    "AuthKind",
    "FieldMessages",
    "FieldStore",
    "MANIFESTS",
    "ProviderField",
    "ProviderFieldError",
    "ProviderManifest",
    "all_manifests",
    "get_manifest",
    "merge_credentials",
    "normalize",
    "prepare_credentials",
    "provider_keys",
    "read_field",
    "validate_field",
    "validate_store",
]
