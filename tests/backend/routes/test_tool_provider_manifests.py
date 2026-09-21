"""Manifest registry: shape, validation, merging and normalization.

Replaces the six per-provider test files that each asserted the same three
things about a different key. Provider-specific cases that are genuinely
specific (GitLab's namespace shape, Azure DevOps org parsing) stay, as
parametrized cases rather than separate modules.
"""

import json
from unittest.mock import patch

import pytest

from rhesis.backend.app.services.tool.providers import (
    MANIFESTS,
    get_manifest,
    merge_credentials,
    prepare_credentials,
    validate_store,
)
from rhesis.backend.app.services.tool.providers.spec import (
    FieldStore,
    ProviderFieldError,
    ToolAction,
    Transport,
)

ALL_KEYS = sorted(MANIFESTS)


@pytest.fixture(autouse=True)
def _no_dns():
    """Keep URL validation off the network.

    ``JIRA_URL`` and ``CONFLUENCE_URL`` resolve their hostname to check it
    against the SSRF blocklist. Left unpatched these unit tests fail on an
    offline runner and hang on a slow resolver, for reasons unrelated to what
    they assert.
    """
    with patch(
        "rhesis.backend.app.services.tool.url_validation.socket.getaddrinfo",
        return_value=[(None, None, None, None, ("93.184.216.34", 0))],
    ):
        yield


# --- registry shape -------------------------------------------------------


def test_registry_covers_every_seeded_provider():
    """The manifest set and the ToolProviderType seed rows must not drift."""
    from pathlib import Path

    seed = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "apps/backend/src/rhesis/backend/app/services/initial_data.json"
        ).read_text()
    )
    seeded = {
        row["type_value"]
        for row in seed["type_lookup"]
        if row.get("type_name") == "ToolProviderType"
    }
    assert seeded == set(MANIFESTS)


@pytest.mark.parametrize("key", ALL_KEYS)
def test_manifest_is_self_consistent(key):
    manifest = MANIFESTS[key]
    assert manifest.key == key
    assert manifest.display_name
    assert manifest.description
    assert manifest.auth_methods, "every provider needs at least one way in"
    assert manifest.actions, "a provider with no actions is unreachable"
    # A field key must be unique, or one silently shadows the other.
    keys = [f.key for f in manifest.fields]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize("key", ALL_KEYS)
def test_mcp_providers_declare_a_template(key):
    manifest = MANIFESTS[key]
    if Transport.MCP in manifest.actions.values():
        assert manifest.mcp_template, f"{key} serves an action over MCP but names no template"


@pytest.mark.parametrize("key", ALL_KEYS)
def test_serialize_is_json_safe(key):
    payload = MANIFESTS[key].serialize()
    json.dumps(payload)
    assert payload["key"] == key
    assert {"kind", "label", "available"} <= set(payload["auth_methods"][0])


@pytest.mark.parametrize("key", ALL_KEYS)
def test_route_resolves_every_declared_action(key):
    """``route()`` reads the manifest, so the two cannot disagree."""
    from rhesis.backend.app.services.tool.actions import route

    manifest = MANIFESTS[key]
    for action, transport in manifest.actions.items():
        assert route(key, action) is transport


def test_route_rejects_an_unsupported_action():
    from rhesis.backend.app.services.tool.actions import route
    from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError

    # Shortcut has no ticket-creation path.
    with pytest.raises(ToolConfigurationError):
        route("shortcut", ToolAction.CREATE_TICKET)


@pytest.mark.parametrize("key", ALL_KEYS)
def test_rest_providers_declare_a_client(key):
    """A provider routing an action over REST needs a client to build."""
    manifest = MANIFESTS[key]
    if Transport.REST in manifest.actions.values():
        assert manifest.rest_client is not None, f"{key} routes REST but names no client"
    else:
        assert manifest.rest_client is None, f"{key} names a REST client it never uses"


@pytest.mark.parametrize("key", ALL_KEYS)
def test_declared_mcp_template_exists_on_disk(key):
    """A template named but not shipped fails at run time, not import time."""
    from pathlib import Path

    manifest = MANIFESTS[key]
    if not manifest.mcp_template:
        pytest.skip(f"{key} declares no MCP template")

    templates = (
        Path(__file__).resolve().parents[3] / "sdk/src/rhesis/sdk/agents/mcp/provider_templates"
    )
    assert (templates / manifest.mcp_template).is_file()


def test_get_manifest_returns_none_for_unknown_provider():
    assert get_manifest("does-not-exist") is None


# --- credential validation ------------------------------------------------


def _sample_value(field) -> str:
    """A value that satisfies *field*, including its validator."""
    if field.key.endswith("_URL"):
        return "https://example.atlassian.net"
    return "value"


def _credentials_for(key: str) -> dict:
    """A minimal set of credentials that satisfies a provider."""
    return {
        f.key: _sample_value(f)
        for f in MANIFESTS[key].fields_in(FieldStore.CREDENTIALS)
        if f.required
    }


@pytest.mark.parametrize("key", ALL_KEYS)
def test_complete_credentials_pass(key):
    validate_store(MANIFESTS[key], FieldStore.CREDENTIALS, _credentials_for(key))


@pytest.mark.parametrize("key", ALL_KEYS)
def test_missing_required_credential_names_the_key(key):
    manifest = MANIFESTS[key]
    required = manifest.fields_in(FieldStore.CREDENTIALS)
    required = [f for f in required if f.required]
    if not required:
        pytest.skip(f"{key} has no required credentials")

    for field in required:
        incomplete = _credentials_for(key)
        del incomplete[field.key]
        with pytest.raises(ProviderFieldError) as exc:
            validate_store(manifest, FieldStore.CREDENTIALS, incomplete)
        assert field.leaf in str(exc.value)


@pytest.mark.parametrize("key", ALL_KEYS)
def test_blank_credential_is_rejected(key):
    manifest = MANIFESTS[key]
    required = [f for f in manifest.fields_in(FieldStore.CREDENTIALS) if f.required]
    if not required:
        pytest.skip(f"{key} has no required credentials")

    blanked = _credentials_for(key)
    blanked[required[0].key] = "   "
    with pytest.raises(ProviderFieldError):
        validate_store(manifest, FieldStore.CREDENTIALS, blanked)


# --- metadata validation --------------------------------------------------


@pytest.mark.parametrize(
    "key,metadata,expected_fragment",
    [
        ("gitlab", None, "project metadata"),
        ("gitlab", {}, "project metadata"),
        ("gitlab", {"project": {}}, "namespace"),
        ("gitlab", {"project": {"namespace": "no-slash"}}, "group/project"),
        ("azure_devops", {}, "project"),
        ("azure_devops", {"project": "   "}, "project"),
        ("jira", {}, "space_key"),
        ("jira", {"space_key": "  "}, "space_key"),
    ],
)
def test_metadata_rejections(key, metadata, expected_fragment):
    with pytest.raises(ProviderFieldError) as exc:
        validate_store(MANIFESTS[key], FieldStore.METADATA, metadata)
    assert expected_fragment in str(exc.value)


@pytest.mark.parametrize(
    "key,metadata",
    [
        ("gitlab", {"project": {"namespace": "my-group/my-project"}}),
        ("azure_devops", {"project": "Contoso"}),
        ("jira", {"space_key": "ENG"}),
        ("asana", {}),
        ("asana", None),
        ("asana", {"workspace_gid": "123"}),
        ("confluence", {}),
    ],
)
def test_metadata_acceptances(key, metadata):
    validate_store(MANIFESTS[key], FieldStore.METADATA, metadata)


@pytest.mark.parametrize(
    "key,store,payload",
    [
        ("asana", FieldStore.METADATA, {"workspace_gid": "   "}),
        ("confluence", FieldStore.METADATA, {"space_key": ""}),
        (
            "gitlab",
            FieldStore.CREDENTIALS,
            {"GITLAB_PERSONAL_ACCESS_TOKEN": "t", "GITLAB_API_URL": ""},
        ),
        (
            "confluence",
            FieldStore.CREDENTIALS,
            {
                "CONFLUENCE_URL": "https://x.atlassian.net",
                "CONFLUENCE_USERNAME": "e@x.com",
                "CONFLUENCE_API_TOKEN": "t",
            },
        ),
        ("github", FieldStore.METADATA, {"repository": {"owner": "", "repo": ""}}),
    ],
)
def test_blank_optional_field_means_not_provided(key, store, payload):
    """A generic form posts "" for every field left empty.

    ``GET /tools/providers`` exists so the frontend can render fields it knows
    nothing about, and such a form submits blanks rather than omitting keys.
    Rejecting those would 400 a gitlab.com connection for leaving the
    self-managed API URL empty.
    """
    validate_store(MANIFESTS[key], store, payload)


def test_blank_required_field_is_still_rejected():
    with pytest.raises(ProviderFieldError):
        validate_store(MANIFESTS["linear"], FieldStore.CREDENTIALS, {"LINEAR_API_TOKEN": "  "})


@pytest.mark.parametrize(
    "key,url_field,token_field,email_field",
    [
        ("jira", "JIRA_URL", "JIRA_API_TOKEN", "JIRA_USERNAME"),
        ("confluence", "CONFLUENCE_URL", "CONFLUENCE_API_TOKEN", "CONFLUENCE_USERNAME"),
    ],
)
def test_atlassian_email_is_required(key, url_field, token_field, email_field):
    """Both clients authenticate with HTTP Basic ``(username, api_token)``.

    A blank email would pass validation and then fail the health check with an
    opaque 401, so the form has to catch it.
    """
    with pytest.raises(ProviderFieldError) as exc:
        validate_store(
            MANIFESTS[key],
            FieldStore.CREDENTIALS,
            {url_field: "https://x.atlassian.net", token_field: "t", email_field: ""},
        )
    assert email_field in str(exc.value)


# --- merging on update ----------------------------------------------------


@pytest.mark.parametrize("key", ALL_KEYS)
def test_preserved_fields_survive_a_partial_update(key):
    """A PATCH carrying only a new secret keeps every preserved field."""
    manifest = MANIFESTS[key]
    preserved = [f for f in manifest.fields_in(FieldStore.CREDENTIALS) if f.preserve_on_update]
    if not preserved:
        pytest.skip(f"{key} has nothing to preserve")

    stored = {f.key: f"stored-{f.key}" for f in manifest.fields_in(FieldStore.CREDENTIALS)}
    secret = next(f for f in manifest.fields_in(FieldStore.CREDENTIALS) if f.secret)
    merged = merge_credentials(manifest, json.dumps(stored), {secret.key: "fresh"})

    assert merged[secret.key] == "fresh"
    for field in preserved:
        if field.key != secret.key:
            assert merged[field.key] == stored[field.key]


def test_incoming_value_wins_over_stored():
    manifest = MANIFESTS["gitlab"]
    stored = json.dumps({"GITLAB_API_URL": "https://old.example.com/api/v4"})
    merged = merge_credentials(
        manifest,
        stored,
        {"GITLAB_PERSONAL_ACCESS_TOKEN": "t", "GITLAB_API_URL": "https://new.example.com/api/v4"},
    )
    assert merged["GITLAB_API_URL"] == "https://new.example.com/api/v4"


@pytest.mark.parametrize("stored", ["not json", "", None, "[]", "null"])
def test_unreadable_stored_credentials_do_not_break_the_merge(stored):
    """A corrupt credentials blob degrades to "nothing to preserve", not a 500."""
    merged = merge_credentials(MANIFESTS["gitlab"], stored, {"GITLAB_PERSONAL_ACCESS_TOKEN": "t"})
    assert merged == {"GITLAB_PERSONAL_ACCESS_TOKEN": "t"}


def test_non_preserved_secret_is_not_resurrected():
    """An omitted secret stays omitted; only declared fields carry over."""
    manifest = MANIFESTS["gitlab"]
    stored = json.dumps({"GITLAB_PERSONAL_ACCESS_TOKEN": "old-secret"})
    merged = merge_credentials(manifest, stored, {})
    assert "GITLAB_PERSONAL_ACCESS_TOKEN" not in merged


# --- normalization --------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("acme", "acme"),
        ("  acme  ", "acme"),
        ("https://dev.azure.com/acme", "acme"),
        ("https://dev.azure.com/acme/", "acme"),
        ("https://dev.azure.com/acme/some/project", "acme"),
        ("acme.visualstudio.com", "acme"),
    ],
)
def test_azure_devops_org_is_normalized(raw, expected):
    prepared = prepare_credentials(
        MANIFESTS["azure_devops"],
        {"AZURE_DEVOPS_ORG": raw, "AZURE_DEVOPS_EMAIL": "e@x.com", "AZURE_DEVOPS_PAT": "p"},
    )
    assert prepared["AZURE_DEVOPS_ORG"] == expected


@pytest.mark.parametrize("raw", ["http://x", "a/b", "https://example.com"])
def test_azure_devops_org_rejects_non_org_values(raw):
    with pytest.raises(ProviderFieldError):
        prepare_credentials(
            MANIFESTS["azure_devops"],
            {"AZURE_DEVOPS_ORG": raw, "AZURE_DEVOPS_EMAIL": "e@x.com", "AZURE_DEVOPS_PAT": "p"},
        )


@pytest.mark.parametrize("key", ALL_KEYS)
def test_whitespace_is_stripped_from_every_declared_field(key):
    """A token pasted with a trailing newline used to be stored verbatim."""
    manifest = MANIFESTS[key]
    fields = [f for f in manifest.fields_in(FieldStore.CREDENTIALS) if f.normalize is None]
    if not fields:
        pytest.skip(f"{key} has no plain credential fields")

    padded = {f.key: "  value  " for f in fields}
    prepared = prepare_credentials(manifest, padded)
    for field in fields:
        assert prepared[field.key] == "value"


def test_normalize_does_not_invent_absent_keys():
    """Only fields actually supplied come back.

    The old ``prepare_azure_devops_credentials`` wrote ``AZURE_DEVOPS_EMAIL: ""``
    even when the caller never sent one, which put an empty string into the MCP
    config template for any path that skipped validation.
    """
    prepared = prepare_credentials(MANIFESTS["azure_devops"], {"AZURE_DEVOPS_PAT": "p"})
    assert prepared == {"AZURE_DEVOPS_PAT": "p"}


def test_ssrf_blocklist_applies_to_instance_urls(_no_dns):
    with (
        patch(
            "rhesis.backend.app.services.tool.url_validation.socket.getaddrinfo",
            return_value=[(None, None, None, None, ("169.254.169.254", 0))],
        ),
        pytest.raises(ProviderFieldError),
    ):
        validate_store(
            MANIFESTS["jira"],
            FieldStore.CREDENTIALS,
            {
                "JIRA_URL": "http://169.254.169.254",
                "JIRA_API_TOKEN": "t",
            },
        )


# --- GET /tools/providers -------------------------------------------------


def test_providers_endpoint_returns_every_manifest():
    from rhesis.backend.app.routers.tools import read_tool_providers

    payload = read_tool_providers()
    assert {row["key"] for row in payload} == set(MANIFESTS)
    json.dumps(payload)


def test_providers_endpoint_describes_fields_without_carrying_values():
    """The contract is a form description, not a credential dump.

    ``secret: true`` marks a field for masked input; it must never be
    accompanied by anything holding what a tenant actually stored.
    """
    from rhesis.backend.app.routers.tools import read_tool_providers

    allowed = {
        "key",
        "label",
        "store",
        "required",
        "secret",
        "preserve_on_update",
        "placeholder",
        "help_text",
        "help_url",
    }
    for provider in read_tool_providers():
        for field in provider["fields"]:
            assert set(field) == allowed


def test_providers_route_precedes_the_tool_id_route():
    """``/providers`` must be matched before ``/{tool_id}`` or it 422s."""
    from rhesis.backend.app.routers.tools import router

    paths = [route.path for route in router.routes]
    assert paths.index("/tools/providers") < paths.index("/tools/{tool_id}")


# --- registry vs. persisted provider rows ---------------------------------


def test_every_manifest_has_a_migration_that_seeds_it():
    """A provider in the registry but in no migration never reaches an
    existing database.

    ``initial_data.json`` only covers fresh installs. Upgrades get their
    ``ToolProviderType`` row from a migration, and forgetting that half is the
    failure mode this catches: the provider works locally and 400s in
    production with "Invalid tool provider type".

    The migrations are deliberately left as literal, per-provider files rather
    than one that reads this registry. A migration must replay identically
    forever, so it cannot depend on code that changes after it ships.
    """
    from pathlib import Path

    versions = (
        Path(__file__).resolve().parents[3] / "apps/backend/src/rhesis/backend/alembic/versions"
    )
    seeded_by_migrations = set()
    for migration in versions.glob("*.py"):
        text = migration.read_text()
        if "ToolProviderType" not in text:
            continue
        for key in MANIFESTS:
            if f"'{key}'" in text:
                seeded_by_migrations.add(key)

    missing = set(MANIFESTS) - seeded_by_migrations
    assert not missing, f"providers with no seeding migration: {sorted(missing)}"


# --- MCP scope context ----------------------------------------------------


@pytest.mark.parametrize(
    "provider,metadata,expected",
    [
        ("gitlab", None, None),
        ("gitlab", {}, None),
        (
            "gitlab",
            {"project": {"namespace": "my-group/my-project"}},
            {"namespace": "my-group/my-project"},
        ),
        ("asana", {}, None),
        ("asana", {"workspace_gid": "123"}, {"workspace_gid": "123"}),
        ("asana", {"workspace_gid": "  "}, None),
        ("azure_devops", {"project": "Contoso"}, {"project": "Contoso"}),
        ("azure_devops", {"project": " Contoso "}, {"project": "Contoso"}),
    ],
)
def test_scope_context_narrows_the_agent(provider, metadata, expected):
    from rhesis.backend.app.services.tool.mcp.config import _scope_context_from_metadata

    assert _scope_context_from_metadata(provider, metadata) == expected


@pytest.mark.parametrize(
    "provider,metadata",
    [
        ("gitlab", {"project": {}}),
        ("gitlab", {"project": "flat-string"}),
        ("gitlab", {"project": {"namespace": "no-slash"}}),
        ("azure_devops", {"project": None}),
        ("azure_devops", {"project": "   "}),
    ],
)
def test_malformed_scope_metadata_fails_loudly(provider, metadata):
    """Naming a project but supplying nothing usable must not run unscoped.

    Returning ``None`` here would let the MCP agent search everything the token
    can reach, which is a silent data-scope escalation rather than an error.
    """
    from rhesis.backend.app.services.tool.exceptions import ToolConfigurationError
    from rhesis.backend.app.services.tool.mcp.config import _scope_context_from_metadata

    with pytest.raises(ToolConfigurationError):
        _scope_context_from_metadata(provider, metadata)
