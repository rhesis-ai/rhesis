# API Structure

## Overview

The Rhesis backend API is built with FastAPI and follows RESTful principles. The API endpoints are organized into routers, each handling a specific resource type.

## Router Organization

All API routers are defined in the `app/routers/` directory. The application includes over 30 routers for different entities, including:

- Authentication
- Users and Organizations
- Tests and Test Sets
- Prompts and Templates
- Models and Endpoints
- Categories and Tags

## Route Categories

Routes are categorized based on authentication requirements:

### Public Routes

These routes don't require any authentication:

```python
public_routes = [
    "/",
    "/auth/login",
    "/auth/callback",
    "/auth/logout",
    "/home",
    "/docs",
    "/redoc",
    "/openapi.json",
]
```

### Token-Enabled Routes

These routes accept both session and token authentication:

```python
token_enabled_routes = [
    "/api/",
    "/tokens/",
    "/test_sets/",
    "/topics/",
    "/prompts/",
    # ...and many more
]
```

### Session-Only Routes

All other routes require session-based authentication.

## Custom Route Class

The application uses a custom `AuthenticatedAPIRoute` class that automatically adds the appropriate authentication dependencies based on the route path:

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

## Standard Endpoints

Most resource routers follow a standard pattern with these endpoints:

### Read Operations

- `GET /{resource}/`: List all resources (with filtering and pagination)
- `GET /{resource}/{id}`: Get a specific resource by ID
- `GET /{resource}/count`: Get the count of resources

### Write Operations

- `POST /{resource}/`: Create a new resource
- `PUT /{resource}/{id}`: Update a resource
- `DELETE /{resource}/{id}`: Delete a resource

## Example Router

Here's a simplified example of a router structure:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.database import get_db
from rhesis.backend.app.schemas import TestCreate, TestUpdate, Test
from rhesis.backend.app.crud import create_test, get_test, update_test, delete_test

router = APIRouter(
    prefix="/tests",
    tags=["tests"],
)

@router.post("/", response_model=Test)
def create_test_endpoint(test: TestCreate, db: Session = Depends(get_db)):
    return create_test(db=db, test=test)

@router.get("/{test_id}", response_model=Test)
def read_test(test_id: str, db: Session = Depends(get_db)):
    db_test = get_test(db, test_id=test_id)
    if db_test is None:
        raise HTTPException(status_code=404, detail="Test not found")
    return db_test

# Additional endpoints...
```

## Query Parameters

The API supports various query parameters for filtering, sorting, and pagination:

### Filtering

OData-style filtering is supported:

```
GET /tests/?$filter=prompt_id eq '89905869-e8e9-4b2f-b362-3598cfe91968'
```

### Sorting

```
GET /tests/?$orderby=created_at desc
```

### Pagination

```
GET /tests/?$skip=10&$top=10
```

## Response Headers

The API includes helpful response headers:

- `X-Total-Count`: Total number of items for paginated responses
- Standard CORS headers for cross-origin requests

## API Documentation

The API documentation is automatically generated using FastAPI's built-in support for OpenAPI:

- Swagger UI: Available at `/docs`
- ReDoc: Available at `/redoc`
- OpenAPI JSON: Available at `/openapi.json`

## Error Handling

The API uses standard HTTP status codes for error responses:

- 400: Bad Request (invalid input)
- 401: Unauthorized (authentication required)
- 403: Forbidden (insufficient permissions)
- 404: Not Found (resource doesn't exist)
- 500: Internal Server Error (server-side error)

Error responses include a JSON body with details about the error. 