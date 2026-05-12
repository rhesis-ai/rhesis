"""API Clients EE feature.

Per-organization OAuth2 / RFC 8693 clients used by external integrations
(e.g. br.AI.n) to mint Rhesis access tokens on behalf of users via the
``POST /auth/token-exchange`` endpoint.

Contents
--------
- :mod:`.clients` -- :class:`~rhesis.backend.ee.api_clients.clients.AuthClient`
  ORM model and the constant-time authentication helper.
- :mod:`.schemas` -- Pydantic CRUD request/response schemas.
- :mod:`.router` -- org-scoped REST endpoints under
  ``/orgs/{org_id}/auth-clients``.
- :mod:`.audit` -- structured audit events for both client lifecycle
  (``AUTH_CLIENT_*``) and the token-exchange flow
  (``TOKEN_EXCHANGE_*``).

The runtime execution code for the token exchange itself lives under
:mod:`rhesis.backend.ee.sso.token_exchange` because it depends on SSO
primitives (``verify_oidc_jwt``, ``find_or_create_sso_user``); that
module imports :class:`~rhesis.backend.ee.api_clients.clients.AuthClient`
from here.
"""
