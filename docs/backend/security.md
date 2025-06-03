# Security Features

## Overview

The Rhesis backend implements multiple layers of security to protect sensitive data and ensure secure access to the API. This document outlines the key security features and best practices implemented in the application.

## Authentication and Authorization

### Auth0 Integration

The application uses Auth0 as the identity provider, which offers:

- Secure user authentication
- Multi-factor authentication (MFA)
- Social login integration
- Centralized user management
- Security monitoring and anomaly detection

### JWT Token Security

JSON Web Tokens (JWTs) are used for API authentication:

- Tokens are signed using a secure algorithm (HS256)
- Tokens have a configurable expiration time
- Token validation checks for tampering and expiration
- Sensitive operations require fresh authentication

### Session Security

For web UI users, the application uses secure session management:

- Sessions are encrypted using a secret key
- Session data is stored server-side
- Session cookies use secure and HTTP-only flags
- Sessions have a configurable expiration time

## Multi-tenancy and Data Isolation

### Row-Level Security

The application implements PostgreSQL row-level security to ensure complete data isolation between organizations:

- Each request is associated with an organization context
- Database queries automatically filter data based on the organization
- Direct database access bypassing the application cannot access unauthorized data

### Organization-Specific Resources

Resources are scoped to organizations:

- Users belong to a single organization
- Resources created by users are associated with their organization
- Cross-organization access is strictly controlled

## API Security

### CORS Protection

Cross-Origin Resource Sharing (CORS) is configured to prevent unauthorized cross-origin requests:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://app.rhesis.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Test-Header"],
)
```

### HTTPS Enforcement

HTTPS is enforced for all communications:

```python
class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if "X-Forwarded-Proto" in request.headers:
            request.scope["scheme"] = request.headers["X-Forwarded-Proto"]
        return await call_next(request)
```

### Rate Limiting

API rate limiting protects against abuse and DoS attacks:

- Limits are applied per IP address and/or API key
- Different limits for authenticated and unauthenticated requests
- Graduated response to excessive requests (warning, temporary block, permanent block)

## Data Security

### Password Security

User passwords are managed securely:

- Passwords are never stored in the database (delegated to Auth0)
- Password reset flows follow security best practices
- Password strength requirements are enforced

### Sensitive Data Handling

Sensitive data is handled with care:

- API keys and secrets are stored securely
- Sensitive data is encrypted at rest
- Logging filters out sensitive information
- Environment variables are used for configuration instead of hardcoded values

### Database Security

The database is secured through multiple measures:

- Connection strings use least-privilege accounts
- Database credentials are not exposed to clients
- Prepared statements prevent SQL injection
- Database connections are encrypted

## Logging and Monitoring

### Security Logging

Security events are logged for monitoring and auditing:

- Authentication attempts (successful and failed)
- Access to sensitive resources
- Administrative actions
- Changes to security settings

### Error Handling

Errors are handled securely:

- Detailed error information is not exposed to clients
- Errors are logged for investigation
- Generic error messages are returned to users

## Code Security

### Dependency Management

Dependencies are managed securely:

- Regular updates to address security vulnerabilities
- Dependency scanning for known vulnerabilities
- Pinned dependency versions for reproducible builds

### Security Headers

The application sets security headers to protect against common web vulnerabilities:

- Content-Security-Policy
- X-Content-Type-Options
- X-Frame-Options
- X-XSS-Protection

## Deployment Security

### Container Security

When deployed in containers:

- Non-root users run the application
- Minimal base images reduce attack surface
- Read-only file systems where possible
- Container security scanning

### Environment Isolation

Different environments are isolated:

- Development, testing, and production environments are separated
- Production credentials are not used in development
- Strict access controls for production environments 