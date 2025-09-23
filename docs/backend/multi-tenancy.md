# Multi-tenancy

## Overview

The Rhesis backend implements a robust multi-tenancy model that ensures complete data isolation between different organizations. This is achieved through a combination of database design, row-level security policies, and session context management.

## Multi-tenant Database Design

### Organization Model

The foundation of multi-tenancy is the `Organization` model:

```python
class Organization(Base):
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    # Additional fields...
```

### Organization References

Most models include a reference to the organization they belong to:

```python
class SomeModel(Base):
    # ...other fields
    organization_id = Column(GUID(), ForeignKey("organization.id"))
    organization = relationship("Organization")
```

## PostgreSQL Row-Level Security

The application leverages PostgreSQL's row-level security (RLS) features to enforce data isolation at the database level.

### Session Variables

Two PostgreSQL session variables are used to track the current tenant context:

- `app.current_organization`: The ID of the current organization
- `app.current_user`: The ID of the current user

### Setting Tenant Context

The tenant context is set during request processing:

```python
def set_tenant(
    session: Session, organization_id: Optional[str] = None, user_id: Optional[str] = None
):
    """Set PostgreSQL session variables for row-level security."""
    try:
        # Store in context vars
        if organization_id is not None:
            _current_tenant_organization_id.set(organization_id)
        if user_id is not None:
            _current_tenant_user_id.set(user_id)

        # Set PostgreSQL session variables
        _execute_set_tenant(session, organization_id, user_id)
    except Exception as e:
        logger.debug(f"Error in set_tenant: {e}")
```

### Context Variables

Python's `ContextVar` is used to maintain tenant context across async operations:

```python
_current_tenant_organization_id: ContextVar[Optional[str]] = ContextVar(
    "organization_id", default=None
)
_current_tenant_user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
```

## Database Connection Management

### Connection Event Listeners

The application registers event listeners to set tenant context on new database connections:

```python
@event.listens_for(engine, "connect")
def _set_tenant_for_connection(dbapi_connection, connection_record):
    """Set tenant context for new connections"""
    try:
        organization_id = _current_tenant_organization_id.get()
        user_id = _current_tenant_user_id.get()
        _execute_set_tenant(dbapi_connection, organization_id, user_id)
    except Exception as e:
        logger.debug(f"Error in _set_tenant_for_connection: {e}")
```

### Context Maintenance

A context manager ensures tenant context is maintained across transactions using `SET LOCAL` for transaction-scoped variables:

```python
@contextmanager
def get_db_with_tenant_context(organization_id: str, user_id: str):
    """
    Context manager for organization-aware database operations.
    
    Uses SET LOCAL for transaction-scoped variables and automatic transaction management.
    This approach eliminates connection pooling issues and provides cleaner error handling.
    """
    # Get database session
    db = next(get_db())
    
    try:
        # Begin transaction
        with db.begin():
            # Set tenant context using SET LOCAL (transaction-scoped)
            db.execute(text("SET LOCAL app.current_organization = :organization_id"), {"organization_id": organization_id})
            db.execute(text("SET LOCAL app.current_user = :user_id"), {"user_id": user_id})
            
            yield db
            
            # Transaction is automatically committed by db.begin() on success
    except Exception:
        # Transaction is automatically rolled back by db.begin() on exception
        raise
    finally:
        # Session cleanup
        db.close()
```

**Key improvements over the previous approach:**

- **`SET LOCAL`**: Variables are automatically scoped to the transaction and cleared when it ends
- **Automatic transaction management**: `db.begin()` handles commit/rollback automatically  
- **No connection pooling issues**: Each context gets a fresh session
- **Cleaner error handling**: No need for manual cleanup in finally blocks
- **Better isolation**: Transaction-scoped variables prevent context leakage

### Usage Patterns

**For multi-entity operations (recommended):**
```python
# Use get_db and pass tenant context directly to CRUD operations
def load_initial_data(organization_id: str, user_id: str):
    with get_db() as db:
        # Pass tenant context directly to CRUD operations
        create_statuses(db, initial_data["status"], organization_id=organization_id, user_id=user_id)
        create_behaviors(db, initial_data["behavior"], organization_id=organization_id, user_id=user_id)
        # Automatic commit on success, rollback on exception
```

**For API request handling:**
```python
# Standard dependency injection for regular API endpoints
async def get_tests(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_current_user)
):
    # Tenant context is set by require_current_user dependency
    return crud.get_tests(db)
```

**When to use each approach:**

- **`get_db` with direct parameters**: Multi-entity operations, background tasks, data migrations, initial data loading
- **Standard dependencies**: Regular API endpoints where tenant context is set by authentication middleware

## Authentication Integration

The multi-tenancy system integrates with authentication to set tenant context based on the authenticated user:

```python
async def require_current_user(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Set tenant context for database operations
    set_tenant(db, user.get("organization_id"), user.get("sub"))
    
    return user
```

## API Request Flow

1. Client makes a request to a protected endpoint
2. Authentication middleware validates the request
3. Current user and organization are extracted from the authentication context
4. Tenant context is set in the database session
5. Database queries automatically filter data based on the tenant context
6. After the request completes, tenant context is cleared

## Benefits of This Approach

1. **Security**: Data isolation is enforced at the database level
2. **Simplicity**: Application code doesn't need to filter by organization
3. **Performance**: Database indexes can be optimized for tenant-based queries
4. **Compliance**: Helps meet data segregation requirements for regulatory compliance

## Superuser Access

Superusers can access data across organizations by bypassing the row-level security policies:

```python
def bypass_rls(db: Session):
    """Temporarily bypass row-level security for superuser operations."""
    db.execute(text("SET app.bypass_rls = true"))
```

This feature is carefully controlled and only available to authenticated superusers. 