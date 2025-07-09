import os
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException
from rhesis.backend.logging import logger

# OAuth configuration
oauth = OAuth()
oauth.register(
    "auth0",
    client_id=os.getenv("AUTH0_CLIENT_ID"),
    client_secret=os.getenv("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f"https://{os.getenv('AUTH0_DOMAIN')}/.well-known/openid-configuration",
)

async def get_auth0_user_info(request):
    """Get user information from Auth0"""
    try:
        token = await oauth.auth0.authorize_access_token(request)
        userinfo = await oauth.auth0.userinfo(token=token)
        return token, userinfo
    except Exception as e:
        logger.error(f"Error getting Auth0 user info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))

def extract_user_data(userinfo):
    """Extract and normalize user data from Auth0 userinfo"""
    # Extract basic user information
    auth0_id = userinfo.get("sub")
    email = userinfo.get("email")

    # Create user profile dictionary
    user_profile = {
        "name": userinfo.get("name"),
        "given_name": userinfo.get("given_name"),
        "family_name": userinfo.get("family_name"),
        "picture": userinfo.get("picture"),
    }

    # Handle missing email for GitHub users
    if not email and auth0_id:
        email = _generate_placeholder_email(auth0_id)

    return auth0_id, email, user_profile

def _generate_placeholder_email(auth0_id):
    """Generate a placeholder email for users without an email"""
    provider_parts = auth0_id.split("|")

    if len(provider_parts) == 2 and provider_parts[0] == "github":
        github_id = provider_parts[1]
        email = f"github-user-{github_id}@placeholder.rhesis.ai"
        logger.info(f"Created placeholder email for GitHub user: {email}")
    else:
        # For other providers with missing email
        email = f"user-{auth0_id.replace('|', '-')}@placeholder.rhesis.ai"
        logger.info(f"Created placeholder email for user: {email}")

    # Ensure we have an email (last resort fallback)
    if not email:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        email = f"unknown-user-{timestamp}@placeholder.rhesis.ai"
        logger.warning(f"No email provided, using generated placeholder: {email}")

    return email 