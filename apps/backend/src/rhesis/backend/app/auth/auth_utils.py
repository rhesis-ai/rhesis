"""Backward-compatible re-exports from canonical auth modules.

All auth logic now lives in:
- token_utils.py — token creation and verification
- user_utils.py — user authentication (get_current_user, require_*, etc.)
- token_validation.py — API bearer token validation

This module re-exports symbols so that existing imports continue to work.
New code should import from the canonical modules directly.
"""

# Token utilities
from rhesis.backend.app.auth.token_utils import (  # noqa: F401
    generate_api_token,
    get_secret_key,
    verify_jwt_token,
)

# Token validation
from rhesis.backend.app.auth.token_validation import (  # noqa: F401
    update_token_usage,
    validate_token,
)

# User utilities
from rhesis.backend.app.auth.user_utils import (  # noqa: F401
    get_authenticated_user_with_context,
    get_current_user,
    get_user_from_jwt,
    require_current_user,
    require_current_user_or_token,
    require_current_user_or_token_without_context,
)
