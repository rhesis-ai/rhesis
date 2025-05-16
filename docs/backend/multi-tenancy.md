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
        org_id = _current_tenant_organization_id.get()
        user_id = _current_tenant_user_id.get()
        _execute_set_tenant(dbapi_connection, org_id, user_id)
    except Exception as e:
        logger.debug(f"Error in _set_tenant_for_connection: {e}")
```

### Context Maintenance

A context manager ensures tenant context is maintained across transactions:

```python
@contextmanager
def maintain_tenant_context(session: Session):
    """Maintain the tenant context across a transaction."""
    # Store current context
    try:
        prev_org_id = _current_tenant_organization_id.get()
        prev_user_id = _current_tenant_user_id.get()
    except Exception:
        prev_org_id = None
        prev_user_id = None

    try:
        # Set context before the operation
        set_tenant(session, prev_org_id, prev_user_id)
        yield
    except Exception:
        if session.in_transaction():
            session.rollback()
        raise
    finally:
        try:
            # Clean up tenant context
            _execute_set_tenant(session, None, None)
        except Exception as e:
            logger.debug(f"Error in maintain_tenant_context cleanup: {e}")
```

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