# Authentication

## Overview

The Rhesis backend implements a comprehensive authentication system using Auth0 as the identity provider. The system supports both session-based authentication for web UI users and token-based authentication for API access.

## Authentication Methods

### Session-Based Authentication

Session-based authentication is used for web UI users:

1. User is redirected to Auth0 login page
2. After successful authentication, Auth0 redirects back to the application
3. A session is created and maintained using cookies
4. Session middleware manages the user's session state

### Token-Based Authentication

Token-based authentication is used for API access:

1. Client obtains a JWT token (either from Auth0 or through the `/tokens/` endpoint)
2. Client includes the token in the `Authorization` header with each request
3. The backend validates the token and extracts user information

## Auth0 Integration

The application integrates with Auth0 for identity management:

```python
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
```

### Login Flow

1. User accesses `/auth/login`
2. Backend redirects to Auth0 authorization URL
3. User authenticates with Auth0
4. Auth0 redirects back to `/auth/callback` with an authorization code
5. Backend exchanges the code for tokens
6. User information is stored in the session

```python
@router.get("/login")
async def login(request: Request):
    redirect_uri = request.url_for("auth_callback")
    return await oauth.auth0.authorize_redirect(request, redirect_uri)

@router.get("/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.auth0.authorize_access_token(request)
    user_info = token.get("userinfo")
    
    # Store user info in session
    request.session["user"] = dict(user_info)
    
    # Create or update user in database
    # ...
    
    return RedirectResponse(url=FRONTEND_URL)
```

## Authentication Middleware

The application uses a custom route class to enforce authentication requirements:

```python
class AuthenticatedAPIRoute(APIRoute):
    def get_dependencies(self):
        if self.path in public_routes:
            # No auth required
            return []
        elif any(self.path.startswith(route) for route in token_enabled_routes):
            # Both session and token auth accepted
            return [Depends(require_current_user_or_token)]
        # Default to session-only auth
        return [Depends(require_current_user)]
```

## Authentication Dependencies

The application defines several authentication dependencies:

### `require_current_user`

Requires a valid user session:

```python
async def require_current_user(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Set tenant context for database operations
    set_tenant(db, user.get("organization_id"), user.get("sub"))
    
    return user
```

### `require_current_user_or_token`

Accepts either a valid user session or a valid token:

```python
async def require_current_user_or_token(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    try:
        # First try token authentication
        payload = verify_token(token)
        # Set tenant context for database operations
        set_tenant(db, payload.get("organization_id"), payload.get("sub"))
        return payload
    except:
        # Fall back to session authentication
        return await require_current_user(request, db)
```

## JWT Tokens

The application uses JWT tokens for API authentication:

### Token Generation

```python
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt
```

### Token Validation

```python
def verify_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

## Logout

The logout process invalidates the user's session:

```python
@router.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url=FRONTEND_URL)
```

## Security Considerations

- HTTPS is enforced for all communications
- Tokens have a configurable expiration time
- Session data is encrypted using a secret key
- Auth0's security features protect against common attacks
- CORS is configured to allow only specific origins 