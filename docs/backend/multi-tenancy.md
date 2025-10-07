# Multi-tenancy

## Overview

The Rhesis backend implements a robust multi-tenancy model that ensures complete data isolation between different organizations. This is achieved through a combination of database design, explicit parameter passing, and organization filtering in CRUD operations.

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

## Direct Parameter Passing Architecture

The application uses **direct parameter passing** for tenant context instead of session variables, providing better performance and security.

### Tenant Context Extraction

Tenant context is extracted from authenticated users and passed directly to CRUD operations:

```python
def get_tenant_context(current_user: User = Depends(require_current_user_or_token)):
    """Extract tenant context from authenticated user."""
    return current_user.organization_id, current_user.id
```

### CRUD Operations with Tenant Context

All CRUD operations accept `organization_id` and `user_id` parameters explicitly:

```python
def create_entity(
    db: Session, 
    entity_data: EntityCreate, 
    organization_id: str, 
    user_id: str
) -> Entity:
    """Create entity with explicit tenant context."""
    # Auto-populate tenant fields
    populated_data = _auto_populate_tenant_fields(
        Entity, entity_data.dict(), organization_id, user_id
    )
    
    db_entity = Entity(**populated_data)
    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    return db_entity
```

### Query Filtering

Database queries include organization filtering to prevent data leakage:

```python
def get_entities(db: Session, organization_id: str) -> List[Entity]:
    """Get entities filtered by organization."""
    return db.query(Entity).filter(
        Entity.organization_id == UUID(organization_id)
    ).all()
```

## Database Session Management

### Simple Session Management

Database sessions are managed without tenant setup overhead:

```python
@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get a simple database session with transparent transaction management."""
    db = SessionLocal()
    try:
        yield db
        # Commit any pending transactions automatically
        if db.in_transaction():
            db.commit()
    except Exception:
        # Rollback on exception
        if db.in_transaction():
            db.rollback()
        raise
    finally:
        # Close the session
        db.close()
```

### FastAPI Dependencies

FastAPI dependencies provide both database sessions and tenant context:

```python
def get_db_with_tenant_context(tenant_context: tuple = Depends(get_tenant_context)):
    """
    FastAPI dependency that provides both a database session and tenant context.
    
    This eliminates the need for SET LOCAL commands by providing the tenant 
    context directly to CRUD operations.
    
    Returns:
        tuple: (db_session, organization_id, user_id)
    """
    organization_id, user_id = tenant_context
    
    with get_db() as db:
        yield db, organization_id, user_id
```

**Key advantages of this approach:**

- **No SET LOCAL overhead**: Eliminates PostgreSQL session variable management
- **Better performance**: Reduces database round trips
- **Explicit parameters**: Makes tenant context visible in function signatures
- **Easier debugging**: Tenant context is explicit in stack traces
- **Transparent transactions**: Automatic commit/rollback handling

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