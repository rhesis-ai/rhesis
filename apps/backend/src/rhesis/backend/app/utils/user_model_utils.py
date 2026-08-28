"""
User Model Utilities

Helper functions for managing user-configured AI models (LLMs and embeddings)
for different purposes (generation, evaluation, embedding, etc.)
"""

import logging
import os
from typing import Literal, Optional, Union
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.config.settings import (
    get_application_settings,
    get_model_settings,
    get_rhesis_settings,
)
from rhesis.backend.app.crud import model as model_crud
from rhesis.backend.app.crud import user as user_crud
from rhesis.backend.app.models.model import Model
from rhesis.backend.app.models.organization import Organization
from rhesis.backend.app.models.user import User
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.quota.enforcement import enforce_quota
from rhesis.backend.app.services.platform_key import get_platform_api_key
from rhesis.backend.app.utils.model_errors import ModelConfigurationError
from rhesis.backend.app.utils.usage_tracking import stamp_usage_provenance
from rhesis.sdk.models.base import BaseEmbedder, BaseLLM
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger(__name__)


# The language-model purposes. Embeddings are not one of them: an embedder is a
# different SDK type, accrues no usage and takes no quota gate, so it has its
# own entry point in :func:`resolve_embedder` rather than a fourth purpose here.
MODEL_PURPOSES = ("generation", "evaluation", "execution")

ModelPurpose = Literal["generation", "evaluation", "execution"]

# What a caller can name the person the model is resolved for: the User itself,
# or just their id when that is all the call site has (a Celery payload, a test
# config row). The id form resolves leniently -- see _resolve_by_user_id.
Principal = Union[User, str, UUID]


def _default_model(purpose: str) -> str:
    """The system default for *purpose*, from this deployment's DEFAULT_*_MODEL settings."""
    return getattr(get_model_settings(), f"{purpose}_model")


def _check_purpose(purpose: str) -> None:
    if purpose not in MODEL_PURPOSES:
        raise ValueError(
            f"Unknown model purpose {purpose!r}; expected one of {', '.join(MODEL_PURPOSES)}"
        )


def resolve_model(
    db: Session,
    principal: Principal,
    purpose: ModelPurpose,
    override: Optional[str] = None,
) -> BaseLLM:
    """
    Resolve the language model to use for *purpose*, for *principal*.

    The single entry point for language-model resolution in the backend.
    Precedence is always the same: an explicit *override* model id, then the
    principal's configured default for that purpose, then this deployment's
    ``DEFAULT_<PURPOSE>_MODEL`` setting.

    Args:
        db: Database session
        principal: The ``User`` to resolve for, or their id when that is all
            the call site has. Passing an id resolves leniently:
            a missing user or a failure anywhere in resolution falls back to
            the system default instead of raising, because the call sites that
            only have an id (batch execution, telemetry evaluation) run outside
            a request and have no user to show an error to.
        purpose: One of ``MODEL_PURPOSES`` -- what the model is for.
        override: Optional model UUID that wins over the principal's default,
            for per-request model selection.

    Returns:
        A ready ``BaseLLM``, already stamped for usage accrual. Never a bare
        provider string: a caller that cannot get a working model gets an
        exception, not a value it has to finish building itself.

    Raises:
        ~rhesis.backend.app.utils.model_errors.ModelConfigurationError: the
            principal's configured model cannot be built, with a message
            saying what to fix in the Models settings.
        ~rhesis.backend.app.quota.enforcement.QuotaExceededError: the org has
            reached its enforceable ceiling for ``MODEL_TOKENS``.

    Security:
        The lookup is always filtered by the principal's own ``organization_id``,
        which is never accepted as a parameter -- an override id from an
        untrusted request body therefore cannot reach another org's model.
    """
    _check_purpose(purpose)
    if isinstance(principal, (str, UUID)):
        return _resolve_by_user_id(db, str(principal), purpose, override)
    return _resolve_for_user(db, principal, purpose, override)


def resolve_embedder(
    db: Session,
    principal: Principal,
    override: Optional[str] = None,
    *,
    dimensions: Optional[int] = None,
) -> BaseEmbedder:
    """
    Resolve the embedder to use for *principal*.

    The embedding counterpart to :func:`resolve_model`, separate because an
    embedder is a different SDK type that emits no usage: there is nothing to
    stamp, and no MODEL_TOKENS gate to run before building one.

    Args:
        db: Database session
        principal: As for :func:`resolve_model`.
        override: Optional model UUID that wins over the principal's default.
        dimensions: Vector width to request, applied only when this builds the
            *system default* embedder. A ``Model`` row the org configured is
            built from its own stored settings and ignores this, which is the
            behaviour the explorer and the embedding job already relied on.

    Returns:
        A ready ``BaseEmbedder``. Never a bare provider string.
    """
    if isinstance(principal, (str, UUID)):
        return _resolve_by_user_id(db, str(principal), "embedding", override, dimensions)
    return _resolve_for_user(db, principal, "embedding", override, dimensions)


def _resolve_for_user(
    db: Session,
    user: User,
    purpose: str,
    override: Optional[str],
    dimensions: Optional[int] = None,
) -> Union[BaseLLM, BaseEmbedder]:
    """Resolve for a real ``User``: override, then their setting, then the default."""
    default_model = _default_model(purpose)
    embedding = purpose == "embedding"

    if override:
        logger.debug("Using per-request %s model override: model_id=%s", purpose, override)
        model_id = override
    else:
        model_id = getattr(user.settings.models, purpose).model_id

    if not model_id:
        if embedding:
            return _ensure_embedder(default_model, dimensions)
        # Guard, not str(user.organization_id) unconditionally: for an orgless
        # user that produces the literal string "None", not an actual null --
        # exactly the bug peqy flagged on #2355 for this same branch.
        org_id = str(user.organization_id) if user.organization_id else None
        return resolve_default_hosted_model(default_model, db, org_id)

    if embedding:
        return _fetch_and_configure_embedder(
            db=db,
            model_id=str(model_id),
            organization_id=str(user.organization_id),
            default_model=default_model,
            dimensions=dimensions,
        )

    return _fetch_and_configure_model(
        db=db,
        model_id=str(model_id),
        organization_id=str(user.organization_id),
        default_model=default_model,
        user=user,
    )


def _resolve_by_user_id(
    db: Session,
    user_id: str,
    purpose: str,
    override: Optional[str],
    dimensions: Optional[int] = None,
) -> Union[BaseLLM, BaseEmbedder]:
    """Resolve from a user id, degrading to the system default rather than raising.

    Every caller here is a background path with no user-facing error channel,
    so a bad id or a broken model configuration must not take the whole job
    down -- it runs on the default and logs why.
    """
    default_model = _default_model(purpose)
    try:
        user = user_crud.get_user_by_id(db, user_id)
        if user:
            return _resolve_for_user(db, user, purpose, override, dimensions)
        logger.warning(
            f"[MODEL_SELECTION] User {user_id} not found, using default: {default_model}"
        )
    except Exception as e:
        logger.warning(
            f"[MODEL_SELECTION] Error fetching user model: {str(e)}, using default: {default_model}"
        )

    # Built without the MODEL_TOKENS gate, because the org to gate on is the
    # one we just failed to resolve. That matches what happened before: the
    # bare default string was handed on and constructed downstream, past
    # every gate. Anything raising here has no fallback left and propagates.
    if purpose == "embedding":
        return _ensure_embedder(default_model, dimensions)
    return ensure_language_model(default_model)


def validate_model(db: Session, user: User, purpose: ModelPurpose) -> None:
    """
    Check that the user's configured model for *purpose* can be initialized.

    Called before long-running work starts, so a misconfigured model surfaces
    as an error the user can act on rather than as a failure deep inside a job.
    A user with nothing configured for *purpose* is always valid -- they get
    the system default.

    Raises:
        ValueError: If the configured model cannot be initialized. The message
            is user-facing and says what is wrong with the configuration.
    """
    _check_purpose(purpose)
    logger.info(
        "Validating %s model for user_id=%s, org_id=%s",
        purpose,
        user.id,
        user.organization_id,
    )

    if not getattr(user.settings.models, purpose).model_id:
        return

    _resolve_for_user(db, user, purpose, override=None)


def _is_rhesis_system_model(provider: str, api_key: str) -> bool:
    """
    Check if a model is a Rhesis system model.

    Rhesis system models use the backend's infrastructure and have no user-provided API key.

    Args:
        provider: The provider type value (e.g., "rhesis", "openai", "gemini")
        api_key: The API key stored for the model

    Returns:
        True if this is a Rhesis system model, False otherwise
    """
    return provider == "rhesis" and not api_key


def _is_hosted_model(provider: str, api_key: Optional[str]) -> bool:
    """
    Check if an explicitly-selected Model row runs on Rhesis-operated infrastructure.

    A model is charged for if and only if *Rhesis supplied it*. There are
    exactly three ways that happens, and this function covers the first:
    the org picked one of Rhesis's own hosted providers. The other two are
    the system default (:func:`resolve_default_hosted_model`, which stamps
    unconditionally because whatever a deployment names as its
    `DEFAULT_*_MODEL` is that deployment's own infra cost by definition) and
    a Rhesis-issued platform key (:func:`_try_platform_key_model`, which
    passes `metered` explicitly because a platform key looks like an org key).

    So: `rhesis`/`polyphemus` are the two provider values meaning "use
    Rhesis's own hosted infrastructure" in the Models UI, and they charge
    when the row carries no org key of its own. Every *other* provider an
    org names here -- their `vertex_ai`, `ollama`, `openai`, self-hosted
    `vllm`, whatever -- is their infrastructure choice and never charges,
    whatever the row's key or endpoint looks like.

    Deliberately *not* inferred from credentials. A row for a non-Rhesis
    provider with a blank key will fall through to whatever this deployment
    has in `OPENAI_API_KEY` and friends, because every SDK provider treats a
    falsy key as "read the environment". That is a real problem, but it is a
    misconfiguration and a credential-leak problem, not a billing one:
    the answer is to surface it (see `_warn_if_row_would_use_our_credentials`),
    not to bill an org for a model we never agreed to supply. Trying to
    encode it here is what made the two earlier attempts wrong -- a bare
    `not api_key` swept in every keyless self-hosted row, and adding an
    endpoint check still caught providers like `ollama` and `vllm` that fall
    back to an implicit `localhost` base (`litellm/main.py`) and so reach the
    org's own server with neither key nor endpoint set.

    Args:
        provider: The provider type value (e.g., "rhesis", "polyphemus", "openai")
        api_key: The API key stored for the model, e.g. `model_record.key`.
            Nullable, and blank or whitespace-only is treated as absent.

    Returns:
        True if this model's tokens should accrue against the org's
        MODEL_TOKENS quota.
    """
    return provider in ("rhesis", "polyphemus") and not (api_key or "").strip()


def has_own_credentials(provider: str, api_key: Optional[str], endpoint: Optional[str]) -> bool:
    """Whether a Model row can be served without reaching for our credentials.

    A tenant row needs either a key of its own or an endpoint of its own.
    With neither, every provider falls back to reading its key from the
    process environment (``litellm/main.py``: ``api_key or ... or
    get_secret("OPENAI_API_KEY")``), so the row would quietly run on whatever
    this deployment holds -- billed to us, attributed to nobody, and looking
    to the tenant like a working configuration.

    ``rhesis``/``polyphemus`` rows are exempt: running on our credentials with
    no key is exactly what picking them means, and they are billed for it.
    """
    if provider in ("rhesis", "polyphemus"):
        return True
    return bool((api_key or "").strip() or (endpoint or "").strip())


def _require_own_credentials(
    provider: str, api_key: Optional[str], endpoint: Optional[str], model_name: str
) -> None:
    """Refuse to build a tenant model that would borrow our provider keys.

    Raising beats warning here because the fallback is silent and succeeds:
    without this the tenant gets working inference on our account and nobody
    finds out. Refusing costs only rows that are already misconfigured, since
    a row with no key of its own always has an endpoint in practice.
    """
    if has_own_credentials(provider, api_key, endpoint):
        return
    logger.error(
        "Refusing to build model '%s' (provider '%s'): no API key and no endpoint, so it would "
        "run on this deployment's environment credentials",
        model_name,
        provider,
    )
    raise ModelConfigurationError(
        f"Your configured model '{model_name}' ({provider}) has neither an API key nor an "
        f"endpoint. Add an API key, or an endpoint if it is a self-hosted model, in the "
        f"Models settings."
    )


def ensure_language_model(model_or_provider: Union[str, BaseLLM]) -> BaseLLM:
    """Turn a ``"provider/model_name"`` string into a real, stamped model.

    The single place in the backend that does that. Call sites used to unwrap
    strings themselves with a plain ``get_model(x)``, which produces an
    *unstamped* model -- so whether those tokens counted depended on
    remembering to stamp, at N sites, which is the bug this accrual mechanism
    exists to remove. Routing them all through here removes the choice.

    Not needed to use :func:`resolve_model`, which returns a built model and
    calls this itself. What is left for it is the callers holding a model
    string from somewhere else -- a deployment setting, a metric config --
    and the resolution paths inside this module.

    ``metered=True`` is always right for a string, because a string only ever
    names the system default: a ``DEFAULT_*_MODEL`` setting, or a model
    configured on a metric. ``_fetch_and_configure_model`` (the only path
    carrying an org's own key) stamps directly or raises.

    Args:
        model_or_provider: A bare ``"provider/model_name"`` string, or an
            already-resolved (and already-stamped) ``BaseLLM`` to pass through.

    Returns:
        A ``BaseLLM`` instance, stamped if this function built it.

    Raises:
        Whatever ``get_model`` raises when the string names something that
        cannot be built -- typically ``ValueError``.
    """
    if isinstance(model_or_provider, str):
        return stamp_usage_provenance(
            get_model(model_or_provider, model_type="language"),
            metered=True,
        )
    return model_or_provider


def _ensure_embedder(
    model_or_provider: Union[str, BaseEmbedder], dimensions: Optional[int] = None
) -> BaseEmbedder:
    """The embedder counterpart to :func:`ensure_language_model`.

    No provenance stamp: embedders have no usage-emission path, so there is
    nothing to attribute. *dimensions* applies only here, on the system
    default -- a configured ``Model`` row carries its own.
    """
    if isinstance(model_or_provider, str):
        extra = {"dimensions": dimensions} if dimensions is not None else {}
        return get_model(model_or_provider, model_type="embedding", **extra)
    return model_or_provider


def _enforce_model_token_quota(db: Session, organization_id: Optional[str]) -> None:
    """Enforce the MODEL_TOKENS quota for *organization_id* before a hosted
    model is constructed.

    Fails closed: a missing ``organization_id`` raises ``ValueError``
    rather than silently skipping enforcement. Every real call site
    already has an org id in scope, so a ``None`` here means a new caller
    forgot to thread it -- failing loud surfaces the gap immediately
    instead of granting unmetered access.

    :raises ValueError: if *organization_id* is falsy.
    :raises ~rhesis.backend.app.quota.enforcement.QuotaExceededError: if
        the org has reached its enforceable ceiling for ``MODEL_TOKENS``.
    """
    if not organization_id:
        raise ValueError(
            "No organization_id available for a hosted-model quota check. "
            "Every production call site must pass one; see the docstring."
        )
    organization = db.query(Organization).filter(Organization.id == organization_id).first()
    enforce_quota(db, str(organization_id), organization, QuotaResource.MODEL_TOKENS)


def resolve_default_hosted_model(
    default_model: str, db: Session, organization_id: Optional[str]
) -> BaseLLM:
    """
    Build the system default model, after gating it on the org's token quota.

    For the callers that have an organization but no resolvable *user* to
    resolve through: the execution/evaluation model resolution in the batch
    and sequential test-execution paths when a test config carries no user,
    and explorer suggestions. :func:`resolve_model` uses it internally for
    the same reason, when a user has configured nothing for a purpose.

    Public rather than underscore-prefixed because those out-of-module
    fallbacks are the point of it: anything that would otherwise hand a bare
    `DEFAULT_*_MODEL` string downstream should route through here instead, so
    that the resulting model carries a provenance stamp.

    Construction is cheap (no network call -- provider `__init__`s only set
    up client config) so doing it eagerly costs nothing.

    Takes ``db``/``organization_id`` -- unlike an earlier version of this
    function, which took neither and left MODEL_TOKENS display-only. Every
    real caller (checked directly rather than assumed) already has an
    organization id in scope even when it has no resolvable *user*: the
    batch/sequential execution paths that hit this when a test config
    carries no user still have `test_config.organization_id`. Which org to
    *bill* still comes from the ambient context at emission time (see
    `rhesis.backend.app.usage_attribution`) -- this is only the pre-call
    check that a hosted call is allowed to happen at all.

    Args:
        default_model: A "provider/model_name" string, e.g. "rhesis/rhesis"
        db: Database session, tenant-scoped for *organization_id* (RLS on
            the `usage` table this indirectly reads requires it -- see
            `auth/quota_gates.py` for the same requirement on the HTTP gate).
        organization_id: The org to enforce the quota against.

    Returns:
        A model stamped `usage_metered=True`.

    Raises:
        ~rhesis.backend.app.quota.enforcement.QuotaExceededError: if the org
            has reached its enforceable ceiling for `MODEL_TOKENS`.
        Whatever `get_model` raises if this deployment's `DEFAULT_*_MODEL`
            cannot be built at all -- typically `ValueError`, but also e.g.
            `ImportError` from providers with optional dependencies
            (`huggingface.py` needs torch). That used to be swallowed here
            and the bare string returned, which only moved the same failure
            to whichever call site got around to constructing it.
    """
    _enforce_model_token_quota(db, organization_id)

    # No provider restriction: the *system default* is by definition the
    # model this deployment runs on its own credentials, whatever provider
    # it names. A deployment configured with
    # ``DEFAULT_GENERATION_MODEL=vertex_ai/gemini-2.5-flash`` calls Vertex
    # from the backend using the server's GOOGLE_APPLICATION_CREDENTIALS,
    # so Rhesis pays for those tokens exactly as it does for
    # ``rhesis/...``. Restricting this to rhesis/polyphemus meant every such
    # deployment reported zero MODEL_TOKENS forever.
    return ensure_language_model(default_model)


def _call_polyphemus_with_delegation(user: User, model_name: str, **kwargs):
    """
    Create Polyphemus client with delegation token.

    Uses service delegation tokens to allow the backend to call Polyphemus
    on behalf of a user while maintaining user attribution.

    Args:
        user: User on whose behalf the request is made
        model_name: Polyphemus model name (e.g., "default")
        **kwargs: Additional arguments to pass to PolyphemusLLM

    Returns:
        Configured PolyphemusLLM instance, stamped as running on our credentials

    Raises:
        ValueError: If user is not active or not verified
    """
    from rhesis.backend.app.auth.token_utils import create_service_delegation_token
    from rhesis.sdk.models.providers.polyphemus import PolyphemusLLM

    # Verify user is active and verified before creating delegation token
    if not user.is_active:
        logger.error("Cannot create delegation token: user %s is inactive", user.email)
        raise ValueError("User account is inactive")

    if not user.is_verified:
        logger.error("Cannot create delegation token: user %s is not verified", user.email)
        raise ValueError("User account is not verified")

    delegation_token = create_service_delegation_token(user, "polyphemus")
    polyphemus_url = os.environ.get("DEFAULT_POLYPHEMUS_URL", "https://polyphemus.rhesis.ai")

    # Metered: a delegation token means the call goes out on Rhesis
    # infrastructure, not on a key the org supplied.
    return stamp_usage_provenance(
        PolyphemusLLM(
            model_name=model_name,
            api_key=delegation_token,
            base_url=polyphemus_url,
            **kwargs,
        ),
        metered=True,
    )


def _try_platform_key_model(
    db: Session,
    organization_id: str,
    provider: str,
    model_name: str,
    model_type: str,
    *,
    metered: bool = False,
) -> Optional[Union[BaseLLM, BaseEmbedder]]:
    """Authenticate a Rhesis-hosted model with the org's platform key, when
    ENABLE_RHESIS_KEY is set.

    Returns a configured instance when the feature is enabled and a platform
    key resolves; ``None`` otherwise, so callers fall through to their own
    default/delegation logic unchanged.

    ``metered`` records that we pay for these tokens, and must be passed
    explicitly here rather than derived from :func:`_is_hosted_model`: that
    helper reads any API key as the org's own, and the platform key looks like
    one while actually being Rhesis-issued credentials. Left ``False`` for
    embedders, which have no usage-emission path at all, so the stamp is a
    no-op on them.
    """
    if not get_application_settings().enable_rhesis_key:
        return None
    key = get_platform_api_key(db, organization_id)
    if not key:
        return None
    return stamp_usage_provenance(
        get_model(
            provider=provider,
            model_name=model_name,
            api_key=key,
            model_type=model_type,
        ),
        metered=metered,
    )


def _load_model_row(db: Session, model_id: str, organization_id: str) -> Optional[Model]:
    """The org's own Model row, or ``None`` when it is missing or unusable.

    The fallback stays with the caller: a language model falls back to a
    *constructed* default, an embedder to the bare default string.
    """
    # SECURITY: Always use organization_id for filtering
    model = model_crud.get_model(db=db, model_id=model_id, organization_id=organization_id)
    if not model or not model.provider_type:
        logger.warning("Model with id=%s not found or has no provider_type", model_id)
        return None
    return model


def _build_configured_model(
    model: Model,
    provider: str,
    model_name: str,
    api_key: Optional[str],
    model_type: Literal["language", "embedding"],
) -> Union[BaseLLM, BaseEmbedder]:
    """Build the SDK instance for a Model row, or raise a user-facing error.

    The SDK reports every configuration problem as a plain ``ValueError``, so
    which one it is has to be read back off the message text.
    """
    embedding = model_type == "embedding"
    label = "embedding model" if embedding else "model"
    subject = "embedder" if embedding else "user model"
    try:
        extra_params = {}
        if model.endpoint and model.endpoint.strip():
            extra_params["api_base"] = model.endpoint.strip()
        return get_model(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            model_type=model_type,
            **extra_params,
        )
    except ValueError as e:
        error_msg = str(e)
        error_msg_lower = error_msg.lower()

        # Provide specific error messages based on the type of configuration issue
        if "api_key" in error_msg_lower or "not set" in error_msg_lower:
            logger.error("%s API key not configured: %s", subject.capitalize(), error_msg)
            raise ModelConfigurationError(
                f"Your configured {label} '{model.name}' ({provider}/{model_name}) requires "
                f"an API key that is missing or invalid. "
                f"Please update your API key in the Models settings.",
                original_error=e,
            )
        elif "provider" in error_msg_lower or "not supported" in error_msg_lower:
            logger.error("Invalid provider for %s: %s", subject, error_msg)
            raise ModelConfigurationError(
                f"Your configured {label} '{model.name}' uses an unsupported provider "
                f"({provider}). Please select a different model in the Models settings.",
                original_error=e,
            )
        # An embedder has no message of its own for a bad model name, so it
        # falls through to the generic one -- as it always has.
        elif (
            not embedding
            and "model" in error_msg_lower
            and ("not found" in error_msg_lower or "invalid" in error_msg_lower)
        ):
            logger.error("Invalid model name for user model: %s", error_msg)
            raise ModelConfigurationError(
                f"Your configured model '{model.name}' has an invalid model name ({model_name}). "
                f"Please select a valid model in the Models settings.",
                original_error=e,
            )
        logger.error("Failed to configure %s: %s", subject, error_msg)
        if embedding:
            raise ModelConfigurationError(
                f"Failed to configure your embedding model '{model.name}': {error_msg}. "
                f"Please check your model configuration in the Models settings.",
                original_error=e,
            )
        raise ModelConfigurationError(
            f"Failed to initialize your configured model '{model.name}': {error_msg}",
            original_error=e,
        )


def _fetch_and_configure_model(
    db: Session,
    model_id: str,
    organization_id: str,
    default_model: str,
    user: User = None,
) -> BaseLLM:
    """
    Fetch a model from the database and configure it for use.

    Args:
        db: Database session
        model_id: ID of the model to fetch
        organization_id: Organization ID for security filtering
        default_model: Default model to fall back to

    Returns:
        A configured BaseLLM, built from the system default when the
        configured model cannot be loaded
    """
    model = _load_model_row(db, model_id, organization_id)
    if model is None:
        return resolve_default_hosted_model(default_model, db, organization_id)

    # Get provider configuration
    provider = model.provider_type.type_value
    model_name = model.model_name
    # `Model.key` is NOT NULL but accepts "", and a whitespace-only key is the same
    # misconfiguration. Normalize once so the provenance decision and the provider
    # both see a single "no key" value rather than two that differ subtly: a "  "
    # reaches LiteLLM as a real key and fails auth instead of falling back.
    api_key = (model.key or "").strip() or None
    _require_own_credentials(provider, api_key, model.endpoint, model.name)

    # Enforce MODEL_TOKENS once, up front, iff this call will end up billed to
    # us. _is_hosted_model(provider, api_key) is exactly that predicate for
    # every branch below: the two special-cased branches (rhesis / polyphemus
    # without a stored key) only special-case providers _is_hosted_model
    # already considers hosted, and the general path's own `metered=` kwarg
    # a few lines down is this identical expression. Gating here rather than
    # unconditionally at function entry is what keeps an org's own key (a
    # non-hosted provider, or a hosted provider with its own key) from ever
    # being blocked by *our* token quota -- their call was never going to
    # cost us anything.
    if _is_hosted_model(provider, api_key):
        _enforce_model_token_quota(db, organization_id)

    # Special handling for Rhesis system models
    if _is_rhesis_system_model(provider, api_key):
        # When ENABLE_RHESIS_KEY is set: authenticate the prepopulated Rhesis-hosted
        # system models with the org-scoped platform key when one is configured,
        # accruing usage like any other hosted call. Otherwise behavior is
        # unchanged: fall back to the stamped default.
        hosted = _try_platform_key_model(
            db,
            organization_id,
            "rhesis",
            model_name or "default",
            "language",
            metered=True,
        )
        if hosted is not None:
            return hosted
        return resolve_default_hosted_model(default_model, db, organization_id)

    # Special handling for Polyphemus models without a stored API key.
    #
    # - Self-hosted deployments configure a real RHESIS_API_KEY and call
    #   Polyphemus directly with it (same path as any other provider below).
    # - Rhesis-hosted (SaaS) deployments have no such key configured, so we
    #   mint a short-lived delegation token on the user's behalf instead.
    #   Delegation only validates because the backend and Polyphemus share
    #   the same JWT_SECRET_KEY there; a self-hosted backend's secret would
    #   be meaningless to the externally-hosted Polyphemus service, so a
    #   configured RHESIS_API_KEY always takes precedence when present.
    if provider == "polyphemus" and not api_key:
        # When ENABLE_RHESIS_KEY is set: authenticate with the org-scoped platform
        # key when configured, accruing usage like any other hosted call.
        # Otherwise behavior is unchanged: existing env-precedence and
        # delegation logic runs when no per-org key resolves.
        hosted = _try_platform_key_model(
            db, organization_id, "polyphemus", model_name, "language", metered=True
        )
        if hosted is not None:
            return hosted
        if get_rhesis_settings().api_key:
            logger.debug("Using configured RHESIS_API_KEY for Polyphemus (self-hosted mode)")
        elif user:
            return _call_polyphemus_with_delegation(user, model_name)

    return stamp_usage_provenance(
        _build_configured_model(model, provider, model_name, api_key, "language"),
        metered=_is_hosted_model(provider, api_key),
    )


def _fetch_and_configure_embedder(
    db: Session,
    model_id: str,
    organization_id: str,
    default_model: str,
    dimensions: Optional[int] = None,
) -> BaseEmbedder:
    """
    Fetch a model from the database and configure it as an embedder.

    Args:
        db: Database session
        model_id: UUID of the configured Model
        organization_id: Organization ID (for security filtering)
        default_model: Default embedder provider to fall back to
        dimensions: Vector width, used only when falling back to default_model

    Returns:
        A configured BaseEmbedder, built from the system default when the
        configured model cannot be loaded
    """
    model = _load_model_row(db, model_id, organization_id)
    if model is None:
        return _ensure_embedder(default_model, dimensions)

    # Get provider configuration
    provider = model.provider_type.type_value
    model_name = model.model_name
    api_key = model.key

    # Special handling for Rhesis system models
    if _is_rhesis_system_model(provider, api_key):
        # When ENABLE_RHESIS_KEY is set: authenticate the prepopulated Rhesis-hosted
        # embedding models with the org-scoped platform key when configured.
        # Otherwise behavior is unchanged: fall back to default_model.
        hosted = _try_platform_key_model(
            db, organization_id, "rhesis", model_name or "default", "embedding"
        )
        if hosted is not None:
            return hosted
        return _ensure_embedder(default_model, dimensions)

    return _build_configured_model(model, provider, model_name, api_key, "embedding")
