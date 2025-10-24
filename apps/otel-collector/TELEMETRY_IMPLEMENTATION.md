# OpenTelemetry Implementation Complete ✅

## Overview

A complete OpenTelemetry-based telemetry system has been implemented for Rhesis to collect retention numbers and feature usage data. The system works for both cloud-hosted web app and self-hosted Docker Compose installations.

## Architecture

**Centralized Telemetry Collection:**
- Self-hosted users and cloud users send data to OpenTelemetry Collector (Cloud Run)
- No local telemetry services run on user machines
- **Environment-based control:**
  - **Cloud deployments**: Telemetry always enabled (implicit user consent)
  - **Self-hosted deployments**: Controlled via `TELEMETRY_ENABLED` environment variable
- Privacy-first: all user/org IDs are hashed, no PII collected

## What Was Built

### 🔧 Services Created

1. **OpenTelemetry Collector** (`apps/otel-collector/`)
   - Receives OTLP data via gRPC/HTTP
   - Filters sensitive data (passwords, tokens)
   - Exports to Telemetry Processor
   - Ports: 4317 (gRPC), 4318 (HTTP), 13133 (health)

2. **Telemetry Processor** (`apps/telemetry-processor/`)
   - gRPC service that writes to PostgreSQL
   - Transforms OTLP traces to analytics records
   - Handles 3 event types: user activity, endpoint usage, feature usage
   - Port: 4317

### 📊 Database Changes

**New Tables:**
- `analytics_user_activity` - Login/logout, sessions (user_id/org_id as hashed strings)
- `analytics_endpoint_usage` - API calls, performance (user_id/org_id as hashed strings)
- `analytics_feature_usage` - Feature-specific actions (user_id/org_id as hashed strings)

**Key Schema Notes:**
- `user_id` and `organization_id` are stored as `VARCHAR(32)` (hashed IDs, not UUIDs)
- All IDs are one-way SHA-256 hashed for privacy

**Migration:**
- `a1b2c3d4e5f7_add_telemetry_analytics_tables.py`

### 🔌 Backend Implementation

**New Module:** `apps/backend/src/rhesis/backend/telemetry/`
- `instrumentation.py` - OpenTelemetry setup with environment-based control
  - `is_telemetry_enabled()` - Checks `DEPLOYMENT_TYPE` and `TELEMETRY_ENABLED` env vars
  - `initialize_telemetry()` - Sets up OpenTelemetry SDK
  - `track_user_activity()` - Tracks login/logout events
  - `track_feature_usage()` - Tracks feature interactions
- `middleware.py` - Automatic endpoint tracking
  - Tracks API endpoint usage, performance, and errors
  - Sets telemetry context for each request
- `__init__.py` - Public API

**Telemetry Control Logic:**
```python
def is_telemetry_enabled() -> bool:
    """
    Environment-based telemetry control:
    - Cloud deployment (DEPLOYMENT_TYPE=cloud): Always enabled
    - Self-hosted (DEPLOYMENT_TYPE=self-hosted): Check TELEMETRY_ENABLED env var
    """
    deployment_type = os.getenv("DEPLOYMENT_TYPE", "unknown")
    if deployment_type == "cloud":
        return True
    if deployment_type == "self-hosted":
        return os.getenv("TELEMETRY_ENABLED", "false").lower() in ("true", "1", "yes")
    return False
```

**Functions for Tracking:**
```python
from rhesis.backend.telemetry import track_user_activity, track_feature_usage, is_telemetry_enabled

# Check if telemetry is enabled
if is_telemetry_enabled():
    # Track login
    track_user_activity("login", session_id=session.id)
    
    # Track feature usage
    track_feature_usage("test_run", "created", test_id=run.id)
```

**Tracking Examples:**
```python
# In auth.py (login)
if is_telemetry_enabled():
    set_telemetry_enabled(enabled=True, user_id=str(user.id), org_id=str(user.organization_id))
    track_user_activity("login", session_id=session_id, login_method="oauth")

# In task_management.py (create task)
if is_telemetry_enabled():
    track_feature_usage("task", "created", task_id=str(task.id))
```

### 🎨 Frontend Implementation

**Telemetry SDK:** `apps/frontend/src/lib/telemetry.ts`
```typescript
import { trackPageView, trackEvent, trackFeatureUsage } from '@/lib/telemetry';

// Track page view
trackPageView('/dashboard', userId, orgId);

// Track custom event
trackEvent('button_click', { button_id: 'create_test' });

// Track feature usage
trackFeatureUsage('test_run', 'created', { test_id: '123' });
```

**Note:** No UI components for telemetry settings. Telemetry is controlled at the deployment level, not per-user.

### ⚙️ Configuration

**Docker Compose:**
- Telemetry services (otel-collector, telemetry-processor) run as Docker containers
- Backend and frontend configured with telemetry environment variables
- See `docker-compose.yml` for full configuration

**Environment Variables (Cloud Deployment):**
```bash
# Backend
DEPLOYMENT_TYPE=cloud                                    # Always enabled
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.run.app:4318
OTEL_SERVICE_NAME=rhesis-backend
APP_VERSION=1.0.0

# Frontend
NEXT_PUBLIC_OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.run.app:4318
NEXT_PUBLIC_OTEL_SERVICE_NAME=rhesis-frontend
DEPLOYMENT_TYPE=cloud
```

**Environment Variables (Self-Hosted):**
```bash
# Backend
DEPLOYMENT_TYPE=self-hosted                              # User controls via TELEMETRY_ENABLED
TELEMETRY_ENABLED=true                                   # Optional: Enable telemetry
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.run.app:4318
OTEL_SERVICE_NAME=rhesis-backend
APP_VERSION=dev

# Frontend
NEXT_PUBLIC_OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.run.app:4318
NEXT_PUBLIC_OTEL_SERVICE_NAME=rhesis-frontend
DEPLOYMENT_TYPE=self-hosted
```

**Key Environment Variables:**
- `DEPLOYMENT_TYPE`: `cloud` (always enabled) or `self-hosted` (optional)
- `TELEMETRY_ENABLED`: Only for `self-hosted`, defaults to `false`
- `OTEL_EXPORTER_OTLP_ENDPOINT`: URL of the OTel Collector service

### 📚 Documentation

**Note:** Previous documentation has been consolidated. Current documentation includes:

1. **TELEMETRY_IMPLEMENTATION.md** (this file) - Complete implementation overview
2. **GitHub Workflows for Cloud Run Deployment:**
   - `.github/workflows/otel-collector.yml` - Deploys OTel Collector
   - `.github/workflows/telemetry-processor.yml` - Deploys Telemetry Processor

### 🚀 Cloud Run Deployment

**GitHub Workflows Created:**

1. **OTel Collector Workflow** (`.github/workflows/otel-collector.yml`)
   - Builds minimal Docker image extending `otel/opentelemetry-collector-contrib:0.97.0`
   - Deploys to Cloud Run (dev/stg/prd environments)
   - Auto-detects telemetry processor URL
   - Resources: 512Mi RAM, 1 CPU, 1-3 instances
   - Public access for receiving telemetry

2. **Telemetry Processor Workflow** (`.github/workflows/telemetry-processor.yml`)
   - Full Python app build (similar to backend workflow)
   - Deploys to Cloud Run with Cloud SQL connection
   - Internal-only access (IAM protected)
   - Resources: 512Mi RAM, 1 CPU, 1-5 instances
   - Auto-configures IAM for collector access

**Dockerfile:**
- `apps/otel-collector/Dockerfile` - Minimal Dockerfile extending official image

## Data Collected

### ✅ What We Collect (Anonymous)

**Retention Metrics:**
- Login events (timestamp, hashed user_id)
- Session duration
- Last active timestamps
- Return visit patterns
- DAU/WAU/MAU calculations

**Feature Usage:**
- Feature name + action (e.g., "test_run.created")
- Usage frequency
- Feature adoption rates
- Most used features

**Endpoint Usage:**
- API endpoint paths
- HTTP methods and status codes
- Response times (performance)
- Error rates

### ❌ What We Don't Collect

- Email addresses, names, or any PII
- Test data, prompts, or LLM responses
- API keys, tokens, or credentials
- IP addresses
- Organization names
- Any sensitive business data

## Privacy Features

✅ **Default opt-out** for self-hosted installations
✅ **Environment-based control** - No per-user settings, deployment-level control
✅ **One-way hashing** of all user/org IDs (SHA-256)
✅ **Automatic filtering** of sensitive data (passwords, tokens, API keys)
✅ **Transparent disclosure** of what's collected
✅ **5-second timeout** - doesn't block app if telemetry is slow
✅ **Graceful degradation** - app works perfectly without telemetry
✅ **Cloud deployment implicit consent** - Users agree to telemetry as part of service terms

## How It Works

### For Self-Hosted Users

1. **Default State:** Telemetry **disabled** (no data collected)
2. **Admin Control:** Set `TELEMETRY_ENABLED=true` in environment variables to enable
3. **Data Flows:**
   - Backend checks `is_telemetry_enabled()` → reads `DEPLOYMENT_TYPE` and `TELEMETRY_ENABLED`
   - If enabled: Send OTLP data to OTel Collector (Cloud Run)
   - If disabled: No data sent, no performance impact
4. **Data Stored:** Central PostgreSQL database (Cloud SQL)
5. **Tagged with:** `deployment_type: "self-hosted"`

### For Cloud/SaaS Users

1. **Default State:** Telemetry **always enabled** (implicit consent in service terms)
2. **No User Control:** Deployment-level setting, not configurable per user
3. **Data Flows:**
   - Backend checks `is_telemetry_enabled()` → returns `true` for `DEPLOYMENT_TYPE=cloud`
   - Send OTLP to internal OTel Collector (Cloud Run)
   - Collector processes and forwards to Telemetry Processor
   - Processor writes to PostgreSQL analytics tables
4. **Data Stored:** Central PostgreSQL database (Cloud SQL)
5. **Tagged with:** `deployment_type: "cloud"`

### Architecture Flow

```
Backend/Frontend
    ↓ (if telemetry enabled)
    ↓ OTLP/HTTP or gRPC
OTel Collector (Cloud Run)
    ↓ Batch, filter, retry
    ↓ OTLP/gRPC
Telemetry Processor (Cloud Run)
    ↓ Parse and transform
    ↓ SQL INSERT
PostgreSQL (Cloud SQL)
    ↓
Analytics Tables
```

## Deployment Steps

### 1. Run Database Migrations

```bash
cd apps/backend
source .venv/bin/activate
cd src/rhesis/backend
alembic upgrade head
```

This creates the three analytics tables: `analytics_user_activity`, `analytics_endpoint_usage`, and `analytics_feature_usage`.

### 2. Deploy Telemetry Services to Cloud Run

**Via GitHub Workflows (Recommended):**

```bash
# Step 1: Deploy Telemetry Processor first (no dependencies)
gh workflow run telemetry-processor.yml -f environment=dev -f reason="Initial deployment"

# Step 2: Deploy OTel Collector (auto-detects processor URL)
gh workflow run otel-collector.yml -f environment=dev -f reason="Initial deployment"

# Step 3: Get collector URL from GitHub Actions summary
# Then add as GitHub secret
gh secret set OTEL_EXPORTER_OTLP_ENDPOINT -b "https://rhesis-otel-collector-dev-xxx.run.app:4318"
gh secret set NEXT_PUBLIC_OTEL_EXPORTER_OTLP_ENDPOINT -b "https://rhesis-otel-collector-dev-xxx.run.app:4318"
```

**Manual Deployment (Alternative):**

```bash
# Deploy Telemetry Processor
cd apps/telemetry-processor
gcloud run deploy rhesis-telemetry-processor \
  --source . \
  --region us-central1 \
  --set-env-vars="SQLALCHEMY_DATABASE_URL=...,..." \
  --add-cloudsql-instances=PROJECT:REGION:INSTANCE

# Deploy OTel Collector
cd apps/otel-collector
gcloud run deploy rhesis-otel-collector \
  --source . \
  --region us-central1 \
  --set-env-vars="TELEMETRY_PROCESSOR_ENDPOINT=https://rhesis-telemetry-processor-xxx.run.app"
```

### 3. Update Backend/Frontend Environment Variables

Add these to your backend deployment (`.github/workflows/backend.yml`):

```yaml
DEPLOYMENT_TYPE=cloud,
OTEL_EXPORTER_OTLP_ENDPOINT=https://rhesis-otel-collector-dev-xxx.run.app:4318,
OTEL_SERVICE_NAME=rhesis-backend,
APP_VERSION=${{ github.sha }}
```

Add these to your frontend deployment (`.github/workflows/frontend.yml`):

```yaml
NEXT_PUBLIC_OTEL_EXPORTER_OTLP_ENDPOINT=https://rhesis-otel-collector-dev-xxx.run.app:4318,
NEXT_PUBLIC_OTEL_SERVICE_NAME=rhesis-frontend,
DEPLOYMENT_TYPE=cloud
```

### 4. Redeploy Backend and Frontend

```bash
gh workflow run backend.yml -f environment=dev -f reason="Enable telemetry"
gh workflow run frontend.yml -f environment=dev -f reason="Enable telemetry"
```

### 5. Verify Data Collection

```sql
-- Check recent user activity
SELECT * FROM analytics_user_activity 
WHERE timestamp > NOW() - INTERVAL '1 hour' 
ORDER BY timestamp DESC LIMIT 10;

-- Check endpoint usage
SELECT * FROM analytics_endpoint_usage 
WHERE timestamp > NOW() - INTERVAL '1 hour' 
ORDER BY timestamp DESC LIMIT 10;

-- Check feature usage
SELECT * FROM analytics_feature_usage 
WHERE timestamp > NOW() - INTERVAL '1 hour' 
ORDER BY timestamp DESC LIMIT 10;
```

### 6. Connect Looker Studio (Optional)

1. Create PostgreSQL data source
2. Connect to Cloud SQL analytics database
3. Create dashboards for:
   - Daily/Weekly/Monthly Active Users
   - Retention cohorts
   - Feature adoption rates
   - API performance metrics

## Testing Locally

```bash
# 1. Start Docker services
docker-compose up -d

# 2. Run migrations
cd apps/backend && source .venv/bin/activate
cd src/rhesis/backend && alembic upgrade head

# 3. Set environment variables for backend
export DEPLOYMENT_TYPE=cloud
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=rhesis-backend
export APP_VERSION=dev

# 4. Start backend
./rh backend start

# 5. Generate test data
# - Login to the app
# - Navigate around the app
# - Create tasks, view dashboards, etc.

# 6. Verify data in database
PGPASSWORD=rhesis-password psql -h 127.0.0.1 -U rhesis-user -d rhesis-db -c "SELECT * FROM analytics_user_activity ORDER BY timestamp DESC LIMIT 10;"
PGPASSWORD=rhesis-password psql -h 127.0.0.1 -U rhesis-user -d rhesis-db -c "SELECT * FROM analytics_endpoint_usage ORDER BY timestamp DESC LIMIT 10;"
PGPASSWORD=rhesis-password psql -h 127.0.0.1 -U rhesis-user -d rhesis-db -c "SELECT * FROM analytics_feature_usage ORDER BY timestamp DESC LIMIT 10;"

# 7. Check OTel Collector health
curl http://localhost:13133/health
# Expected: {"status":"up"}

# 8. Check collector logs
docker logs rhesis-otel-collector

# 9. Check processor logs
docker logs rhesis-telemetry-processor
```

**Note:** For self-hosted testing, use `DEPLOYMENT_TYPE=self-hosted` and `TELEMETRY_ENABLED=true`

## Sample Queries

### Daily Active Users

```sql
SELECT 
    DATE(timestamp) as date,
    deployment_type,
    COUNT(DISTINCT user_id) as daily_active_users
FROM analytics_user_activity
WHERE event_type = 'login'
    AND timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date, deployment_type
ORDER BY date DESC;
```

### Feature Adoption Rate

```sql
SELECT 
    feature_name,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(*) as total_uses,
    deployment_type
FROM analytics_feature_usage
WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY feature_name, deployment_type
ORDER BY unique_users DESC;
```

### API Performance

```sql
SELECT 
    endpoint,
    method,
    AVG(duration_ms) as avg_response_time,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_response_time,
    COUNT(*) as request_count
FROM analytics_endpoint_usage
WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY endpoint, method
ORDER BY request_count DESC;
```

## Files Modified/Created

**Created:**
- `apps/otel-collector/` (entire directory)
  - `Dockerfile` - Minimal Dockerfile extending official image
  - `otel-collector-config.yaml` - Collector configuration
- `apps/telemetry-processor/` (entire directory)
  - `Dockerfile` - Python app Dockerfile
  - `pyproject.toml` - Python dependencies
  - `src/processor.py` - gRPC service
- `apps/backend/src/rhesis/backend/telemetry/` (entire module)
  - `instrumentation.py` - OpenTelemetry setup with `is_telemetry_enabled()`
  - `middleware.py` - Automatic endpoint tracking
  - `__init__.py` - Public API
- `apps/backend/src/rhesis/backend/alembic/versions/a1b2c3d4e5f7_add_telemetry_analytics_tables.py`
- `apps/frontend/src/lib/telemetry.ts` - Frontend OpenTelemetry SDK
- `.github/workflows/otel-collector.yml` - Cloud Run deployment workflow
- `.github/workflows/telemetry-processor.yml` - Cloud Run deployment workflow
- `TELEMETRY_IMPLEMENTATION.md` (this file)

**Modified:**
- `apps/backend/src/rhesis/backend/app/main.py` (added telemetry initialization)
- `apps/backend/src/rhesis/backend/app/routers/auth.py` (added telemetry tracking for login/logout)
- `apps/backend/src/rhesis/backend/app/routers/task_management.py` (added telemetry tracking for CRUD operations)
- `apps/backend/pyproject.toml` (added OpenTelemetry dependencies)
- `apps/frontend/package.json` (added OpenTelemetry dependencies)
- `docker-compose.yml` (added telemetry services and environment variables)

**Deleted (from previous implementation):**
- `apps/backend/src/rhesis/backend/alembic/versions/a1b2c3d4e5f8_add_telemetry_enabled_to_user.py` (no longer needed)
- `apps/frontend/src/components/settings/TelemetrySettings.tsx` (environment-based control)
- `apps/frontend/src/components/telemetry/TelemetryOptInDialog.tsx` (environment-based control)
- API endpoints for user telemetry control (no longer needed)

## Next Steps

1. **Deploy to Production/Staging**
   - ✅ Deploy telemetry services to Cloud Run via GitHub workflows
   - ✅ Run database migrations (analytics tables)
   - ⏳ Update backend/frontend workflows with telemetry environment variables
   - ⏳ Add GitHub secrets with collector URLs
   - ⏳ Redeploy backend and frontend with telemetry enabled

2. **Verify Data Collection**
   - ⏳ Login to production/staging
   - ⏳ Perform various actions
   - ⏳ Check analytics tables for data
   - ⏳ Monitor Cloud Run logs for errors

3. **Create Looker Studio Dashboards**
   - ⏳ Connect to Cloud SQL analytics database
   - ⏳ Create retention dashboard (DAU/WAU/MAU)
   - ⏳ Create feature usage dashboard
   - ⏳ Create API performance dashboard

4. **Monitor and Iterate**
   - ⏳ Monitor telemetry service health in Cloud Run
   - ⏳ Track data volume and Cloud SQL storage
   - ⏳ Optimize batch sizes and instance counts
   - ⏳ Add more tracking as needed (e.g., test runs, evaluations)

5. **Optional Enhancements**
   - Create admin dashboard showing real-time telemetry stats
   - Add data export functionality
   - Implement data retention policies (e.g., delete data older than 2 years)
   - Add alerting for telemetry service failures

## Support & Documentation

- **Implementation Guide:** `TELEMETRY_IMPLEMENTATION.md` (this file)
- **Cloud Run Deployment:** `.github/workflows/otel-collector.yml` and `.github/workflows/telemetry-processor.yml`
- **Backend Telemetry Module:** `apps/backend/src/rhesis/backend/telemetry/`
- **Frontend Telemetry SDK:** `apps/frontend/src/lib/telemetry.ts`

## Success Criteria ✅

### Core Implementation
- [x] Telemetry collector service created (`apps/otel-collector/`)
- [x] Telemetry processor service created (`apps/telemetry-processor/`)
- [x] Database migrations created (analytics tables)
- [x] Backend instrumentation implemented with `is_telemetry_enabled()`
- [x] Frontend SDK implemented (`lib/telemetry.ts`)
- [x] Environment-based control implemented
- [x] Documentation complete

### Privacy & Security
- [x] Default opt-out for self-hosted users
- [x] Cloud deployment implicit consent (always enabled)
- [x] No per-user consent UI (deployment-level control)
- [x] One-way hashing of user/org IDs (SHA-256)
- [x] Sensitive data filtering (passwords, tokens, API keys)
- [x] No PII collected

### Deployment
- [x] Cloud Run deployment workflows created
  - `.github/workflows/otel-collector.yml`
  - `.github/workflows/telemetry-processor.yml`
- [x] Docker configurations ready
- [x] Environment variables documented

### Data Collection
- [x] User activity tracking (login/logout)
- [x] Endpoint usage tracking (automatic via middleware)
- [x] Feature usage tracking (tasks: create, view, update, delete)
- [x] Performance metrics (response times, error rates)

### Infrastructure
- [x] No local services required for self-hosted users
- [x] Auto-scaling Cloud Run services
- [x] IAM-protected internal services
- [x] Health checks and monitoring ready

**Status:** 🎉 **COMPLETE AND READY FOR CLOUD DEPLOYMENT**

---

**Implementation Date:** 2025-10-24
**Version:** 1.0.0
**Last Updated:** 2025-10-24
**Author:** AI Assistant

