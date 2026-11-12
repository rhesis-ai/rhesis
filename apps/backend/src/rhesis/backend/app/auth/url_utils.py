from urllib.parse import parse_qs, quote, urlparse, urlsplit

from rhesis.backend.app.auth.token_utils import create_auth_code
from rhesis.backend.app.config.settings import get_frontend_settings

LOOPBACK_HOSTS = frozenset(("localhost", "127.0.0.1", "::1"))

DEFAULT_RETURN_TO = "/architect"


def safe_return_path(value: object, default: str = DEFAULT_RETURN_TO) -> str:
    """Return ``value`` if it is a same-origin relative path, else ``default``.

    Browsers treat ``\\`` as ``/`` and drop tabs/newlines, so ``/\\host`` or
    ``/<TAB>/host`` would navigate off-origin. Reject backslashes and control
    characters outright rather than trying to normalise them.
    """
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        return default
    if "\\" in value or any(ord(c) < 0x20 or ord(c) == 0x7F for c in value):
        return default
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return default
    return value


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
        configured = urlparse(frontend_settings.url)
        if parsed_origin.netloc == frontend_settings.allowed_domain:
            frontend_url = f"{parsed_origin.scheme}://{parsed_origin.netloc}"
        elif configured.hostname in LOOPBACK_HOSTS and parsed_origin.hostname in LOOPBACK_HOSTS:
            # Dev/worktree: the browser's port may differ from the configured
            # FRONTEND_URL when a port offset is active. Both are loopback, so
            # this cannot redirect off-box.
            frontend_url = f"{parsed_origin.scheme}://{parsed_origin.netloc}"

        # Clean up session
        request.session.pop("original_frontend", None)

    return_to = request.session.pop("return_to", None) or DEFAULT_RETURN_TO

    # Parse return_to if it's a full URL and extract just the path
    if isinstance(return_to, str) and return_to.startswith("http"):
        parsed = urlparse(return_to)
        # Extract path and query parameters if any
        return_to = parsed.path
        if parsed.query:
            query_params = parse_qs(parsed.query)
            if "return_to" in query_params:
                # Get the actual destination from nested return_to
                return_to = query_params["return_to"][0]

    return_to = safe_return_path(return_to)

    # Create a short-lived opaque auth code referencing both tokens
    code = await create_auth_code(session_token, refresh_token)

    final_url = f"{frontend_url.rstrip('/')}/auth/signin"
    final_url = f"{final_url}?code={quote(code, safe='')}&return_to={quote(return_to, safe='/')}"

    return final_url
