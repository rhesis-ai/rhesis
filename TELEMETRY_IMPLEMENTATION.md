# OpenTelemetry Implementation Complete ✅

## Overview

A complete OpenTelemetry-based telemetry system has been implemented for Rhesis to collect retention numbers and feature usage data. The system works for both cloud-hosted web app and self-hosted Docker Compose installations.

## Architecture

**Centralized Telemetry Collection:**
- Self-hosted users and cloud users send data to the same central OpenTelemetry Collector
- No local telemetry services run on user machines
- User-controlled opt-in/opt-out system
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
- `analytics_user_activity` - Login/logout, sessions
- `analytics_endpoint_usage` - API calls, performance
- `analytics_feature_usage` - Feature-specific actions

**Updated Tables:**
- `user` table: Added `telemetry_enabled` column (default: FALSE)

**Migrations:**
- `a1b2c3d4e5f7_add_telemetry_analytics_tables.py`
- `a1b2c3d4e5f8_add_telemetry_enabled_to_user.py`

### 🔌 Backend Implementation

**New Module:** `apps/backend/src/rhesis/backend/telemetry/`
- `instrumentation.py` - OpenTelemetry setup with conditional export
- `middleware.py` - Automatic endpoint tracking
- `__init__.py` - Public API

**API Endpoints Added:**
- `GET /api/users/telemetry/status` - Get user's preference
- `PUT /api/users/telemetry/enable` - Opt-in
- `PUT /api/users/telemetry/disable` - Opt-out

**Functions for Tracking:**
```python
from rhesis.backend.telemetry import track_user_activity, track_feature_usage

# Track login
track_user_activity("login", session_id=session.id)

# Track feature usage
track_feature_usage("test_run", "created", test_id=run.id)
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

**UI Components:**
- `src/components/settings/TelemetrySettings.tsx` - Settings page
- `src/components/telemetry/TelemetryOptInDialog.tsx` - First-time dialog

### ⚙️ Configuration

**Docker Compose:**
- Added telemetry environment variables to services
- Included commented telemetry services (optional)

**Environment Variables:**
```bash
# Backend
OTEL_EXPORTER_OTLP_ENDPOINT=https://telemetry.rhesis.ai
OTEL_SERVICE_NAME=rhesis-backend
DEPLOYMENT_TYPE=self_hosted

# Frontend
NEXT_PUBLIC_OTEL_ENDPOINT=https://telemetry.rhesis.ai
NEXT_PUBLIC_DEPLOYMENT_TYPE=self_hosted
```

### 📚 Documentation

1. **docs/TELEMETRY.md** - Comprehensive technical guide
   - Architecture overview
   - Data collection details
   - API reference
   - Looker Studio queries
   - Privacy policy

2. **docs/TELEMETRY_SETUP.md** - Step-by-step setup guide
   - Quick start instructions
   - Deployment guide
   - Database setup
   - Troubleshooting

3. **docs/telemetry/README.md** - Implementation summary

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
✅ **User-controlled** toggle in settings
✅ **One-way hashing** of all user/org IDs
✅ **Automatic filtering** of sensitive data
✅ **Transparent disclosure** of what's collected
✅ **5-second timeout** - doesn't block app if telemetry is slow
✅ **Graceful degradation** - app works perfectly without telemetry

## How It Works

### For Self-Hosted Users

1. **Default State:** Telemetry disabled
2. **User Opts In:** Toggle in Settings → Privacy
3. **Data Flows:**
   - App SDKs check `user.telemetry_enabled`
   - If enabled: Send OTLP data to `https://telemetry.rhesis.ai`
   - If disabled: No data sent
4. **Data Stored:** Central PostgreSQL database
5. **Visualization:** Google Looker Studio dashboards

### For Cloud/SaaS Users

1. **Default State:** Telemetry enabled (with notice)
2. **User Can Opt Out:** Toggle in Settings → Privacy
3. **Data Flows:**
   - App SDKs check `user.telemetry_enabled`
   - If enabled: Send OTLP to internal collector
   - Collector forwards to processor
4. **Data Stored:** Same central database
5. **Differentiation:** Tagged with `deployment.type: "cloud"`

## Deployment Steps

### 1. Run Database Migrations

```bash
cd apps/backend
source venv/bin/activate
cd src/rhesis/backend
alembic upgrade head
```

### 2. Deploy Telemetry Services (Cloud)

```bash
# Deploy OpenTelemetry Collector
cd apps/otel-collector
gcloud run deploy otel-collector --source . --region us-central1

# Deploy Telemetry Processor
cd apps/telemetry-processor
gcloud run deploy telemetry-processor --source . --region us-central1
```

### 3. Update Environment Variables

**Backend:**
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318  # Cloud
# OR
OTEL_EXPORTER_OTLP_ENDPOINT=https://telemetry.rhesis.ai # Self-hosted (optional)
```

**Frontend:**
```bash
NEXT_PUBLIC_OTEL_ENDPOINT=https://telemetry.rhesis.ai
NEXT_PUBLIC_DEPLOYMENT_TYPE=cloud  # or self_hosted
```

### 4. Connect Looker Studio

1. Create PostgreSQL data source
2. Connect to analytics database
3. Create custom SQL queries (see docs/TELEMETRY.md)
4. Build dashboards for:
   - Daily/Weekly/Monthly Active Users
   - Retention cohorts
   - Feature adoption rates
   - API performance metrics

## Testing Locally

```bash
# 1. Start services
docker-compose up -d

# 2. Run migrations
cd apps/backend && source venv/bin/activate
cd src/rhesis/backend && alembic upgrade head

# 3. Enable telemetry in UI
# Go to Settings → Privacy → Toggle ON

# 4. Generate test data
# Navigate around the app, create test runs, etc.

# 5. Verify data
psql -h localhost -U rhesis-user -d rhesis-db
SELECT * FROM analytics_user_activity LIMIT 10;
SELECT * FROM analytics_endpoint_usage LIMIT 10;
SELECT * FROM analytics_feature_usage LIMIT 10;
```

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
- `apps/telemetry-processor/` (entire directory)
- `apps/backend/src/rhesis/backend/telemetry/` (entire module)
- `apps/backend/src/rhesis/backend/alembic/versions/a1b2c3d4e5f7_*.py`
- `apps/backend/src/rhesis/backend/alembic/versions/a1b2c3d4e5f8_*.py`
- `apps/frontend/src/lib/telemetry.ts`
- `apps/frontend/src/components/settings/TelemetrySettings.tsx`
- `apps/frontend/src/components/telemetry/TelemetryOptInDialog.tsx`
- `docs/TELEMETRY.md`
- `docs/TELEMETRY_SETUP.md`
- `docs/telemetry/README.md`

**Modified:**
- `apps/backend/src/rhesis/backend/app/main.py` (added telemetry initialization)
- `apps/backend/src/rhesis/backend/app/models/user.py` (added telemetry_enabled field)
- `apps/backend/src/rhesis/backend/app/routers/user.py` (added telemetry endpoints)
- `apps/backend/pyproject.toml` (added OpenTelemetry dependencies)
- `apps/frontend/package.json` (added OpenTelemetry dependencies)
- `docker-compose.yml` (added telemetry configuration)

## Next Steps

1. **Deploy to production**
   - Deploy telemetry services to Cloud Run
   - Run database migrations
   - Update environment variables

2. **Create Looker Studio dashboards**
   - Connect to analytics database
   - Create retention dashboard
   - Create feature usage dashboard
   - Create performance dashboard

3. **Monitor and iterate**
   - Monitor telemetry service health
   - Track data volume and storage
   - Add more tracking as needed

4. **Optional enhancements**
   - Add first-time opt-in dialog to onboarding flow
   - Create admin dashboard showing telemetry stats
   - Add data export functionality
   - Implement data deletion on user request

## Support & Documentation

- **Comprehensive Guide:** `docs/TELEMETRY.md`
- **Setup Instructions:** `docs/TELEMETRY_SETUP.md`
- **Implementation Details:** `docs/telemetry/README.md`
- **Privacy Policy:** https://rhesis.ai/privacy

## Success Criteria ✅

- [x] Telemetry collector service created
- [x] Telemetry processor service created
- [x] Database migrations created
- [x] Backend instrumentation implemented
- [x] Frontend SDK implemented
- [x] User opt-in/opt-out UI created
- [x] Privacy controls implemented
- [x] Documentation complete
- [x] Environment configuration ready
- [x] Default opt-out for self-hosted users
- [x] No local services required for self-hosted users
- [x] One-way hashing of user IDs
- [x] Sensitive data filtering

**Status:** 🎉 **COMPLETE AND READY FOR DEPLOYMENT**

---

**Implementation Date:** 2025-10-21
**Version:** 0.4.0
**Author:** AI Assistant

