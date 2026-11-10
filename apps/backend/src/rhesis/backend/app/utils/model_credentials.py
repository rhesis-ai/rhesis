"""Which credential each SDK provider class reads from a tenant's Model row.

Every SDK provider reads its credential from the process environment when it
is not handed one (``OPENAI_API_KEY``, ``GOOGLE_APPLICATION_CREDENTIALS``, ...).
A tenant row is stamped ``metered=False`` because it is meant to run on the
tenant's own credentials, so the check has to be made against the field the
provider class actually consumes, not just any non-empty field on the row.
"""

import base64
import binascii
import json
from typing import Any, Optional

# Rhesis-hosted: running on our credentials is what picking them means, and they are metered.
HOSTED_PROVIDERS = frozenset({"rhesis", "polyphemus"})

# Served from the tenant's own server: the endpoint is what makes the row theirs, and
# without one these fall back to an env or localhost base on our side.
ENDPOINT_PROVIDERS = frozenset(
    {"ollama", "vllm", "litellm_proxy", "huggingface", "lmformatenforcer"}
)

# Endpoint providers that read an env key when given none (HOSTED_VLLM_API_KEY,
# LITELLM_PROXY_API_KEY) and would send it to the tenant's endpoint.
_ENV_KEY_ENDPOINT_PROVIDERS = frozenset({"vllm", "litellm_proxy"})

# LiteLLM's own stand-in for a keyless server (litellm/llms/hosted_vllm); any non-empty
# value stops the env read.
KEYLESS_SERVER_KEY = "fake-api-key"

# VertexAILLM/VertexAIEmbedder drop ``api_key`` and read a service-account JSON from
# ``credentials``, falling back to GOOGLE_APPLICATION_CREDENTIALS.
SERVICE_ACCOUNT_PROVIDERS = frozenset({"vertex_ai"})

_SERVICE_ACCOUNT_FIELDS = ("project_id", "private_key", "client_email")


def _clean(value: Optional[str]) -> Optional[str]:
    return (value or "").strip() or None


def vertex_service_account(key: Optional[str]) -> Optional[dict[str, Any]]:
    """The service-account JSON a vertex_ai row carries as its key, or None.

    Accepts the JSON itself or base64 of it. Never a file path: the SDK would
    read that file from this server, which is where our own credentials live.
    """
    key = _clean(key)
    if key is None:
        return None
    raw = key
    if not key.startswith("{"):
        try:
            raw = base64.b64decode(key, validate=True).decode("utf-8")
        except (binascii.Error, ValueError):
            return None
    try:
        info = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(info, dict) or info.get("type") != "service_account":
        return None
    if not all(isinstance(info.get(f), str) and info[f].strip() for f in _SERVICE_ACCOUNT_FIELDS):
        return None
    return info


def has_own_credentials(provider: str, api_key: Optional[str], endpoint: Optional[str]) -> bool:
    """Whether the provider will run this row on the row's own credential."""
    if provider in HOSTED_PROVIDERS:
        return True
    if provider in SERVICE_ACCOUNT_PROVIDERS:
        return vertex_service_account(api_key) is not None
    if provider in ENDPOINT_PROVIDERS:
        return _clean(endpoint) is not None
    # Every other provider ignores ``api_base`` for auth and reads its key from env.
    return _clean(api_key) is not None


def credential_requirement(provider: str) -> str:
    """What a row for *provider* must carry, for error messages."""
    if provider in SERVICE_ACCOUNT_PROVIDERS:
        return "a service-account JSON key (as JSON or base64) in the API key field"
    if provider in ENDPOINT_PROVIDERS:
        return "an endpoint"
    return "an API key"


def tenant_model_kwargs(
    provider: str, api_key: Optional[str], endpoint: Optional[str]
) -> dict[str, Any]:
    """``get_model`` kwargs that hand the provider the row's own credential.

    Callers check :func:`has_own_credentials` first; a vertex_ai row without a
    usable service account raises here rather than reaching the env fallback.
    """
    if provider in SERVICE_ACCOUNT_PROVIDERS:
        info = vertex_service_account(api_key)
        if info is None:
            raise ValueError(f"vertex_ai needs {credential_requirement(provider)}")
        return {
            "api_key": None,
            "credentials": base64.b64encode(json.dumps(info).encode("utf-8")).decode("ascii"),
            "project": info["project_id"],
        }
    key = _clean(api_key)
    if key is None and provider in _ENV_KEY_ENDPOINT_PROVIDERS:
        key = KEYLESS_SERVER_KEY
    kwargs: dict[str, Any] = {"api_key": key}
    if _clean(endpoint):
        kwargs["api_base"] = _clean(endpoint)
    return kwargs
