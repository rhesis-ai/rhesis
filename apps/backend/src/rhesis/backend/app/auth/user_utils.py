import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, NamedTuple, Optional, Tuple

import anyio
from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.constants import (
    UNAUTHORIZED_MESSAGE,
    AuthenticationMethod,
    AuthProviderType,
)
from rhesis.backend.app.auth.oauth_scope import capabilities_for_oauth_scope
from rhesis.backend.app.auth.principal import (
    REQUEST_STATE_API_TOKEN_PROJECT_ID,
    REQUEST_STATE_API_TOKEN_SCOPES,
    REQUEST_STATE_AUTH_KIND,
    AuthKind,
    Principal,
    resolve_principal_from_request,
)
from rhesis.backend.app.auth.token_utils import get_secret_key, verify_jwt_token
from rhesis.backend.app.auth.token_validation import validate_token
from rhesis.backend.app.config.settings import get_auth_settings
from rhesis.backend.app.crud import user as user_crud
from rhesis.backend.app.crud.token import get_token_by_value
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.provenance import ActorType, record_credential, record_delegation
from rhesis.backend.app.schemas import UserCreate

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from rhesis.backend.app.auth.providers.base import AuthUser

bearer_scheme = HTTPBearer(auto_error=False)


class RegistrationDisabledError(Exception):
    """A first login would create an account while AUTH_REGISTRATION_ENABLED is off."""


def mark_user_joined_if_needed(user: User, when: datetime | None = None) -> bool:
    """Stamp ``joined_at`` the first time a user becomes an active org member.

    A user is considered joined once they belong to an organization and have
    authenticated (or, for org founders, attached to the org they created).
    Returns True when ``joined_at`` was set on this call.
    """
    if user.organization_id is None or user.joined_at is not None:
        return False
    user.joined_at = when or datetime.now(timezone.utc)
    return True


def drop_credentials_of_unverified_account(db: Session, user: User) -> None:
    """Clear the password and revoke every token of a not-yet-verified account.

    Call this right before a login that proves ownership of the email (OAuth, SSO,
    magic link) marks the account verified. Until then anyone could have registered
    the address, so credentials set on it may belong to someone else.
    """
    from rhesis.backend.app.auth.refresh_token_utils import revoke_all_for_user
    from rhesis.backend.app.crud.token import revoke_user_tokens

    if user.is_email_verified:
        return

    had_password = user.password_hash is not None
    user.password_hash = None
    refresh_count = revoke_all_for_user(db, str(user.id))
    api_count = revoke_user_tokens(db, user.id)
    if had_password or refresh_count or api_count:
        logger.warning(
            "Verified login on unverified account %s: cleared password=%s, "
            "revoked %d refresh and %d API tokens",
            user.id,
            had_password,
            refresh_count,
            api_count,
        )


def _apply_login_to_existing_user(
    db: Session, user: User, auth_user: "AuthUser", when: datetime
) -> None:
    """Update a matched user from a provider login."""
    user.name = auth_user.name or user.name
    user.given_name = auth_user.given_name or user.given_name
    user.family_name = auth_user.family_name or user.family_name
    user.picture = auth_user.picture or user.picture
    user.provider_type = auth_user.provider_type
    user.external_provider_id = auth_user.external_id
    user.last_login_at = when
    # A password login proves nothing about the address; the other providers
    # only return addresses they have verified.
    if auth_user.provider_type != AuthProviderType.EMAIL:
        drop_credentials_of_unverified_account(db, user)
        user.is_email_verified = True
    mark_user_joined_if_needed(user, when=when)


def find_or_create_user_from_auth(db: Session, auth_user: "AuthUser") -> User:
    """
    Find existing user or create a new one from provider-agnostic AuthUser.

    Users are matched primarily by email, with provider info updated on each login.

    Args:
        db: Database session
        auth_user: AuthUser dataclass from any authentication provider

    Returns:
        User instance (existing or newly created)
    """
    from rhesis.backend.app.auth.disposable_email import screen_signup_email
    from rhesis.backend.app.auth.providers.base import AuthUser as AuthUserClass
    from rhesis.backend.app.utils.validation import validate_and_normalize_email

    if not isinstance(auth_user, AuthUserClass):
        raise TypeError(f"Expected AuthUser, got {type(auth_user)}")

    current_time = datetime.now(timezone.utc)

    # Normalize email for lookup (no DNS check on login)
    normalized_email = validate_and_normalize_email(auth_user.email)

    # First try to find user by email (this is our primary matching criteria)
    user = user_crud.get_user_by_email(db, normalized_email)

    if user:
        logger.info(f"Found existing user by email: {normalized_email}")
        _apply_login_to_existing_user(db, user, auth_user, current_time)
        return user

    # OAuth providers verify email ownership themselves; skip MX deliverability
    # check to avoid DNS failures in split-horizon environments where the
    # internal BIND9 zone only carries subdomain A records (no apex MX).
    normalized_email = validate_and_normalize_email(auth_user.email, check_deliverability=False)

    # Only reached when no user matched above, so this is a first login — existing
    # and invited accounts keep working when sign-up is off.
    if not get_auth_settings().registration_enabled:
        logger.info("Refused OAuth sign-up via %s: registration disabled", auth_user.provider_type)
        raise RegistrationDisabledError()
    screen_signup_email(normalized_email, source=f"oauth:{auth_user.provider_type}")

    # Create new user
    logger.info(f"Creating new user: {normalized_email} via {auth_user.provider_type}")
    user_data = UserCreate(
        email=normalized_email,
        name=auth_user.name,
        given_name=auth_user.given_name,
        family_name=auth_user.family_name,
        picture=auth_user.picture,
        provider_type=auth_user.provider_type,
        external_provider_id=auth_user.external_id,
        is_active=True,
        is_email_verified=True,  # OAuth/credentials auth confirms email ownership
        last_login_at=current_time,
    )
    user = user_crud.create_user(db, user_data)
    mark_user_joined_if_needed(user, when=current_time)

    return user


def find_or_create_magic_link_user(db: Session, email: str) -> Tuple[Optional[User], bool]:
    """Resolve the account a magic link goes to, creating it on first use.

    Returns ``(user, is_new_user)``, or ``(None, False)`` when no account should
    get a link. The caller answers the same either way, so the response never
    says whether an address has an account.

    Raises DisposableEmailError for a refused sign-up address.
    """
    from rhesis.backend.app.auth.constants import AuthProviderType
    from rhesis.backend.app.auth.disposable_email import screen_signup_email
    from rhesis.backend.app.utils.redact import redact_email

    user = user_crud.get_user_by_email(db, email)
    if user:
        return user, False

    # Invited users already have a row (POST /users/), so they never reach here.
    if not get_auth_settings().registration_enabled:
        logger.info("Refused magic-link sign-up for %s: registration disabled", redact_email(email))
        return None, False

    # Sign-up branch only, so existing accounts on a disposable domain keep working.
    screen_signup_email(email, source="magic_link")

    try:
        user = user_crud.create_user(
            db,
            UserCreate(
                email=email,
                provider_type=AuthProviderType.EMAIL,
                is_email_verified=False,
                is_active=True,
            ),
        )
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.warning("Failed to create user for magic link: %s", e)
        return None, False
    logger.info("New user created via magic link: %s", redact_email(email))
    return user, True


def _load_user_by_id(user_id) -> Optional[User]:
    """Look a user up in a short-lived session. Runs in a worker thread.

    ``get_db`` is read from this module at call time on purpose: the test
    fixtures monkeypatch ``user_utils.get_db`` to share the test transaction.
    """
    with get_db() as db:
        return user_crud.get_user_by_id(db, user_id)


class _ApiTokenAuth(NamedTuple):
    user: User
    project_id: Optional[str]
    scopes: Optional[frozenset]
    token_id: str
    token_hint: Optional[str]


def _load_user_for_api_token(token_value: str) -> Optional[_ApiTokenAuth]:
    """Validate an ``rh-*`` token and load its owner. Runs in a worker thread.

    The token's fields are read here, inside the session, so nothing lazy-loads
    after it closes.
    """
    with get_db() as db:
        is_valid, _ = validate_token(token_value, db=db)
        if not is_valid:
            return None
        token = get_token_by_value(db, token_value)
        if not token:
            return None
        user = user_crud.get_user_by_id(db, token.user_id)
        if not user:
            return None
        project_id = str(token.project_id) if token.project_id is not None else None
        scopes = getattr(token, "scopes", None)
        return _ApiTokenAuth(
            user=user,
            project_id=project_id,
            scopes=None if scopes is None else frozenset(scopes),
            token_id=str(token.id),
            token_hint=token.token_obfuscated,
        )


def _store_api_token_state(request, project_id: Optional[str], scopes: Optional[frozenset]):
    """Record what an API token carries so downstream dependencies can scope by it."""
    # get_project_context falls back to the token's project_id
    if project_id is not None:
        setattr(request.state, REQUEST_STATE_API_TOKEN_PROJECT_ID, project_id)
    # SP9: None means "inherit the owner's full access", so only narrow when set
    if scopes is not None:
        setattr(request.state, REQUEST_STATE_API_TOKEN_SCOPES, scopes)
    # Always a token, even when it carries no scopes and no project_id
    setattr(request.state, REQUEST_STATE_AUTH_KIND, AuthKind.TOKEN)


async def get_current_user(request: Request) -> Optional[User]:
    """
    Get current user from session using org-aware database session.

    Uses a simple session to get user and organization_id, then returns the user
    only if they have an organization_id. The actual database operations that
    need tenant context should pass organization_id and user_id directly to CRUD operations.

    The lookup runs in the threadpool: this dependency sits on every request, and a
    psycopg call here would block the event loop for the whole worker.
    """
    if "user_id" not in request.session:
        return None

    user_id = request.session.get("user_id")
    user = await anyio.to_thread.run_sync(_load_user_by_id, user_id)

    # User must have an organization_id to proceed
    if not user or not user.organization_id:
        return None

    return user


async def get_user_from_jwt(token: str, secret_key: str) -> Optional[User]:
    """
    Get user from JWT token using simple database session.

    Uses a simple session to get user. The caller is responsible for checking
    whether the user needs an organization_id (via without_context parameter).
    """
    try:
        payload = verify_jwt_token(token, secret_key)
        user_info = payload.get("user", {})
        user_id = user_info.get("id")

        if user_id:
            return await anyio.to_thread.run_sync(_load_user_by_id, user_id)

    except Exception:
        return None

    return None


async def get_authenticated_user_with_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    secret_key: Optional[str] = None,
    session_only: bool = False,
    without_context: bool = False,
) -> Optional[User]:
    """
    Get authenticated user without database session dependency.

    No longer sets tenant context - pass organization_id and user_id directly to CRUD operations.
    """
    # Try session auth first
    user = await get_current_user(request)
    if user:
        if not user.organization_id and not without_context:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not associated with an organization",
            )
        # Set user on request state for middleware access (e.g., telemetry)
        request.state.user = user
        return user

    # If session_only or no credentials, return None
    if session_only or not credentials:
        return None

    # Try bearer token
    if credentials.credentials.startswith("rh-"):
        resolved = await anyio.to_thread.run_sync(_load_user_for_api_token, credentials.credentials)
        if resolved:
            user = resolved.user
            _store_api_token_state(request, resolved.project_id, resolved.scopes)
            record_credential(request, ActorType.API_TOKEN, resolved.token_id, resolved.token_hint)
            if not without_context and not user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User is not associated with an organization",
                )
            # Tenant context is passed directly to CRUD operations when needed
            request.state.user = user
            return user

    # Try JWT token if secret_key is provided
    if secret_key and credentials and not credentials.credentials.startswith("rh-"):
        jwt_user = await get_user_from_jwt(credentials.credentials, secret_key)
        if jwt_user:
            if not jwt_user.organization_id and not without_context:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User is not associated with an organization",
                )

            # ``azp`` marks a token-exchange-issued JWT; UI/SSO JWTs never
            # carry it, so gating on it leaves their AuthKind.SESSION
            # classification untouched. Storing the ``project`` and
            # ``scope`` claims on request.state is what lets
            # get_project_context and the EE RBAC provider treat this like
            # a project-scoped, scope-restricted rh-* token (membership and
            # scope both re-checked per request). The re-decode is a cheap
            # HMAC verify -- get_user_from_jwt discards the payload.
            #
            # Authentication already succeeded above, so this only reads
            # claims for scoping and must not be able to fail the request:
            # on any decode problem we fall through with no project/scope
            # binding, which is fail-closed (fewer rows/permissions visible,
            # never more).
            try:
                payload = verify_jwt_token(credentials.credentials, secret_key)
            except Exception:
                logger.debug("Could not re-read JWT claims for project scope", exc_info=True)
                payload = {}
            if payload.get("azp"):
                setattr(request.state, REQUEST_STATE_AUTH_KIND, AuthKind.TOKEN)
                # azp is the EE API client's client_id.
                record_credential(request, ActorType.API_CLIENT, str(payload["azp"]))
                project_claim = payload.get("project")
                if project_claim:
                    setattr(request.state, REQUEST_STATE_API_TOKEN_PROJECT_ID, str(project_claim))
                # None means "full access" (Principal.scopes' own sentinel);
                # only set request.state when the claim actually narrows it,
                # so an unset field keeps meaning "inherit owner's access".
                scope_capabilities = capabilities_for_oauth_scope(payload.get("scope"))
                if scope_capabilities is not None:
                    setattr(request.state, REQUEST_STATE_API_TOKEN_SCOPES, scope_capabilities)
            if payload.get("type") == "service_delegation":
                record_delegation(request, payload.get("target_service"))

            request.state.user = jwt_user
            return jwt_user

    return None


async def get_authenticated_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    secret_key: str = Depends(get_secret_key),
) -> Tuple[Optional[User], Optional[str]]:
    """Get authenticated user and authentication method without database session dependency"""
    user = await get_authenticated_user_with_context(request, credentials, secret_key)
    if not user:
        return None, None

    # Determine authentication method
    if "user_id" in request.session:
        return user, AuthenticationMethod.SESSION
    elif credentials:
        if credentials.credentials.startswith("rh-"):
            return user, AuthenticationMethod.BEARER
        else:
            return user, AuthenticationMethod.JWT

    return None, None


async def require_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    """Require authenticated user via session only without database session dependency"""
    user = await get_authenticated_user_with_context(request, credentials, session_only=True)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_MESSAGE)
    return user


async def require_current_user_or_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    secret_key: str = Depends(get_secret_key),
) -> User:
    """Require authenticated user via session or token without database session dependency"""
    user = await get_authenticated_user_with_context(request, credentials, secret_key)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def require_current_user_or_token_without_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    secret_key: str = Depends(get_secret_key),
) -> User:
    """Require authenticated user via session or token, without organization context."""
    user = await get_authenticated_user_with_context(
        request, credentials, secret_key, without_context=True
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def authenticate_websocket(websocket: WebSocket) -> tuple["User", Principal]:
    """
    Authenticate WebSocket connection using Bearer token.

    Thin wrapper around get_authenticated_user_with_context that extracts
    credentials from WebSocket headers. Requires organization context.
    Does not accept the connection - that's the endpoint's responsibility.

    Args:
        websocket: The WebSocket connection to authenticate

    Returns:
        Tuple of (User, Principal). The principal carries the token's scopes
        and project, so permission checks on the connection honour them.
        ``principal.token_project_id`` is also an alternate authorization path:
        a token scoped to a project can connect the connector even if its owner
        lacks a ProjectMembership row (e.g. tokens created before the
        membership migration ran).

    Raises:
        HTTPException: If authentication fails or user lacks organization
    """
    # Extract and validate Authorization header
    auth_header = websocket.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    # Create credentials object
    token_value = auth_header.replace("Bearer ", "")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_value)

    # Create minimal mock request (websockets don't have full Request object)
    class MockRequest:
        def __init__(self):
            self.session = {}
            self.state = type("obj", (object,), {})()

    mock_request = MockRequest()

    # Use existing authentication logic (supports both rh- tokens and JWT)
    user = await get_authenticated_user_with_context(
        request=mock_request,
        credentials=credentials,
        secret_key=get_secret_key(),
        without_context=False,  # Require organization
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed"
        )

    # get_authenticated_user_with_context stored the token's scopes and project
    # on the mock request state.
    return user, resolve_principal_from_request(user, mock_request)
