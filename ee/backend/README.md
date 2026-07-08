# rhesis-backend-ee

Enterprise Edition backend package for Rhesis. Licensed under the
[Rhesis Enterprise License](../LICENSE).

This package registers enterprise features (SSO, audit log retention,
advanced RBAC, etc.) with the core `FeatureRegistry` at application
startup. It is loaded conditionally: if the package is not installed,
or if `bootstrap()` is never called, the application behaves as the
Community Edition.

## Structure

```
ee/backend/src/rhesis/backend/ee/
  __init__.py       # bootstrap(app) entry point + dynamic __version__
  sso/              # Per-org OIDC SSO
    __init__.py
    audit.py             # SSO audit logging
    encryption.py        # client_secret Fernet encryption (SSO_ENCRYPTION_KEY)
    http_client.py       # SSRF-safe HTTP client for IdP discovery
    oidc.py              # OIDC provider abstraction + signed state
    provider_enricher.py # /auth/providers decorator (registered from bootstrap)
    rate_limits.py       # SSO route rate-limit constants
    router.py            # /auth/sso/* and /organizations/{id}/sso/* endpoints
    runtime_check.py
    schemas.py           # SSOConfig pydantic schema
    user_utils.py        # find_or_create_sso_user
```

## Dependency rule

EE code may import freely from `rhesis.backend.*` (core). Core code
must **never** import from `rhesis.backend.ee.*`. The only core-side
surface is `ee_bootstrap.py:bootstrap_ee(app)`, which calls into this
package via a guarded `try/except ImportError`.

The rule is enforced statically by `tests/backend/test_ee_boundary.py`
and the `community-boundary` CI job. The check is AST-based and
catches module-level imports; function-body and dynamic imports are
out of scope (and a code smell anyway — CODEOWNERS review on
`apps/backend/` is the secondary defence).

## Adding a new EE feature

1. **Add to `FeatureName`** in
   `apps/backend/src/rhesis/backend/app/features/__init__.py`. The
   enum is the canonical wire identifier shared between backend and
   frontend; new EE features get a new member here. This is the only
   one-line edit core ever needs.

2. **Implement under `ee/backend/src/rhesis/backend/ee/<feature>/`**.
   Mirror the SSO subpackage layout: routers, schemas, runtime
   checks, encryption helpers, rate-limit constants, and any other
   feature-specific code all live inside the EE subpackage. Do not
   place feature-specific code in `apps/backend/`, even if it is a
   "utility" — the boundary guard catches imports, but only review
   catches symbol-name leaks (see "Soft couplings" below).

3. **Register in `ee/__init__.py:bootstrap()`**. Construct the
   `Feature` instance, call `FeatureRegistry.register(...)`, and
   `app.include_router(<feature>_router)`. If the router relies on
   path-based auth, set `route_class = app.router.route_class`
   before `include_router` (see SSO for the pattern).

4. **Add tests under `tests/backend/ee/<feature>/`**. The autouse
   conftest in `tests/backend/ee/conftest.py` re-bootstraps EE
   features whenever the registry has been wiped, so tests can
   call `FeatureRegistry.reset()` freely without breaking each
   other.

5. **Add `FeatureName.<NEW_FEATURE>` to the frontend** in
   `apps/frontend/src/constants/features.ts`. Wrap UI in
   `<FeatureGate feature={FeatureName.NEW_FEATURE}>`. The frontend
   does not have a physical EE separation today (see below); gating
   is purely runtime via the `/features` endpoint response.

## Extension points (core-published seams for EE to plug into)

Core publishes a small number of named extension points that EE uses
to decorate behaviour at runtime without core ever importing from
`rhesis.backend.ee.*`. EE wires into these from
`ee/__init__.py:bootstrap()`.

### Provider enricher hook

`apps/backend/src/rhesis/backend/app/auth/provider_hooks.py` exposes
`register_provider_enricher(callback)` and `apply_enrichers(...)`.
Core's `GET /auth/providers` calls `apply_enrichers(providers, org)`
after building the base list and before returning the response. SSO
plugs in via `ee/.../sso/provider_enricher.py:sso_provider_enricher`,
which reads `organization.sso_config` and appends an `sso` entry plus
applies the org-level `allowed_auth_methods` filter.

When adding an EE feature that needs to influence the public provider
list (e.g. SAML), add a new enricher in EE and register it from
`bootstrap()`. Core stays untouched.

### Public route registry

`apps/backend/src/rhesis/backend/app/auth/public_routes.py` exposes
`PUBLIC_ROUTES` and `TOKEN_ENABLED_ROUTES` as mutable module-level
lists. EE extends them in `bootstrap()` *before* the EE
`app.include_router` call, so the auth class sees the extended list at
the moment it resolves dependencies for EE routes. SSO adds
`/auth/sso/{org_id}` and `/auth/sso/callback` this way; core's main
module knows nothing about either path.

When adding an EE feature with public endpoints, follow the same
pattern: append to `PUBLIC_ROUTES` (or `TOKEN_ENABLED_ROUTES`) before
`app.include_router(<your_router>)`.

## Soft couplings (intentional)

The following are deliberate exceptions to the "core never knows
about EE" guideline. They are documented here so future maintainers
do not silently expand the surface.

### `FeatureName` enum members

`apps/backend/src/rhesis/backend/app/features/__init__.py` declares
the `FeatureName` enum, with one member per EE feature
(`FeatureName.SSO` today). The enum is the canonical wire identifier
shared by backend, frontend, and license JWT claims, so it has to
live somewhere central. Adding a new EE feature is a one-line edit
to this enum; the rest of the implementation stays in `ee/`.

### `Organization.sso_config` and `Organization.slug` columns

The `organization` SQLAlchemy model declares an `sso_config` JSON
column and a `slug` string column. Both are core schema (the database
is core-owned) but the names hint at SSO. Core never *parses*
`sso_config` — it stores it as opaque JSON and the EE provider
enricher is the only consumer. Renaming `sso_config` to a more
generic `auth_config` would require a customer-facing migration; the
pragmatic call is to leave the name and document the intent here.

### Database migrations

EE features that need schema changes on **core tables** add their
migrations to the core alembic chain at
`apps/backend/src/rhesis/backend/alembic/versions/`. The two SSO
migrations (`add_sso_config_to_organization`,
`add_slug_to_organization`) follow this pattern.

EE-owned tables (none today) would warrant a separate alembic
environment under `ee/backend/`. We deferred that decision until a
real EE-only table exists.

### Frontend EE separation

The frontend follows the same physical-separation rule as the backend.
EE-owned UI lives under `ee/frontend/` (separate licence, separate
CODEOWNERS) and core wires it in via a single `@ee/*` path alias plus
one bridge file (`apps/frontend/src/ee_bootstrap.ts`). ESLint enforces
that no other core file imports from `@ee/*`. See
`ee/frontend/README.md` for the playbook to add a new EE feature, the
list of published extension points, and the recipe to produce an
MIT-only build.

The backend's `/features` endpoint is what powers `<FeatureGate>`
runtime gating in the UI. Defence-in-depth is intentional: even if a
user tampers with the frontend bundle, the backend returns 404 for
unlicensed feature routes via `require_feature`.

## License providers

Core ships `DefaultLicenseProvider`, which denies every EE feature and
reports the `community` edition — the safe default when the EE package
isn't installed at all.

When the EE package *is* installed, bootstrap installs
`SignedTokenLicenseProvider` (`ee/backend/src/rhesis/backend/ee/licensing/
provider.py`) in its place. It verifies Ed25519-signed JWTs (`EdDSA`, not
RS256) and resolves entitlements in this order:

1. `RHESIS_LICENSE` env var — a blanket `sub:"*"` token covering every
   org in the deployment.
2. `organization.license` column — a per-org token whose `sub` must match
   the org's UUID.
3. Deny.

There is no environment-based bypass. A missing, invalid, or expired
license results in the `community` edition — identically in local
development, staging, production, and self-hosted deployments. To
exercise EE features locally, mint a real non-prod token with the CLI
(`python -m rhesis.backend.ee.licensing.cli mint --org "*" --edition
enterprise --kid rhesis-nonprod-v1`) and set it as `RHESIS_LICENSE`.
