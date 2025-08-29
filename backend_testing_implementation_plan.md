# 🧪 Backend Testing CI/CD Implementation Plan

## 📋 Analysis Summary

Based on the analysis of the current backend setup, here are the key findings:

### ✅ Current Backend Infrastructure
- **Framework**: FastAPI with Python 3.10+
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic with Row Level Security (RLS)
- **Authentication**: Auth0 integration with JWT tokens
- **Dependencies**: uv for package management
- **Testing**: pytest with asyncio, comprehensive test markers
- **Multi-tenancy**: Organization-based with RLS policies

### 🔍 Key Requirements Identified
1. **Database Setup**: PostgreSQL with proper test database configuration
2. **Migrations**: Alembic upgrade head required before tests
3. **User Setup**: Default user and organization creation for tests
4. **Initial Data**: Organization data seeding using `load_initial_data()` service
5. **Environment Variables**: Proper test environment configuration
6. **Dependencies**: Same as Dockerfile (uv sync with dev dependencies)

## 🚀 Implementation Plan

### Phase 1: Core Testing Workflow Setup ⚡

#### Step 1.1: Create Backend Test Workflow File
**File**: `.github/workflows/backend-test.yml`

**Key Components**:
- Multi-stage testing (unit → integration → comprehensive)
- PostgreSQL service with proper configuration
- Redis service for Celery worker tests
- Environment variables matching backend requirements
- Database initialization with migrations and seed data

#### Step 1.2: Database Configuration
**PostgreSQL Service Setup**:
```yaml
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_DB: rhesis_test
      POSTGRES_USER: rhesis_user
      POSTGRES_PASSWORD: test_password_123
      POSTGRES_HOST_AUTH_METHOD: trust
    ports:
      - 5432:5432
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

#### Step 1.3: Environment Variables Setup
**Test Environment Configuration**:
```bash
# Database Configuration
SQLALCHEMY_DB_MODE=test
SQLALCHEMY_DATABASE_TEST_URL=postgresql://rhesis_user:test_password_123@localhost:5432/rhesis_test
SQLALCHEMY_DB_DRIVER=postgresql
SQLALCHEMY_DB_USER=rhesis_user
SQLALCHEMY_DB_PASS=test_password_123
SQLALCHEMY_DB_HOST=localhost
SQLALCHEMY_DB_NAME=rhesis_test

# Application Configuration
LOG_LEVEL=WARNING
PYTHONPATH=/app/src

# Mock AI Services (no real API calls)
AZURE_OPENAI_API_KEY=mock-azure-key-for-testing
AZURE_OPENAI_ENDPOINT=https://mock-endpoint.openai.azure.com
AZURE_OPENAI_DEPLOYMENT_NAME=mock-deployment
AZURE_OPENAI_API_VERSION=2024-02-01
GEMINI_API_KEY=mock-gemini-key-for-testing
GEMINI_MODEL_NAME=gemini-1.5-flash

# Auth Configuration (mocked for tests)
AUTH0_DOMAIN=mock-domain.auth0.com
AUTH0_AUDIENCE=mock-audience
AUTH0_CLIENT_ID=mock-client-id
AUTH0_CLIENT_SECRET=mock-client-secret
AUTH0_SECRET_KEY=mock-secret-key-for-testing-only
JWT_SECRET_KEY=mock-jwt-secret-key-for-testing-only
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Frontend URL (for redirects in tests)
FRONTEND_URL=http://localhost:3000

# Redis for Celery (if needed for worker tests)
REDIS_URL=redis://localhost:6379
BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Email Configuration (mocked)
SMTP_HOST=mock-smtp.example.com
SMTP_PORT=587
SMTP_USER=test@example.com
SMTP_PASSWORD=mock-password
FROM_EMAIL=test@rhesis.ai
```

### Phase 2: Database Initialization Strategy 🗄️

#### Step 2.1: Database Migration Setup
**Migration Command**:
```bash
cd apps/backend
# Run migrations to create all tables with RLS policies
uv run alembic upgrade head
```

#### Step 2.2: Test User and Organization Creation
**Create Test Data Setup Script**:
```python
# tests/backend/fixtures/test_setup.py
import uuid
from sqlalchemy.orm import Session
from rhesis.backend.app import models, crud
from rhesis.backend.app.schemas import UserCreate, OrganizationCreate
from rhesis.backend.app.database import set_tenant
from rhesis.backend.app.services.organization import load_initial_data

def create_test_organization_and_user(db: Session) -> tuple[models.Organization, models.User]:
    """Create test organization and user for testing"""
    
    # Create test organization
    org_data = OrganizationCreate(
        name="Test Organization",
        description="Organization for testing purposes",
        is_active=True,
        is_onboarding_complete=False  # Will be set to True after initial data load
    )
    organization = crud.create_organization(db, org_data)
    
    # Create test user
    user_data = UserCreate(
        email="test@rhesis.ai",
        name="Test User",
        given_name="Test",
        family_name="User",
        auth0_id="test-auth0-id",
        is_active=True,
        is_superuser=True,  # Make superuser for testing
        organization_id=organization.id
    )
    user = crud.create_user(db, user_data)
    
    # Set tenant context and load initial data
    set_tenant(db, organization_id=str(organization.id), user_id=str(user.id))
    load_initial_data(db, str(organization.id), str(user.id))
    
    return organization, user
```

#### Step 2.3: Test Database Fixture
**Update conftest.py**:
```python
# tests/backend/conftest.py
@pytest.fixture(scope="session")
def test_db():
    """Create test database session"""
    from rhesis.backend.app.database import engine, SessionLocal
    from rhesis.backend.app.models import Base
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Create test organization and user
        organization, user = create_test_organization_and_user(db)
        
        # Store IDs for use in tests
        db.test_organization_id = organization.id
        db.test_user_id = user.id
        
        yield db
    finally:
        db.close()
        # Clean up test database
        Base.metadata.drop_all(bind=engine)
```

### Phase 3: GitHub Actions Workflow Implementation 🔄

#### Step 3.1: Multi-Stage Testing Pipeline
**Workflow Structure**:
1. **Unit Tests** (< 2 min): Fast tests with mocked dependencies
2. **Integration Tests** (< 5 min): Database and API integration tests  
3. **Security Tests** (< 3 min): Authentication and security validation
4. **Comprehensive Tests** (main branch only): Slow and AI tests

#### Step 3.2: Dependency Installation Strategy
**Match Dockerfile Dependencies**:
```yaml
- name: Setup Python
  uses: actions/setup-python@v4
  with:
    python-version: '3.11'  # Match backend requirement

- name: Install uv
  uses: astral-sh/setup-uv@v3

- name: Cache uv dependencies
  uses: actions/cache@v3
  with:
    path: ~/.cache/uv
    key: ${{ runner.os }}-uv-${{ hashFiles('apps/backend/uv.lock') }}
    restore-keys: |
      ${{ runner.os }}-uv-

- name: Install dependencies
  run: |
    cd apps/backend
    # Install both runtime and dev dependencies
    uv sync --dev
    
    # Verify SDK is properly linked
    uv pip show rhesis-sdk
```

#### Step 3.3: Database Initialization in CI
**Database Setup Steps**:
```yaml
- name: Wait for PostgreSQL
  run: |
    until pg_isready -h localhost -p 5432 -U rhesis_user; do
      echo "Waiting for PostgreSQL..."
      sleep 2
    done

- name: Setup test database
  run: |
    cd apps/backend
    # Run migrations
    uv run alembic upgrade head
    
    # Verify database structure
    PGPASSWORD=test_password_123 psql -h localhost -U rhesis_user -d rhesis_test -c "\dt"

- name: Run tests with database
  env:
    SQLALCHEMY_DB_MODE: test
    SQLALCHEMY_DATABASE_TEST_URL: postgresql://rhesis_user:test_password_123@localhost:5432/rhesis_test
    # ... other environment variables
  run: |
    cd apps/backend
    uv run pytest -m "unit" -v --tb=short
```

### Phase 4: Test Execution Strategy 🧪

#### Step 4.1: Test Categories and Execution Order
**Stage 1 - Unit Tests (< 2 min)**:
```bash
uv run pytest -m "unit and critical" --maxfail=5 --tb=short -v
```

**Stage 2 - Integration Tests (< 5 min)**:
```bash
uv run pytest -m "integration and not slow" --maxfail=3 -v
```

**Stage 3 - Security Tests (< 3 min)**:
```bash
uv run pytest -m "security" --maxfail=2 -v
```

**Stage 4 - Comprehensive Tests (main branch only)**:
```bash
# Slow tests
uv run pytest -m "slow" --maxfail=1 --tb=short -v

# AI tests (with mocked services)
uv run pytest -m "ai" --maxfail=1 --tb=short -v
```

#### Step 4.2: Coverage Reporting
**Coverage Configuration**:
```bash
uv run pytest --cov=src --cov-report=xml --cov-report=html --cov-report=term-missing -m "not slow" -v
```

### Phase 5: Integration with Existing Backend Workflow 🔗

#### Step 5.1: Modify backend.yml
**Add Test Dependency**:
```yaml
jobs:
  test:
    uses: ./.github/workflows/backend-test.yml
    
  build:
    needs: test  # Only build if tests pass
    if: (github.ref == 'refs/heads/main' && github.event_name == 'push') || (github.event_name == 'workflow_dispatch' && github.event.inputs.deploy_only != 'true')
    # ... existing build job
    
  deploy:
    needs: [test, build]  # Only deploy if tests pass and build succeeds
    # ... existing deploy job
```

#### Step 5.2: Branch Protection Rules
**Required Status Checks**:
- Unit Tests
- Integration Tests  
- Security Tests
- Coverage Report

### Phase 6: Optimization and Monitoring 📊

#### Step 6.1: Performance Optimizations
- **Dependency Caching**: Cache uv dependencies between runs
- **Database Optimization**: Use connection pooling for tests
- **Parallel Execution**: Run independent test categories in parallel
- **Test Selection**: Only run relevant tests based on changed files

#### Step 6.2: Monitoring and Alerts
- **Test Duration Tracking**: Monitor test execution times
- **Flaky Test Detection**: Identify and fix unreliable tests
- **Coverage Trends**: Track coverage changes over time
- **Failure Notifications**: Alert on test failures

## 🛠️ Implementation Checklist

### Phase 1: Immediate Actions (Week 1)
- [ ] Create `.github/workflows/backend-test.yml`
- [ ] Set up PostgreSQL and Redis services
- [ ] Configure environment variables
- [ ] Test basic workflow execution

### Phase 2: Database Integration (Week 1-2)
- [ ] Implement database initialization script
- [ ] Create test organization and user setup
- [ ] Update test fixtures for proper tenant context
- [ ] Verify migrations work in CI environment

### Phase 3: Test Execution (Week 2)
- [ ] Implement multi-stage testing pipeline
- [ ] Configure test categories and markers
- [ ] Set up coverage reporting
- [ ] Test all stages locally and in CI

### Phase 4: Integration (Week 2-3)
- [ ] Modify existing backend.yml workflow
- [ ] Set up branch protection rules
- [ ] Test end-to-end: PR → Tests → Build → Deploy
- [ ] Document workflow for team

### Phase 5: Optimization (Week 3-4)
- [ ] Implement caching strategies
- [ ] Set up monitoring and alerts
- [ ] Optimize test execution time
- [ ] Create troubleshooting guide

## 🎯 Success Criteria

- ✅ **Zero backend deployments without passing tests**
- ⚡ **Unit tests complete in < 2 minutes**
- 🔗 **Integration tests complete in < 5 minutes**
- 🔒 **All security tests pass before deployment**
- 📊 **Maintain > 80% code coverage**
- 🚀 **Clear failure messages and fast feedback**

## 🚨 Risk Mitigation

### Database Connection Issues
- Use health checks for PostgreSQL service
- Implement retry logic for database connections
- Provide clear error messages for database failures

### Environment Variable Conflicts
- Use test-specific environment variable names where possible
- Document all required environment variables
- Validate environment setup before running tests

### Test Flakiness
- Mock external services consistently
- Use deterministic test data
- Implement proper cleanup between tests

### Performance Issues
- Monitor test execution times
- Implement parallel execution where safe
- Cache dependencies and database setup

---

**This implementation plan provides a comprehensive roadmap for implementing backend testing automation that integrates seamlessly with the existing Rhesis backend infrastructure while ensuring reliability, performance, and maintainability.**

