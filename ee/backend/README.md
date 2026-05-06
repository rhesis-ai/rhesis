# rhesis-backend-ee

Enterprise Edition backend package for Rhesis. Licensed under the [Rhesis Enterprise License](../LICENSE).

This package registers enterprise features (SSO, audit log retention, advanced RBAC, etc.)
with the core `FeatureRegistry` at application startup. It is loaded conditionally — if the
package is not installed, or `bootstrap()` is never called, the application behaves as the
Community Edition.

## Structure

```
ee/backend/src/rhesis/backend/ee/
  __init__.py      # bootstrap(app) entry point
  sso/             # Per-org OIDC/SAML SSO (added in PR 2)
```

## Dependency rule

EE code may import from `rhesis.backend.*` (core). Core code must NEVER import from
`rhesis.backend.ee.*`. The only core-side surface is `ee_bootstrap.py:bootstrap_ee(app)`,
which calls into this package via a guarded `try/except ImportError`.
