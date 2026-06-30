import asyncio
import base64
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, List, Optional, Union

from dotenv import load_dotenv

load_dotenv()

# Import endpoint module first to initialize RhesisClient
# This ensures only ONE tracer provider exists (critical for proper trace nesting)
import endpoint as endpoint_module
from cachetools import TTLCache
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from notifications import send_rate_limit_alert
from pydantic import BaseModel, field_validator
from session_store import create_session_store
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from rhesis.sdk import Parameters, endpoint
from rhesis.sdk.services.extractor import extract_with_vision_fallback

CHATBOT_PROJECT = os.getenv("RHESIS_CHATBOT_PROJECT", "chatbot-demo")
PARAMETERS_ENVIRONMENT = os.getenv(
    "RHESIS_PARAMETERS_ENVIRONMENT",
    os.getenv("RHESIS_PARAMETERS_LABEL", "default"),
)

ABSENT_STRING_VALUES = {"", "none", "null", "undefined"}


def _is_absent_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in ABSENT_STRING_VALUES:
        return True
    return False


def _optional_string(value: Any) -> Optional[str]:
    if _is_absent_value(value):
        return None
    return str(value)


def _float_or_default(value: Any, default: float) -> float:
    if _is_absent_value(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_or_default(value: Any, default: int) -> int:
    if _is_absent_value(value):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_defaults() -> dict:
    """Return parameter defaults sourced entirely from environment variables."""
    return {
        "system_prompt": None,
        "use_case": os.getenv("DEFAULT_USE_CASE", "insurance"),
        "model": os.getenv("DEFAULT_GENERATION_MODEL"),
        "temperature": float(os.getenv("DEFAULT_TEMPERATURE", "0.7")),
        "max_tokens": int(os.getenv("DEFAULT_MAX_TOKENS", "1024")),
        "output_mode": os.getenv("DEFAULT_OUTPUT_MODE", "text"),
        "context_strategy": os.getenv("DEFAULT_CONTEXT_STRATEGY", "heuristic"),
    }


def _resolve_chatbot_params() -> dict:
    """Resolve chatbot params from the Rhesis SDK, falling back to env defaults.

    Skips the SDK entirely when RHESIS_API_KEY is not configured so the
    chatbot can operate as a standalone service with no Rhesis dependency.
    """
    from rhesis.sdk.config import get_api_key

    try:
        api_key = get_api_key()
    except Exception:
        api_key = None

    if not api_key:
        logger.debug("RHESIS_API_KEY not set; using env defaults for chatbot parameters")
        return _env_defaults()

    try:
        params = Parameters.get(
            project=CHATBOT_PROJECT, environment=PARAMETERS_ENVIRONMENT
        )
        return {
            "system_prompt": params.get_text("system_prompt") or params.get_string("system_prompt"),
            "use_case": params.get_enum("use_case"),
            "model": params.get_string("model") or os.getenv("DEFAULT_GENERATION_MODEL"),
            "temperature": params.get_number("temperature", 0.7),
            "max_tokens": params.get_integer("max_tokens", 1024),
            "output_mode": params.get_enum("output_mode", "text"),
            "context_strategy": params.get_enum("context_strategy", "heuristic"),
        }
    except Exception:
        logger.warning("SDK Parameters.get() failed; using env defaults", exc_info=True)
        return _env_defaults()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Get rate limit from environment variable (total desired limit across all workers)
# This will be automatically divided by the number of workers
WORKERS = int(os.getenv("WORKERS", "4"))  # Number of Gunicorn workers
TOTAL_RATE_LIMIT_AUTHENTICATED = int(os.getenv("CHATBOT_RATE_LIMIT", "1000"))
TOTAL_RATE_LIMIT_PUBLIC = 100  # Public users get lower limit

# Calculate per-worker limits (each worker tracks independently with in-memory storage)
RATE_LIMIT_PER_WORKER_AUTHENTICATED = TOTAL_RATE_LIMIT_AUTHENTICATED // WORKERS
RATE_LIMIT_PER_WORKER_PUBLIC = TOTAL_RATE_LIMIT_PUBLIC // WORKERS

RATE_LIMIT_AUTHENTICATED = f"{RATE_LIMIT_PER_WORKER_AUTHENTICATED}/day"
RATE_LIMIT_PUBLIC = f"{RATE_LIMIT_PER_WORKER_PUBLIC}/day"

# API Key for backend authentication (optional)
CHATBOT_API_KEY = os.getenv("CHATBOT_API_KEY")

# Email domains whose rh- key holders are granted unlimited rate-limit tier.
# Comma-separated; defaults to "rhesis.ai". Override via CHATBOT_UNLIMITED_EMAIL_DOMAINS.
CHATBOT_UNLIMITED_EMAIL_DOMAINS = {
    d.strip().lower()
    for d in os.getenv("CHATBOT_UNLIMITED_EMAIL_DOMAINS", "rhesis.ai").split(",")
    if d.strip()
}

_TOKEN_INTROSPECT_TTL = 300  # seconds to cache introspection results
# Bounded TTL cache: evicts least-recently-used entries once full, and
# automatically expires entries after _TOKEN_INTROSPECT_TTL seconds.
# Prevents unbounded memory growth from high-volume distinct rh- tokens.
_token_cache: TTLCache = TTLCache(maxsize=500, ttl=_TOKEN_INTROSPECT_TTL)

# Session management configuration
SESSION_TIMEOUT_HOURS = int(os.getenv("SESSION_TIMEOUT_HOURS", "24"))  # Default 24 hours
SESSION_TTL_SECONDS = SESSION_TIMEOUT_HOURS * 60 * 60
session_store = create_session_store(ttl_seconds=SESSION_TTL_SECONDS)

# HTTP Bearer token security
security = HTTPBearer(auto_error=False)  # auto_error=False allows optional auth


def get_rate_limit_identifier(request: Request) -> str:
    """
    Get rate limit identifier from request state.

    This is called by the limiter's key function, but should NOT be used
    as the primary rate limiting mechanism. Use check_rate_limit_chatbot
    dependency instead.

    This function now only reads from request.state which is set by
    the verify_api_key_with_rate_limit dependency.
    """
    # Get identifier from request state (set by auth dependency)
    identifier = getattr(request.state, "rate_limit_id", None)
    if identifier:
        return identifier

    # Fallback to IP address (shouldn't normally reach here with proper dependency order)
    ip = get_remote_address(request)
    logger.warning(f"⚠️ Rate limit identifier not found in request state, falling back to IP: {ip}")
    return f"public:{ip}"


# Initialize rate limiter with custom key function
limiter = Limiter(key_func=get_rate_limit_identifier)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for app startup and shutdown."""
    logger.info("🚀 Chatbot session TTL configured for %sh", SESSION_TIMEOUT_HOURS)

    yield

    await session_store.close()


def _introspect_user_key(token: str) -> Optional[str]:
    """Call GET /tokens/current with a personal API key and return the owner's email.

    Results are cached for _TOKEN_INTROSPECT_TTL seconds. Transient network
    failures return None without caching so the next request retries immediately.
    """
    import requests as _requests

    from rhesis.sdk.config import get_base_url

    if token in _token_cache:
        return _token_cache[token]

    email = None
    try:
        resp = _requests.get(
            f"{get_base_url().rstrip('/')}/tokens/current",
            headers={"Authorization": f"Bearer {token}"},
            timeout=3,
        )
        if resp.status_code == 200:
            email = resp.json().get("user_email")
            _token_cache[token] = email
        elif resp.status_code in (401, 403, 404):
            # Definitive "bad key" — cache the negative result
            _token_cache[token] = None
        # 5xx / 429 / other transient errors: don't cache, let next request retry
        else:
            logger.warning("Unexpected status %d from token introspection", resp.status_code)
            return None
    except Exception:
        logger.warning("User key introspection failed", exc_info=True)
        return None  # transient failure — don't cache

    return email


def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    Verify API key for authentication.
    Returns authentication info. Does not raise error if no key is provided (allows public access).
    Also sets rate_limit_id and rate_limit_tier in request.state for proper rate limiting.
    """
    def _set_public(reason: str) -> dict:
        ip = get_remote_address(request)
        request.state.rate_limit_id = f"public:{ip}"
        request.state.rate_limit_tier = "public"
        logger.debug("Public tier (%s) - IP: %s", reason, ip)
        return {"authenticated": False, "tier": "public"}

    token = credentials.credentials if credentials else None

    # --- Fast path: shared service key ---
    if CHATBOT_API_KEY and token == CHATBOT_API_KEY:
        org_id = request.headers.get("X-Organization-ID", "default-org")
        user_id = request.headers.get("X-User-ID", "default-user")
        request.state.rate_limit_id = f"authenticated:{org_id}:{user_id}"
        request.state.rate_limit_tier = "authenticated"
        logger.info(
            "Authenticated (shared key) - Identifier: %s, Rate limit: %s",
            request.state.rate_limit_id,
            RATE_LIMIT_AUTHENTICATED,
        )
        return {"authenticated": True, "tier": "authenticated"}

    # --- Personal rh- key path ---
    if token and token.startswith("rh-"):
        email = _introspect_user_key(token)
        if email is None:
            # Introspection failed or key is invalid — fail-closed to public
            return _set_public("rh- key unverifiable")
        domain = email.split("@")[-1].lower() if "@" in email else ""
        if domain in CHATBOT_UNLIMITED_EMAIL_DOMAINS:
            request.state.rate_limit_id = f"unlimited:{email}"
            request.state.rate_limit_tier = "unlimited"
            logger.info("Unlimited tier granted for %s", email)
            return {"authenticated": True, "tier": "unlimited"}
        # Valid rh- key but non-unlimited domain — authenticated tier, bucketed by email
        request.state.rate_limit_id = f"authenticated:{email}"
        request.state.rate_limit_tier = "authenticated"
        logger.info(
            "Authenticated (rh- key) - Identifier: %s, Rate limit: %s",
            request.state.rate_limit_id,
            RATE_LIMIT_AUTHENTICATED,
        )
        return {"authenticated": True, "tier": "authenticated"}

    # --- No credentials, no recognised key ---
    if token and not CHATBOT_API_KEY:
        # Service key not configured — unknown token, fall through to public
        pass
    elif token:
        # Token was provided but doesn't match the shared key and isn't an rh- key
        raise HTTPException(
            status_code=401,
            detail="Invalid API key. Public access available with rate limit of 100 requests/day.",
        )

    return _set_public("no credentials")


async def check_rate_limit_chatbot(
    request: Request,
    auth: dict = Depends(verify_api_key),  # Authentication runs first
) -> dict:
    """
    Rate limit dependency that runs after authentication.

    This ensures rate limiting is based on authenticated user/org identifiers
    instead of just IP addresses.

    The "echo" use case is exempt from rate limiting.

    Returns the auth dict for downstream dependencies.
    """
    import json

    from limits import parse

    # The "echo" use case has no usage limitation
    try:
        body_bytes = await request.body()
        body = json.loads(body_bytes) if body_bytes else {}
        if body.get("use_case") == "echo":
            logger.debug("⚡ Rate limit skipped for echo use case")
            return auth
    except Exception:
        pass

    # Unlimited tier: skip all rate limit checks
    if request.state.rate_limit_tier == "unlimited":
        logger.debug("Rate limit skipped for unlimited tier")
        return auth

    # Get the rate limit identifier and tier from request state (set by verify_api_key)
    identifier = request.state.rate_limit_id
    tier = request.state.rate_limit_tier

    # Determine which rate limit to apply
    rate_limit_str = RATE_LIMIT_AUTHENTICATED if tier == "authenticated" else RATE_LIMIT_PUBLIC

    try:
        # Parse the rate limit string into a RateLimitItem
        rate_limit_item = parse(rate_limit_str)

        # Manually perform rate limit check using slowapi's internal limiter
        allowed = limiter._limiter.hit(rate_limit_item, identifier)

        if not allowed:
            logger.warning(
                f"🚫 Rate limit exceeded - Tier: {tier}, Identifier: {identifier}, "
                f"Limit: {rate_limit_str}"
            )

            # Send email notification (async, non-blocking)
            try:
                send_rate_limit_alert(request, identifier, tier.capitalize(), rate_limit_str)
            except Exception as e:
                logger.error(f"⚠️ Error sending rate limit alert: {e}")

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again later. Limit: {rate_limit_str}",
            )

        logger.debug(f"✅ Rate limit check passed - Tier: {tier}, Identifier: {identifier}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Rate limiting error for {identifier}: {str(e)}", exc_info=True)
        # Don't block request on rate limiter errors - fail open
        pass

    return auth


app = FastAPI(
    title="Rhesis Insurance Chatbot API",
    description=(
        "Default insurance chatbot (Rosalind) for new user onboarding. "
        "Provides instant access to explore Rhesis AI capabilities."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# Custom rate limit exceeded handler with email notifications
async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded that sends email notifications.
    """
    # Get the rate limit identifier
    identifier = get_rate_limit_identifier(request)

    # Determine rate limit type and value
    is_authenticated = identifier.startswith("authenticated:")
    rate_limit_type = "Authenticated" if is_authenticated else "Public"
    rate_limit_value = RATE_LIMIT_AUTHENTICATED if is_authenticated else RATE_LIMIT_PUBLIC

    logger.warning(
        f"🚫 RATE LIMIT EXCEEDED - Type: {rate_limit_type}, "
        f"Identifier: {identifier}, Limit: {rate_limit_value}"
    )

    # Send email notification (async, non-blocking)
    try:
        send_rate_limit_alert(request, identifier, rate_limit_type, rate_limit_value)
    except Exception as e:
        # Log but don't fail the response
        logger.error(f"⚠️ Error sending rate limit alert: {e}")

    # Return the standard rate limit exceeded response (not awaited - it returns a Response object)
    return _rate_limit_exceeded_handler(request, exc)


# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)


def get_available_use_cases() -> List[str]:
    """Get list of available use cases from use_cases directory."""
    try:
        import os

        current_dir = os.path.dirname(os.path.abspath(__file__))
        use_cases_dir = os.path.join(current_dir, "use_cases")

        use_cases = ["echo"]  # Built-in use cases (no prompt file required)
        for filename in os.listdir(use_cases_dir):
            if filename.endswith(".md"):
                use_case_name = filename[:-3]  # Remove .md extension
                use_cases.append(use_case_name)
        return sorted(use_cases)
    except Exception:
        return ["echo", "insurance", "travel"]  # Default fallback


class FileInput(BaseModel):
    filename: str
    content_type: Optional[str] = None
    data: str  # base64-encoded file content
    extracted_text: Optional[str] = None  # pre-extracted text from Rhesis backend


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None
    use_case: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    mode: Optional[str] = None  # Output mode: "text" or "json"
    context_strategy: Optional[str] = None
    files: Optional[List[FileInput]] = None
    rhesis: Optional[dict] = None

    @field_validator("files", mode="before")
    @classmethod
    def coerce_empty_to_none(cls, v):
        """Treat empty strings and other falsy non-list values as None."""
        if v is None or v == "" or v == []:
            return None
        return v


class ChatResponse(BaseModel):
    message: Union[str, dict]
    session_id: str
    context: List[str]
    metadata: dict
    tool_calls: Optional[List[dict]] = None


def _get_vision_model():
    """Return a BaseLLM instance for vision extraction, or None on failure."""
    from rhesis.sdk.models.factory import get_language_model

    model_name = os.getenv("DEFAULT_GENERATION_MODEL")
    if model_name:
        try:
            model = get_language_model(model_name)
            logger.info("Using vision model '%s' for file extraction", model_name)
            return model
        except Exception as exc:
            logger.warning(
                "Could not initialise vision model '%s' for extraction: %s — falling back",
                model_name,
                exc,
            )
    return None


def extract_file_content(file_input: FileInput) -> dict:
    """Extract text content from a file for injection into the prompt.

    Uses pre-extracted text from the Rhesis backend when available (preferred),
    otherwise delegates to ``extract_with_vision_fallback`` which applies the
    same text-layer → vision-model strategy used everywhere in the platform.

    Returns:
        Dict with 'filename' and 'content' keys.
    """
    if file_input.extracted_text:
        return {"filename": file_input.filename, "content": file_input.extracted_text}

    file_bytes = base64.b64decode(file_input.data)
    content = extract_with_vision_fallback(
        file_bytes,
        file_input.filename,
        file_input.content_type or "",
        model=_get_vision_model(),
    )

    if not content or not content.strip():
        content = "[File content could not be extracted]"
    return {"filename": file_input.filename, "content": content}


@endpoint(
    name="chat",
    description="Process a chat message and return structured response",
    request_mapping={
        "message": "{{ input }}",
        "session_id": "{{ session_id | default(none) }}",
        "system_prompt": "{{ params.system_prompt | default(none) }}",
        "model": "{{ params.model | default(none) }}",
        "temperature": "{{ params.temperature | default(0.7) }}",
        "max_tokens": "{{ params.max_tokens | default(1024) }}",
        "output_mode": "{{ params.output_mode | default(mode | default('text')) }}",
        "context_strategy": "{{ params.context_strategy | default('heuristic') }}",
        "use_case": "{{ params.use_case | default('insurance') }}",
        "conversation_history": "{{ conversation_history | default(none) }}",
        "files": "{{ files }}",
        "rhesis": {
            "test_id": "{{ test_id | default(none) }}",
            "test_configuration_id": "{{ test_configuration_id | default(none) }}",
            "test_run_id": "{{ test_run_id | default(none) }}",
        },
    },
    response_mapping={
        "output": "{{ message }}",
        "session_id": "{{ session_id }}",
        "context": "{{ context }}",
        "metadata": "{{ metadata }}",
        "tool_calls": "{{ tool_calls }}",
    },
)
async def chat(
    message: str,
    *,
    session_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
    use_case: str = "insurance",
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    output_mode: str = "text",
    context_strategy: str = "heuristic",
    conversation_history: Optional[List[dict]] = None,
    files: Optional[List[dict]] = None,
    file_contents: Optional[List[dict]] = None,
    rhesis: Optional[dict] = None,
) -> ChatResponse:
    """
    Process a chat message and return structured response.

    Session management is handled here so the function works identically
    whether called from the FastAPI route or invoked remotely via the
    SDK connector (which bypasses the FastAPI route).

    Args:
        message: User's message
        session_id: Session identifier (reuse to continue a conversation)
        use_case: Use case for system prompt
        conversation_history: Explicit conversation history; when ``None``
            the history is looked up from the in-memory session store.
        files: Raw file dicts from the backend (each has filename, content_type,
            data, and extracted_text). Takes precedence over file_contents.
        file_contents: Extracted file contents as list of dicts with
            'filename' and 'content' keys (legacy / direct HTTP path).
        rhesis: Optional dict with test execution context
            (test_id, test_run_id, test_configuration_id).

    Returns:
        ChatResponse with message, session_id, context, and metadata
    """
    system_prompt = _optional_string(system_prompt)
    model = _optional_string(model)
    use_case = _optional_string(use_case) or "insurance"
    output_mode = _optional_string(output_mode) or "text"
    context_strategy = _optional_string(context_strategy) or "heuristic"
    temperature = _float_or_default(temperature, 0.7)
    max_tokens = _int_or_default(max_tokens, 1024)

    # Resolve session – reuse existing or create new
    session_id = session_id or str(uuid.uuid4())

    # Use explicit history if provided, otherwise fetch from session.
    # The isinstance guard is necessary because Jinja2 renders
    # ``{{ conversation_history | default(none) }}`` as the *string*
    # ``"None"`` rather than Python ``None``.
    if not isinstance(conversation_history, list):
        try:
            conversation_history = await session_store.get(session_id)
        except Exception:
            logger.warning("Session store unavailable; starting fresh conversation", exc_info=True)
            conversation_history = []

    # Derive file_contents from enriched files when present (connector path).
    # Each file dict from the backend carries an ``extracted_text`` field set
    # by _enrich_files_with_extraction; use that directly.
    if isinstance(files, list) and files:
        logger.info(
            "Received %d file(s) via connector: %s",
            len(files),
            [
                {"name": f.get("filename"), "has_text": bool(f.get("extracted_text"))}
                for f in files
                if isinstance(f, dict)
            ],
        )
        derived = []
        for f in files:
            if not isinstance(f, dict):
                continue
            filename = f.get("filename", "unknown")
            extracted = f.get("extracted_text") or ""
            if extracted.strip():
                derived.append({"filename": filename, "content": extracted})
            else:
                # Extraction produced no text — fall back to local extraction.
                # If local extraction also yields nothing, use an explicit
                # placeholder so the LLM knows a file was attached but its
                # content could not be read (prevents hallucination).
                fallback_content = None
                try:
                    file_input = FileInput(
                        filename=filename,
                        content_type=f.get("content_type"),
                        data=f.get("data", ""),
                        extracted_text=None,
                    )
                    result = extract_file_content(file_input)
                    if result.get("content", "").strip():
                        fallback_content = result["content"]
                        logger.info("Local fallback extraction succeeded for %s", filename)
                    else:
                        logger.info(
                            "Local fallback returned no text for %s; using placeholder",
                            filename,
                        )
                except Exception as exc:
                    logger.warning(
                        "Local fallback extraction failed for %s: %s", filename, exc
                    )
                derived.append({
                    "filename": filename,
                    "content": fallback_content or "[File content could not be extracted]",
                })
        file_contents = derived or None

    # Guard: when no files are present the template renders to an empty string;
    # also handles legacy "None" string from older request mappings.
    if not isinstance(file_contents, list):
        file_contents = None

    _RHESIS_ALLOWED_KEYS = {"test_id", "test_run_id", "test_configuration_id"}
    if not isinstance(rhesis, dict):
        rhesis = None
    else:
        rhesis = {
            k: v
            for k, v in rhesis.items()
            if k in _RHESIS_ALLOWED_KEYS and v and v != "None"
        }
        if not rhesis:
            rhesis = None

    logger.info(f"Rhesis context received: {rhesis}")

    # Echo use case: return input directly without any LLM call
    if use_case == "echo":
        try:
            await session_store.append(
                session_id,
                [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": message},
                ],
            )
        except Exception:
            logger.warning("Failed to persist echo exchange to session store", exc_info=True)
        return ChatResponse(
            message=message,
            session_id=session_id,
            context=[],
            metadata={"use_case": "echo", "output_mode": output_mode},
            tool_calls=[],
        )

    # Create single ResponseGenerator instance to avoid duplicate instantiation
    # This ensures proper trace nesting - all operations under one trace
    response_generator = endpoint_module.get_response_generator(
        use_case,
        system_prompt_override=system_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        context_strategy=context_strategy,
    )
    tool_calls = []

    async def _collect_response():
        chunks = []
        async for chunk in response_generator.stream_assistant_response(
            message,
            conversation_history=conversation_history,
            file_contents=file_contents,
            mode=output_mode,
        ):
            chunks.append(chunk)
        return chunks

    context_fragments, intent_result, chunks = await asyncio.gather(
        response_generator.generate_context(message),
        response_generator.recognize_intent(message),
        _collect_response(),
    )

    if output_mode == "json":
        response_message = chunks[0] if chunks else {}
    else:
        response_message = "".join(chunks)

    tool_calls.extend([
        {
            "name": "generate_context",
            "arguments": {"message": message},
            "result": context_fragments,
        },
        {
            "name": "recognize_intent",
            "arguments": {"message": message},
            "result": intent_result,
        },
        {
            "name": "generate_response",
            "arguments": {
                "message": message,
                "output_mode": output_mode,
                "has_file_contents": file_contents is not None,
                "history_length": len(conversation_history),
            },
            "result": {"length": len(str(response_message))},
        },
    ])

    # Persist the exchange in the session store
    try:
        await session_store.append(
            session_id,
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response_message},
            ],
        )
    except Exception:
        logger.warning("Failed to persist exchange to session store", exc_info=True)

    # Return Pydantic model
    return ChatResponse(
        message=response_message,
        session_id=session_id,
        context=context_fragments,
        metadata={
            "use_case": use_case,
            "output_mode": output_mode,
            "intent": intent_result,
            "rhesis": rhesis,
        },
        tool_calls=tool_calls,
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and load balancer."""
    return {"status": "healthy", "service": "rhesis-insurance-chatbot", "version": "1.0.0"}


@app.get("/")
async def root(request: Request, auth: dict = Depends(verify_api_key)):
    """Root endpoint with API information."""
    return {
        "service": "Rhesis Insurance Chatbot API",
        "description": "Chat with Rosalind, your insurance expert",
        "authentication": {
            "status": "authenticated" if auth["authenticated"] else "public",
            "tier": auth["tier"],
        },
        "endpoints": {
            "chat": "/chat (POST)",
            "health": "/health (GET)",
            "use_cases": "/use-cases (GET)",
            "session": "/sessions/{session_id} (GET, DELETE)",
        },
        "rate_limits": {
            "authenticated": f"{TOTAL_RATE_LIMIT_AUTHENTICATED} requests per day per user",
            "public": f"{TOTAL_RATE_LIMIT_PUBLIC} requests per day per IP address",
            "current_tier": auth["tier"],
        },
    }


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: Request, chat_request: ChatRequest, auth: dict = Depends(check_rate_limit_chatbot)
):
    try:
        logger.info(
            f"Chat request received - Auth tier: {auth['tier']}, "
            f"Message: {chat_request.message[:50]}..."
        )
        
        # Resolve parameters from Rhesis (or fallback to env/defaults).
        # Run in a thread executor because Parameters.get() uses synchronous
        # requests and would otherwise block the async event loop.
        loop = asyncio.get_event_loop()
        params = await loop.run_in_executor(None, _resolve_chatbot_params)
        request_param_overrides = {
            "system_prompt": chat_request.system_prompt,
            "model": chat_request.model,
            "temperature": chat_request.temperature,
            "max_tokens": chat_request.max_tokens,
            "context_strategy": chat_request.context_strategy,
        }
        params.update(
            {
                key: value
                for key, value in request_param_overrides.items()
                if not _is_absent_value(value)
            }
        )

        # Validate use case exists, default to insurance if not
        # The request payload overrides the resolved parameter if provided
        use_case = chat_request.use_case or params.get("use_case") or "insurance"
        available_use_cases = get_available_use_cases() + ["echo"]
        if use_case not in available_use_cases:
            use_case = "insurance"
            
        output_mode = chat_request.mode or params.get("output_mode", "text")

        # Extract file contents if provided
        file_contents = None
        if chat_request.files:
            file_contents = []
            for file_input in chat_request.files:
                try:
                    file_contents.append(extract_file_content(file_input))
                except Exception as e:
                    logger.warning(f"Failed to extract content from {file_input.filename}: {e}")

        # Session management and history are handled inside chat()
        result = await chat(
            message=chat_request.message,
            session_id=chat_request.session_id,
            system_prompt=params.get("system_prompt"),
            use_case=use_case,
            model=params.get("model"),
            temperature=params.get("temperature", 0.7),
            max_tokens=params.get("max_tokens", 1024),
            output_mode=output_mode,
            context_strategy=params.get("context_strategy", "heuristic"),
            file_contents=file_contents,
            rhesis=chat_request.rhesis,
        )

        logger.info(f"Response generated successfully - Length: {len(result.message)} chars")

        return result

    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}")
async def get_session(
    request: Request, session_id: str, auth: dict = Depends(check_rate_limit_chatbot)
):
    if not await session_store.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "messages": await session_store.get(session_id),
        "ttl_hours": SESSION_TIMEOUT_HOURS,
    }


@app.delete("/sessions/{session_id}")
async def delete_session(
    request: Request, session_id: str, auth: dict = Depends(check_rate_limit_chatbot)
):
    if not await session_store.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    logger.info(f"🗑️ Manually deleted session: {session_id}")
    return {"message": "Session deleted"}


@app.get("/use-cases")
async def list_use_cases(request: Request, auth: dict = Depends(check_rate_limit_chatbot)):
    """Get list of available use cases"""
    try:
        use_cases = get_available_use_cases()
        return {"use_cases": use_cases}
    except Exception as e:
        return {"use_cases": ["insurance"], "error": str(e)}
