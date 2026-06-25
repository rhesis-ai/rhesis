"""RFC 8693 token-exchange execution code.

Lives under :mod:`rhesis.backend.ee.sso` (rather than under
:mod:`rhesis.backend.ee.api_clients`) because the runtime validator
depends on SSO primitives:

- :func:`rhesis.backend.ee.sso.oidc.verify_oidc_jwt` validates the
  subject token (signature, issuer, audience, alg-allowlist).
- :func:`rhesis.backend.ee.sso.user_utils.find_or_create_sso_user`
  resolves the user (org-scoped, with the same domain allowlist
  enforcement as the SSO callback).

The :class:`~rhesis.backend.ee.api_clients.clients.AuthClient` model
and the CRUD surface live in
:mod:`rhesis.backend.ee.api_clients` because they belong to the
"API Clients" feature; this module imports the model from there.

Both modules ultimately gate on :class:`FeatureName.API_CLIENTS`,
which has a ``runtime_check`` requiring SSO to be available -- making
the dependency explicit at the registry level rather than hidden
inside the exchange handler.
"""
