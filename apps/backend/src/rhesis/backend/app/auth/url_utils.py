import os
from urllib.parse import parse_qs, urlparse

from rhesis.backend.app.auth.constants import FRONTEND_DOMAINS
from rhesis.backend.app.auth.token_utils import create_auth_code


def build_redirect_url(request, session_token, refresh_token=None):
    """Build the redirect URL with a short-lived auth code.

    The auth code is a 60-second JWT that wraps both the access token
    and the refresh token.  The frontend exchanges it via
    POST /auth/exchange-code, keeping the long-lived tokens out of URLs.
    """
    # Get the original frontend URL from session or fallback to env
    original_frontend = request.session.get("original_frontend")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    if original_frontend:
        parsed_origin = urlparse(original_frontend)
        # Exact hostname/netloc match to prevent open redirect
        if parsed_origin.hostname == "localhost":
            frontend_url = f"{parsed_origin.scheme}://{parsed_origin.netloc}"
        elif parsed_origin.netloc in FRONTEND_DOMAINS:
            frontend_url = f"{parsed_origin.scheme}://{parsed_origin.netloc}"

        # Clean up session
        request.session.pop("original_frontend", None)

    # Get return_to path from session or default to dashboard
    return_to = request.session.get("return_to", "/dashboard")
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

    # Create a short-lived auth code wrapping both tokens
    code = create_auth_code(session_token, refresh_token)

    final_url = f"{frontend_url.rstrip('/')}/auth/signin"
    final_url = f"{final_url}?code={code}&return_to={return_to}"

    return final_url
