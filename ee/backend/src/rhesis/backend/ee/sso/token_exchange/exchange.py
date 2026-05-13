"""Pure orchestrator for the RFC 8693 token-exchange grant.

No FastAPI imports. The router calls :func:`run_token_exchange` with
the parsed request payload and either returns the success body or
maps :class:`TokenExchangeError` to an RFC 6749 response. Splitting
parsing (router) from validation + minting (here) lets the orchestrator
be unit-tested without a FastAPI test client.

Order of operations is load-bearing
-----------------------------------
Each step gates the next; reordering changes the timing-oracle
surface area or skips a security check entirely. The order is:

1. Parse + validate request shape (including ``audience``).
2. Resolve the organization by slug from the ``audience`` parameter.
   Reject if missing / inactive / no SSOConfig. The org must be
   resolved BEFORE client authentication because ``auth_client.client_id``
   is unique only per-organization; without the org binding,
   ``authenticate_client`` could not distinguish two tenants that both
   chose the same client_id and would lock one of them out at random.
3. Authenticate the calling client against ``(org_id, client_id)``
   (constant time, dummy hash on miss). On any failure ->
   ``invalid_client``, single log shape.
4. Validate the subject token against the org's SSOConfig issuer URL.
5. Subject-token client binding: ``azp`` claim must match the
   AuthClient's ``expected_subject_azp`` (S1 -- the only mitigation
   against attacker A3, a sibling integration replaying its valid
   Keycloak token here).
6. Subject-token replay protection (S9): claim the subject token's
   ``jti`` in Redis with TTL = min(remaining_lifetime, 600). Reuse ->
   ``invalid_grant``. Redis unavailable -> log + proceed (matches the
   existing ``auth_code`` policy: fail-open on infra outage,
   fail-closed on confirmed replay).
7. Resolve the user via the same path as the SSO callback (domain
   allowlist, cross-org collision, auto-provision gate, is_active).
8. Mint the Rhesis JWT with ``azp`` / ``aud`` / ``scope`` / ``jti`` /
   ``epoch`` claims via the extended ``create_session_token``.
9. Conditionally mint a refresh token (only when ``offline_access`` is
   in the resolved scope), persisting ``client_id`` and ``scope`` so
   the refresh path can preserve them on rotation.
10. Emit success audit event and return the RFC 8693 payload.

Error contract
--------------
Every rejection raises :class:`TokenExchangeError` with one of the
RFC 6749 error codes (``invalid_request``, ``invalid_client``,
``invalid_grant``, ``invalid_target``, ``invalid_scope``,
``unauthorized_client``, ``temporarily_unavailable``). The
``reason_code`` carried alongside is logged into the audit event but
is **never** included in the HTTP response body -- bodies are
minimal so they cannot serve as oracles.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import List, Mapping, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.auth.constants import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from rhesis.backend.app.auth.refresh_token_utils import create_refresh_token
from rhesis.backend.app.auth.token_utils import (
    RHESIS_TOKEN_AUDIENCE,
    create_session_token,
)
from rhesis.backend.app.auth.used_token_store import (
    TokenStoreUnavailableError,
    claim_token_jti,
)
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.user import User
from rhesis.backend.ee.api_clients.audit import (
    TokenExchangeEvent,
    token_exchange_audit_log,
)
from rhesis.backend.ee.api_clients.clients import authenticate_client
from rhesis.backend.ee.sso.oidc import SubjectTokenError, verify_oidc_jwt
from rhesis.backend.ee.sso.schemas import SSOConfig
from rhesis.backend.ee.sso.token_exchange.schemas import (
    GRANT_TYPE_TOKEN_EXCHANGE,
    TOKEN_TYPE_ACCESS_TOKEN,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


#: Strict regex for the ``audience`` form parameter. Length cap matches
#: the ``Organization.slug`` ``String(50)`` column.
_AUDIENCE_RE = re.compile(r"^rhesis:org:[a-z0-9-]{1,50}$")

#: The single permitted scope separator. Tabs and other Unicode
#: whitespace are rejected because mixed separators are an easy way
#: to smuggle a forbidden scope past a naive splitter.
_SCOPE_SEPARATOR = " "

#: ``offline_access`` triggers a refresh-token issuance. Pulled out
#: as a constant so the orchestrator and the schemas share the spelling.
SCOPE_OFFLINE_ACCESS = "offline_access"


@dataclass(frozen=True)
class TokenExchangeRequest:
    """Validated, normalised inbound request the router hands to the orchestrator.

    Lives as a dataclass (not a Pydantic model) because it is built by
    the router after manual form parsing and never crosses an HTTP
    boundary. The router enforces single-vs-multi rules on
    ``audience`` and the dual-credential check; reaching this struct
    means those structural checks have passed.
    """

    grant_type: str
    subject_token: str
    subject_token_type: str
    audience: str
    requested_token_type: Optional[str]
    scope: Optional[str]
    client_id: str
    client_secret: str
    # Best-effort context for the audit trail; ``None`` is acceptable.
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass(frozen=True)
class TokenExchangeSuccess:
    """Internal representation of a successful exchange.

    The router maps this to
    :class:`~rhesis.backend.ee.sso.token_exchange.schemas.TokenExchangeSuccessResponse`
    so the orchestrator stays Pydantic-free.
    """

    access_token: str
    expires_in: int
    scope: str
    refresh_token: Optional[str]
    refresh_expires_in: Optional[int]


class TokenExchangeError(Exception):
    """Raised by :func:`run_token_exchange` on every rejection.

    ``error`` is one of the RFC 6749 §5.2 codes; ``reason_code`` is
    a stable internal label that the audit log captures (and that the
    test suite asserts against). ``http_status`` lets the router pick
    the right HTTP status without re-deriving it from the error code.
    """

    def __init__(
        self,
        error: str,
        reason_code: str,
        *,
        http_status: int = 400,
    ):
        self.error = error
        self.reason_code = reason_code
        self.http_status = http_status
        super().__init__(f"{error}: {reason_code}")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def run_token_exchange(
    db: Session,
    payload: TokenExchangeRequest,
    *,
    sso_config_loader=None,
) -> TokenExchangeSuccess:
    """Run the validated token-exchange flow end-to-end.

    *sso_config_loader* is an optional injection point (used by tests)
    that takes an :class:`Organization` and returns an
    :class:`SSOConfig`-or-None. The default loader matches the SSO
    router's ``_get_sso_config`` semantics: it parses the org's JSON
    column and decrypts ``client_secret``.

    Returns :class:`TokenExchangeSuccess` on success; raises
    :class:`TokenExchangeError` on every rejection. The function emits
    exactly one audit event (success or denied) at the end of every
    code path so the audit log has 1:1 correspondence with handled
    requests.
    """

    # Default to the SSO router's loader. Imported lazily so unit
    # tests can substitute their own loader without dragging the
    # SSO router (and its FastAPI deps) into the test process.
    if sso_config_loader is None:
        from rhesis.backend.ee.sso.router import (
            _get_sso_config as sso_config_loader,  # type: ignore[import-not-found]
        )

    # ---- Step 1: shape validation ----------------------------------------
    _check_request_shape(payload)
    requested_scopes = _split_scope_string(payload.scope)

    # Audit-context helpers used by the deny-and-raise path. Assemble
    # them up-front so we can pass coherent context whichever step
    # rejects.
    audit_ip = payload.source_ip
    audit_ua = payload.user_agent

    def _deny(error: str, reason_code: str, *, http: int = 400, **kwargs):
        # Annotated as -> NoReturn semantics; the type checker can't
        # see that, so call sites that need narrowing afterwards add
        # an explicit assert.
        token_exchange_audit_log(
            TokenExchangeEvent.DENIED,
            org_id=kwargs.get("org_id"),
            client_id=kwargs.get("client_id", payload.client_id),
            iss=kwargs.get("iss"),
            subject_token_jti=kwargs.get("jti"),
            email=kwargs.get("email"),
            scope=kwargs.get("scope"),
            reason_code=reason_code,
            ip=audit_ip,
            user_agent=audit_ua,
        )
        raise TokenExchangeError(error, reason_code, http_status=http)

    # ---- Step 2: org resolution ------------------------------------------
    # Resolve the org BEFORE authenticating the client so the
    # ``(organization_id, client_id)`` lookup in step 3 hits the right
    # row even when two tenants share a client_id. Doing client auth
    # first would scope the lookup to ``client_id`` alone, return
    # whichever row sorts first, and lock the other tenant out.
    slug = _audience_to_slug(payload.audience)
    if slug is None:
        _deny("invalid_target", "audience_malformed")

    org = (
        db.query(Organization).filter(Organization.slug == slug).first()
        if slug
        else None
    )
    if org is None:
        _deny("invalid_target", "org_not_found")
    assert org is not None
    if not org.is_active:
        _deny("invalid_target", "org_inactive", org_id=str(org.id))
    if org.sso_config is None:
        _deny("invalid_target", "org_no_sso_config", org_id=str(org.id))

    # ---- Step 3: client authentication (org-scoped) ----------------------
    auth_client = authenticate_client(
        db, org.id, payload.client_id, payload.client_secret
    )
    if auth_client is None:
        # invalid_client per RFC 6749 §5.2; HTTP 401 because the
        # request lacked valid client credentials. Note that the
        # uniform invalid_client response covers both "no such client
        # in this org" and "wrong secret" -- the org binding does NOT
        # turn into a tenant-existence oracle because the per-IP rate
        # limit applies before this code path runs.
        _deny(
            "invalid_client",
            "client_auth_failed",
            http=401,
            org_id=str(org.id),
        )
    assert auth_client is not None  # narrow for the type checker

    # ---- Step 4: subject token validation --------------------------------
    sso_config: Optional[SSOConfig] = sso_config_loader(org)
    if sso_config is None:
        _deny("invalid_target", "sso_config_unparseable", org_id=str(org.id))
    assert sso_config is not None

    from rhesis.backend.ee.sso.http_client import SSRFError
    from rhesis.backend.ee.sso.oidc import OIDCProvider

    provider = OIDCProvider(sso_config)
    try:
        jwks = await provider._get_jwks()
    except SSRFError:
        _deny(
            "temporarily_unavailable",
            "jwks_ssrf_blocked",
            http=503,
            org_id=str(org.id),
        )
    except Exception as exc:
        logger.warning(
            "JWKS fetch failed for %s: %s",
            sso_config.issuer_url,
            type(exc).__name__,
        )
        _deny(
            "temporarily_unavailable",
            "jwks_fetch_failed",
            http=503,
            org_id=str(org.id),
        )

    # ``expected_subject_audience`` is REQUIRED at create time, but a
    # row created before that requirement existed may have NULL. Fail
    # closed here rather than silently disabling the audience check by
    # passing ``None`` to verify_oidc_jwt -- a missing audience binding
    # is the difference between A3 being "exploitable" and "impossible
    # in practice" for IdPs that share azp across siblings (Keycloak
    # service-account flows being the canonical example).
    audience_claim = auth_client.expected_subject_audience
    if not audience_claim:
        _deny(
            "invalid_target",
            "client_missing_audience_binding",
            org_id=str(org.id),
            iss=sso_config.issuer_url,
        )
        # _deny raises; this assert just narrows for the type checker.
        assert audience_claim is not None

    # JWKS rotation: if the IdP rotated keys after our cache filled
    # the first decode raises ``no_matching_key``. Force-refresh once
    # and retry. ``_get_jwks(force_refresh=True)`` enforces a per-issuer
    # cooldown so a stream of bogus tokens cannot DoS the JWKS endpoint.
    try:
        claims = verify_oidc_jwt(
            payload.subject_token,
            issuer=sso_config.issuer_url,
            jwks=jwks,
            audience=audience_claim,
        )
    except SubjectTokenError as exc:
        if exc.reason_code == "no_matching_key":
            try:
                jwks = await provider._get_jwks(force_refresh=True)
            except Exception:
                _deny(
                    "temporarily_unavailable",
                    "jwks_refresh_failed",
                    http=503,
                    org_id=str(org.id),
                    iss=sso_config.issuer_url,
                )
            try:
                claims = verify_oidc_jwt(
                    payload.subject_token,
                    issuer=sso_config.issuer_url,
                    jwks=jwks,
                    audience=audience_claim,
                )
            except SubjectTokenError as exc2:
                _deny(
                    "invalid_grant",
                    f"subject_{exc2.reason_code}",
                    org_id=str(org.id),
                    iss=sso_config.issuer_url,
                )
        else:
            _deny(
                "invalid_grant",
                f"subject_{exc.reason_code}",
                org_id=str(org.id),
                iss=sso_config.issuer_url,
            )

    # ---- Step 5: subject-token client binding (S1) -----------------------
    azp = claims.get("azp")
    if not azp:
        # Per OIDC core §2 azp is REQUIRED whenever an ID token has
        # multiple audiences or the azp differs from the aud. Keycloak
        # emits it on access tokens; absence is unsupported (we
        # document this in the integration guide).
        _deny(
            "invalid_grant",
            "subject_missing_azp",
            org_id=str(org.id),
            iss=sso_config.issuer_url,
            jti=claims.get("jti"),
        )
    if azp != auth_client.expected_subject_azp:
        _deny(
            "invalid_grant",
            "subject_azp_mismatch",
            org_id=str(org.id),
            iss=sso_config.issuer_url,
            jti=claims.get("jti"),
        )

    # ---- Step 6: subject-token replay protection (S9) --------------------
    subject_jti = claims.get("jti")
    if subject_jti:
        ttl_seconds = _ttl_until_expiry(claims, max_seconds=600)
        try:
            # Namespace by issuer URL so two IdPs that legitimately
            # mint the same jti (the spec only RECOMMENDS uniqueness)
            # do not DoS each other through a shared replay-set.
            first_use = await claim_token_jti(
                subject_jti,
                ttl_seconds,
                namespace=sso_config.issuer_url,
            )
        except TokenStoreUnavailableError:
            # Fail-open on infra outage, matching the auth_code policy.
            # Without this we'd take down all integrators every time
            # Redis flapped. We still fail-closed on a confirmed replay
            # below.
            logger.warning(
                "Redis unavailable; subject_token replay check skipped (jti=%s)",
                subject_jti,
            )
            first_use = True
        if not first_use:
            _deny(
                "invalid_grant",
                "subject_token_replay",
                org_id=str(org.id),
                iss=sso_config.issuer_url,
                jti=subject_jti,
            )

    # ---- Step 7: user resolution -----------------------------------------
    user = _resolve_user(db, claims, org, sso_config, deny=_deny)
    if not user.is_active:
        _deny(
            "invalid_grant",
            "user_inactive",
            org_id=str(org.id),
            iss=sso_config.issuer_url,
            jti=subject_jti,
            email=user.email,
        )

    # ---- Validate scope against client's allowed_scopes (S7) -------------
    allowed = set(auth_client.allowed_scopes or [])
    if requested_scopes is None:
        # Caller omitted scope -> default. ``default_scope`` is
        # validated against allowed_scopes at create time so this is
        # safe to use without re-checking.
        resolved_scopes: List[str] = [auth_client.default_scope]
    else:
        for s in requested_scopes:
            if s not in allowed:
                _deny(
                    "invalid_scope",
                    "scope_not_allowed",
                    org_id=str(org.id),
                    iss=sso_config.issuer_url,
                    jti=subject_jti,
                    email=user.email,
                    scope=" ".join(requested_scopes),
                )
        resolved_scopes = requested_scopes
    resolved_scope_str = " ".join(resolved_scopes)

    # ---- Step 8: mint Rhesis JWT -----------------------------------------
    # ``offline_access`` is an OIDC convention for "I want a refresh
    # token alongside the access token"; it does not grant authority
    # on the access token itself. Stripping it from the JWT scope
    # claim means a future per-route scope check cannot accidentally
    # treat ``offline_access`` as an authority. The refresh row still
    # carries it (so the refresh path knows the chain was minted with
    # offline intent), and the response body still reports it back to
    # the caller for parity with the requested scope.
    access_scopes = [s for s in resolved_scopes if s != SCOPE_OFFLINE_ACCESS]
    access_scope_str = " ".join(access_scopes)
    issued_jti = str(uuid.uuid4())
    access_token = create_session_token(
        user,
        azp=auth_client.client_id,
        aud=RHESIS_TOKEN_AUDIENCE,
        scope=access_scope_str,
        jti=issued_jti,
        epoch=auth_client.token_epoch,
    )

    # ---- Step 9: refresh token (only when offline_access requested) ------
    refresh_token: Optional[str] = None
    refresh_expires_in: Optional[int] = None
    if SCOPE_OFFLINE_ACCESS in resolved_scopes:
        refresh_token = create_refresh_token(
            db,
            user_id=str(user.id),
            client_id=auth_client.client_id,
            scope=resolved_scope_str,
        )
        db.commit()
        refresh_expires_in = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600

    # ---- Step 10: success audit + return ---------------------------------
    token_exchange_audit_log(
        TokenExchangeEvent.SUCCESS,
        org_id=str(org.id),
        client_id=auth_client.client_id,
        iss=sso_config.issuer_url,
        subject_token_jti=subject_jti,
        email=user.email,
        scope=resolved_scope_str,
        ip=audit_ip,
        user_agent=audit_ua,
    )

    return TokenExchangeSuccess(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        scope=resolved_scope_str,
        refresh_token=refresh_token,
        refresh_expires_in=refresh_expires_in,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_request_shape(payload: TokenExchangeRequest) -> None:
    """Reject requests with the wrong constants up front (S7).

    Errors here are ``invalid_request`` per RFC 6749. The router
    catches and converts them to the response body; we raise
    :class:`TokenExchangeError` with no audit emission because the
    request never authenticated a client (no ``client_id`` to
    correlate the audit event to with confidence).
    """
    if payload.grant_type != GRANT_TYPE_TOKEN_EXCHANGE:
        raise TokenExchangeError("unsupported_grant_type", "grant_type_unsupported")
    if payload.subject_token_type != TOKEN_TYPE_ACCESS_TOKEN:
        raise TokenExchangeError("invalid_request", "subject_token_type_unsupported")
    if payload.requested_token_type is not None and (
        payload.requested_token_type != TOKEN_TYPE_ACCESS_TOKEN
    ):
        raise TokenExchangeError("invalid_request", "requested_token_type_unsupported")
    if not payload.subject_token:
        raise TokenExchangeError("invalid_request", "subject_token_missing")
    if not payload.client_id or not payload.client_secret:
        raise TokenExchangeError("invalid_request", "client_credentials_missing")
    if not _AUDIENCE_RE.match(payload.audience or ""):
        raise TokenExchangeError("invalid_request", "audience_malformed")


def _audience_to_slug(audience: str) -> Optional[str]:
    """Strip the ``rhesis:org:`` prefix; return ``None`` on shape violation."""
    if not _AUDIENCE_RE.match(audience or ""):
        return None
    return audience.split(":", 2)[2]


def _split_scope_string(scope: Optional[str]) -> Optional[List[str]]:
    """Split *scope* on a single ASCII space, dedupe, preserve order.

    Returns ``None`` when the caller did not supply a scope (so the
    orchestrator knows to fall back to ``default_scope``). Returns
    a non-empty list otherwise. Anything containing tabs or other
    Unicode whitespace is rejected because mixed separators are a
    classic way to smuggle a forbidden scope past a naive splitter
    (e.g. ``"read\toffline_access"`` registers as one token under
    ``str.split()`` but two under ``str.split(" ")``; we accept only
    the latter form to keep behaviour unambiguous).
    """
    if scope is None:
        return None
    if not scope.strip():
        raise TokenExchangeError("invalid_request", "scope_empty")
    if any(ch.isspace() and ch != _SCOPE_SEPARATOR for ch in scope):
        raise TokenExchangeError("invalid_request", "scope_invalid_separator")
    seen: dict[str, None] = {}
    for s in scope.split(_SCOPE_SEPARATOR):
        if not s:
            continue
        seen[s] = None
    if not seen:
        raise TokenExchangeError("invalid_request", "scope_empty")
    return list(seen.keys())


# ---- User resolver ---------------------------------------------------------


def _resolve_user(
    db: Session,
    claims: Mapping[str, object],
    org: Organization,
    sso_config: SSOConfig,
    *,
    deny,
) -> User:
    """Run the same path the SSO callback takes to find or create the user.

    Wraps :func:`find_or_create_sso_user` so the orchestrator does not
    grow a parallel implementation -- a parallel impl would mean two
    domain-allowlist enforcement points, two cross-org collision
    checks, and two audit trails.
    """
    from rhesis.backend.app.auth.constants import AuthProviderType
    from rhesis.backend.app.auth.providers.base import AuthUser
    from rhesis.backend.ee.sso.user_utils import (
        SSOLoginError,
        find_or_create_sso_user,
    )

    email = claims.get("email")
    if not email:
        deny(
            "invalid_grant",
            "subject_missing_email",
            org_id=str(org.id),
            iss=sso_config.issuer_url,
            jti=claims.get("jti"),
        )

    auth_user = AuthUser(
        provider_type=AuthProviderType.OIDC,
        external_id=str(claims.get("sub") or ""),
        email=str(email),
        name=claims.get("name"),
        given_name=claims.get("given_name"),
        family_name=claims.get("family_name"),
        picture=claims.get("picture"),
        raw_data={k: v for k, v in claims.items() if k not in ("at_hash", "c_hash")},
    )
    try:
        return find_or_create_sso_user(db, auth_user, org, sso_config)
    except SSOLoginError as exc:
        deny(
            "invalid_grant",
            f"user_{exc.reason_code}",
            org_id=str(org.id),
            iss=sso_config.issuer_url,
            jti=claims.get("jti"),
            email=str(email),
        )


# ---- Replay TTL ------------------------------------------------------------


def _ttl_until_expiry(claims: Mapping[str, object], *, max_seconds: int) -> int:
    """Return ``min(remaining_lifetime, max_seconds)`` as a positive int.

    The Redis ``SET NX EX`` primitive needs a positive TTL. We cap the
    TTL at *max_seconds* because:

    - Keycloak access tokens often live 5-15 minutes; longer TTLs add
      no protection (the token expires anyway) but use Redis space.
    - A subject token with a very long ``exp`` is unusual and could
      itself be a sign of misconfiguration.

    On a token that has already expired we return ``1``; the JWT
    validator will have rejected it before we get here, so this is
    purely defensive.
    """
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        return max_seconds
    remaining = int(exp - time.time())
    if remaining <= 0:
        return 1
    return min(remaining, max_seconds)


__all__ = [
    "SCOPE_OFFLINE_ACCESS",
    "TokenExchangeError",
    "TokenExchangeRequest",
    "TokenExchangeSuccess",
    "run_token_exchange",
]
