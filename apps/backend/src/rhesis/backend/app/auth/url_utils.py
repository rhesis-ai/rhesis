from urllib.parse import parse_qs, urlparse

from rhesis.backend.app.auth.token_utils import create_auth_code
from rhesis.backend.app.config.settings import (
    get_application_settings,
    get_frontend_settings,
)

# Loopback hostnames accepted as redirect targets in development. Matched
# exactly against ``urlparse(...).hostname`` so that lookalikes such as
# ``evil-localhost.com`` or ``localhost.attacker.com`` cannot slip through.
_LOOPBACK_HOSTNAMES = frozenset(("localhost", "127.0.0.1", "::1"))


async def build_redirect_url(request, session_token, refresh_token=None):
    """Build the redirect URL with a short-lived auth code.

    The auth code is a 60-second, single-use OPAQUE reference; the tokens
    it points to are stored server-side (see ``create_auth_code``). The
    frontend exchanges it via POST /auth/exchange-code, keeping the
    long-lived tokens out of URLs, browser history, and logs.
    """
    # Get the original frontend URL from session or fallback to env
    original_frontend = request.session.get("original_frontend")
    frontend_settings = get_frontend_settings()
    frontend_url = frontend_settings.url

    if original_frontend:
        parsed_origin = urlparse(original_frontend)
        # Exact netloc match to prevent open redirects.
        if parsed_origin.netloc == frontend_settings.allowed_domain:
            frontend_url = f"{parsed_origin.scheme}://{parsed_origin.netloc}"
        elif _is_loopback_dev_origin(parsed_origin):
            # Dev-only escape hatch: a frontend running on the developer's
            # loopback (e.g. ``http://localhost:3000``) is allowed to point
            # at a remote dev backend and still receive the redirect back.
            # Dev-only: gated on BACKEND_ENV so production never honours
            # loopback origins regardless of the Origin/Referer the browser
            # sent on /auth/login/{provider}.
            frontend_url = f"{parsed_origin.scheme}://{parsed_origin.netloc}"

        # Clean up session
        request.session.pop("original_frontend", None)

    # Get return_to path from session or default to architect
    return_to = request.session.get("return_to", "/architect")
    request.session.pop("return_to", None)

    # Parse return_to if it's a full URL and extract just the path
    if return_to.startswith("http"):
        parsed = urlparse(return_to)
        # Extract path and query parameters if any
        return_to = parsed.path
        if parsed.query:
            query_params = parse_qs(parsed.query)
            if "return_to" in query_params:
                # Get the actual destination from nested return_to
                return_to = query_params["return_to"][0]

    # Ensure return_to starts with a slash
    return_to = f"/{return_to.lstrip('/')}"

    # Create a short-lived opaque auth code referencing both tokens
    code = await create_auth_code(session_token, refresh_token)

    final_url = f"{frontend_url.rstrip('/')}/auth/signin"
    final_url = f"{final_url}?code={code}&return_to={return_to}"

    return final_url


def _is_loopback_dev_origin(parsed_origin) -> bool:
    """Return True only for safe loopback origins on dev backends.

    Three independent conditions must all hold:

    * The deployment is **not** production (``BACKEND_ENV`` is not
      ``production``). Production deployments never accept loopback origins,
      regardless of what the browser sent.
    * The hostname is an exact match against the loopback whitelist.
      ``urlparse`` lowercases the hostname and strips the port, so
      ``LocalHost:3000`` and ``localhost:9999`` both reduce to
      ``localhost``; lookalikes such as ``evil-localhost.com`` or
      ``localhost.attacker.com`` do not.
    * The scheme is ``http`` or ``https``. This rejects pathological
      values such as ``javascript:`` if they ever appear in a Referer.
    """
    if not get_application_settings().is_development:
        return False
    if parsed_origin.scheme not in ("http", "https"):
        return False
    return (parsed_origin.hostname or "").lower() in _LOOPBACK_HOSTNAMES
