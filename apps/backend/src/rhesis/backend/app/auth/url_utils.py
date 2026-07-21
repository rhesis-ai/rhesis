from urllib.parse import parse_qs, urlparse

from rhesis.backend.app.auth.token_utils import create_auth_code
from rhesis.backend.app.config.settings import get_frontend_settings


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
