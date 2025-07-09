import os
from urllib.parse import parse_qs, urlparse

from rhesis.backend.app.auth.constants import FRONTEND_DOMAINS

def build_redirect_url(request, session_token):
    """Build the redirect URL with session token"""
    # Get the original frontend URL from session or fallback to environment variable
    original_frontend = request.session.get("original_frontend")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    if original_frontend:
        parsed_origin = urlparse(original_frontend)
        # Check if origin is localhost (any port) or matches allowed domains
        if "localhost" in parsed_origin.netloc:
            frontend_url = f"{parsed_origin.scheme}://{parsed_origin.netloc}"
        elif any(domain in parsed_origin.netloc for domain in FRONTEND_DOMAINS):
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

    # Redirect to signin page with session token and clean return_to
    final_url = f"{frontend_url.rstrip('/')}/auth/signin"
    final_url = f"{final_url}?session_token={session_token}&return_to={return_to}"

    return final_url 