---
name: ee-feature
description: Add a new Enterprise Edition feature behind a feature gate, across backend and frontend. Use when adding an EE-only capability such as SSO.
---

# Adding a new EE feature

`FeatureRegistry` is for EE features only. A capability that ships in `apps/backend/` under MIT is
unconditionally available and needs no gating — don't register it.

1. Add a member to `FeatureName` in `app/features/__init__.py`.
2. Implement the feature under `ee/backend/src/rhesis/backend/ee/<feature>/`.
3. Register it in `ee/backend/src/rhesis/backend/ee/__init__.py:bootstrap()` by calling
   `FeatureRegistry.register(Feature(...))` with an optional `runtime_check`, then
   `app.include_router(...)` for any new endpoints.
4. Gate routes with `Depends(require_feature(FeatureName.X))`. Use
   `FeatureRegistry.is_available(name, org)` for org-aware checks elsewhere, and
   `FeatureRegistry.is_registered(name)` for early-bailout checks before an org has been resolved
   (e.g. inside an OIDC callback).
5. Mirror the name in `apps/frontend/src/constants/features.ts` and wrap the UI in
   `<FeatureGate feature={FeatureName.X}>`.

## The import boundary

Core code must never import from `rhesis.backend.ee.*`. The only core-side coupling is the
`try/except ImportError` in `app/ee_bootstrap.py`, which is what lets a Community build run without
the EE package installed. The `community-boundary` CI job fails the PR if you break this.

Background on the registry and the gating dependencies is in `apps/backend/AGENTS.md`; the frontend
half is in `apps/frontend/AGENTS.md`.
