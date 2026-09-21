"""Declarative description of a tool provider.

Every fact that used to be a per-provider ``if`` lives here as data: which
credential and metadata fields a provider needs, how each one is validated and
normalized, which fields survive a partial update, and which transport serves
each action.

The pattern is the one already used by
:mod:`rhesis.backend.app.services.tool.actions` -- a table instead of a switch.
This module widens it from routing to the whole provider definition, so adding
a provider is one file rather than edits scattered across the router, the
credential merger, the seed data and the frontend drawer.

:class:`ToolAction` and :class:`Transport` live here rather than in ``actions``
so that ``actions.route`` can read the registry without a circular import.

Nothing here knows about HTTP. Validation raises :class:`ProviderFieldError`,
and the router maps that to a 400; the MCP and REST layers call the same
helpers without a request in scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from typing import Any, Callable, Dict, Mapping, Optional, Tuple


class ToolAction(str, Enum):
    """A user-facing operation a tool can perform."""

    TEST_CONNECTION = "test_connection"
    EXTRACT = "extract"
    CREATE_TICKET = "create_ticket"


class Transport(str, Enum):
    """How an action is carried out."""

    REST = "rest"
    MCP = "mcp"


class FieldStore(str, Enum):
    """Which column on ``Tool`` a field is persisted in."""

    #: Encrypted JSON blob. Anything secret, plus the few non-secret values
    #: (org name, instance URL) that historically shipped alongside a token.
    CREDENTIALS = "credentials"
    #: Plain JSONB. Scoping values the user picks, such as a repo or workspace.
    METADATA = "metadata"


class AuthKind(str, Enum):
    """How a connection obtains its credential.

    Only :attr:`API_TOKEN` exists today. ``oauth2`` and ``redirect_token`` are
    named here because the serialized contract the frontend branches on must be
    stable before they are implemented: adding a kind is then additive, and no
    frontend code has to change shape when it lands.
    """

    API_TOKEN = "api_token"
    OAUTH2 = "oauth2"
    REDIRECT_TOKEN = "redirect_token"


class ProviderFieldError(ValueError):
    """A provider field is missing or malformed.

    Carries the exact user-facing sentence. The router turns it into a 400
    verbatim, so these strings are part of the API contract and are asserted by
    tests.
    """


@dataclass(frozen=True)
class FieldMessages:
    """Overrides for the generated validation sentences.

    Defaults read ``"<Provider> integrations require '<KEY>'"`` and
    ``"<Provider> '<KEY>' must be a non-empty string"``. A provider overrides
    only where its existing wording differs, so no error text changes.
    """

    missing: Optional[str] = None
    invalid: Optional[str] = None
    #: Used when a nested metadata field's parent object is absent entirely,
    #: e.g. GitLab's ``project`` before ``project.namespace`` can be read.
    container_missing: Optional[str] = None


@dataclass(frozen=True)
class ProviderField:
    """One value a provider needs from the user."""

    key: str
    label: str
    store: FieldStore
    required: bool = True
    secret: bool = False
    #: Keep the stored value when an update leaves this field blank. Set on
    #: anything the user is not asked to retype on every edit: instance URLs,
    #: org names, and the second half of a two-part credential.
    preserve_on_update: bool = False
    placeholder: str = ""
    help_text: str = ""
    help_url: str = ""
    #: Raises :class:`ValueError` with a user-facing message. The raised text is
    #: used as-is, so a validator owns its own wording.
    validate: Optional[Callable[[str], None]] = None
    #: Returns the value to persist. Runs before validation.
    normalize: Optional[Callable[[str], str]] = None
    messages: FieldMessages = dataclass_field(default_factory=FieldMessages)

    @property
    def leaf(self) -> str:
        """Last segment of a dotted key: ``project.namespace`` -> ``namespace``."""
        return self.key.rsplit(".", 1)[-1]

    @property
    def path(self) -> Tuple[str, ...]:
        """Dotted key split into segments."""
        return tuple(self.key.split("."))


@dataclass(frozen=True)
class ApiTokenAuth:
    """Connect by pasting a credential issued in the provider's own UI."""

    kind: AuthKind = AuthKind.API_TOKEN
    label: str = "API token"
    help_url: str = ""


#: Union of auth methods. One member today; see :class:`AuthKind`.
AuthMethod = ApiTokenAuth


@dataclass(frozen=True)
class ProviderManifest:
    """Everything the platform knows about one tool provider."""

    key: str
    display_name: str
    description: str
    auth_methods: Tuple[AuthMethod, ...]
    fields: Tuple[ProviderField, ...]
    actions: Mapping[ToolAction, Transport]
    #: Jinja template under ``sdk/.../agents/mcp/provider_templates/``. Only set
    #: for providers that serve at least one action over MCP.
    mcp_template: Optional[str] = None
    #: Builds the REST client from a credentials mapping. Only set for
    #: providers that serve at least one action over REST.
    rest_client: Optional[Callable[[Dict[str, str]], Any]] = None

    def fields_in(self, store: FieldStore) -> Tuple[ProviderField, ...]:
        return tuple(f for f in self.fields if f.store is store)

    def field(self, key: str) -> Optional[ProviderField]:
        for candidate in self.fields:
            if candidate.key == key:
                return candidate
        return None

    def serialize(self) -> dict[str, Any]:
        """Shape returned by ``GET /tools/providers``.

        Drives the tile grid and every form field on the frontend, replacing the
        constants that used to be duplicated in ``config/tool-providers.tsx`` and
        ``ToolConnectionDrawer.tsx``.
        """
        return {
            "key": self.key,
            "display_name": self.display_name,
            "description": self.description,
            "auth_methods": [
                {
                    "kind": method.kind.value,
                    "label": method.label,
                    "help_url": method.help_url,
                    # Always true for api_token. OAuth methods resolve this per
                    # deployment, from whether client credentials are configured.
                    "available": True,
                }
                for method in self.auth_methods
            ],
            "fields": [
                {
                    "key": f.key,
                    "label": f.label,
                    "store": f.store.value,
                    "required": f.required,
                    "secret": f.secret,
                    "preserve_on_update": f.preserve_on_update,
                    "placeholder": f.placeholder,
                    "help_text": f.help_text,
                    "help_url": f.help_url,
                }
                for f in self.fields
            ],
            "actions": sorted(action.value for action in self.actions),
        }
