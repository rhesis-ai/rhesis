# OpenTelemetry Integration - Implementation Summary

This document provides an overview of the OpenTelemetry integration for Rhesis.

## ✅ Implementation Complete

All components of the OpenTelemetry telemetry system have been successfully implemented.

## 📁 What Was Created

### Services

1. **OpenTelemetry Collector** (`apps/otel-collector/`)
   - Receives OTLP data from all Rhesis instances
   - Filters sensitive data (passwords, tokens, API keys)
   - Forwards processed data to Telemetry Processor
   - Exposes health check and metrics endpoints

2. **Telemetry Processor** (`apps/telemetry-processor/`)
   - gRPC service that receives data from the collector
   - Transforms OTLP traces into structured analytics data
   - Writes to PostgreSQL analytics tables
   - Handles three types of events: user activity, endpoint usage, feature usage

### Backend Changes

1. **Database Migrations** (`apps/backend/src/rhesis/backend/alembic/versions/`)
   - `a1b2c3d4e5f7_add_telemetry_analytics_tables.py` - Creates analytics tables
   - `a1b2c3d4e5f8_add_telemetry_enabled_to_user.py` - Adds user preference column

2. **Telemetry Module** (`apps/backend/src/rhesis/backend/telemetry/`)
   - `instrumentation.py` - Core OpenTelemetry setup with conditional export
   - `middleware.py` - FastAPI middleware for automatic endpoint tracking
   - `__init__.py` - Public API exports

3. **API Endpoints** (`apps/backend/src/rhesis/backend/app/routers/user.py`)
   - `GET /api/users/telemetry/status` - Get user's telemetry preference
   - `PUT /api/users/telemetry/enable` - Opt-in to telemetry
   - `PUT /api/users/telemetry/disable` - Opt-out of telemetry

4. **User Model Update** (`apps/backend/src/rhesis/backend/app/models/user.py`)
   - Added `telemetry_enabled` field (default: False)

5. **Dependencies** (`apps/backend/pyproject.toml`)
   - Added OpenTelemetry packages

### Frontend Changes

1. **Telemetry SDK** (`apps/frontend/src/lib/telemetry.ts`)
   - Initialize OpenTelemetry for browser
   - Track page views, events, feature usage
   - Hash user/org IDs for privacy

2. **UI Components**
   - `src/components/settings/TelemetrySettings.tsx` - Settings page component
   - `src/components/telemetry/TelemetryOptInDialog.tsx` - First-time opt-in dialog

3. **Dependencies** (`apps/frontend/package.json`)
   - Added OpenTelemetry browser packages

### Configuration

1. **Docker Compose** (`docker-compose.yml`)
   - Added telemetry environment variables
   - Included commented telemetry services (optional for self-hosted)

2. **Environment Variables** (`.env.example`)
   - Added telemetry configuration section
   - Clear opt-in instructions

### Documentation

1. **TELEMETRY.md** - Comprehensive telemetry guide
   - Architecture overview
   - Data collection details
   - Configuration instructions
   - API reference
   - Looker Studio queries

2. **TELEMETRY_SETUP.md** - Step-by-step setup guide
   - Quick start for self-hosted users
   - Cloud deployment instructions
   - Database setup
   - Looker Studio configuration
   - Troubleshooting guide

## 🏗️ Architecture

```
User Instances → OpenTelemetry Collector → Telemetry Processor → PostgreSQL → Looker Studio
```

### Data Flow

1. **User enables telemetry** in Settings → Privacy
2. **Application SDKs** (backend + frontend) track events
3. **Conditional export** - Only if user opted in
4. **OTLP over HTTPS** - Data sent to cloud collector
5. **Collector processes** - Filters sensitive data, adds metadata
6. **Processor transforms** - Converts OTLP to SQL inserts
7. **Database stores** - Analytics tables for querying
8. **Looker Studio visualizes** - Dashboards and reports

## 📊 Data Collected

### User Activity Events
- Login/logout events
- Session duration
- Last active timestamps
- Return visit patterns

### Endpoint Usage
- API endpoint calls
- HTTP methods and status codes
- Response times (performance)
- Error rates

### Feature Usage
- Feature-specific actions (created, viewed, updated)
- Feature adoption rates
- User engagement patterns

## 🔒 Privacy Features

✅ **Opt-in by default** (self-hosted)
✅ **User-controlled** (can disable anytime)
✅ **One-way hashing** of user/org IDs
✅ **No PII collection** (emails, names, IP addresses)
✅ **Sensitive data filtering** (passwords, tokens, API keys)
✅ **Transparent disclosure** (what we collect/don't collect)

## 🚀 Deployment

### For Self-Hosted Users

**Default: Telemetry Disabled**

To opt-in (optional):
1. Enable in Settings → Privacy
2. Optionally set environment variables:
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=https://telemetry.rhesis.ai
   NEXT_PUBLIC_OTEL_ENDPOINT=https://telemetry.rhesis.ai
   ```

### For Cloud Deployment

1. Deploy OpenTelemetry Collector to Cloud Run
2. Deploy Telemetry Processor to Cloud Run
3. Run database migrations
4. Set environment variables in services
5. Connect Looker Studio to analytics database

See `TELEMETRY_SETUP.md` for detailed instructions.

## 📝 Next Steps

### Immediate

1. **Test the implementation**
   - Run migrations: `alembic upgrade head`
   - Start services: `docker-compose up`
   - Enable telemetry in UI
   - Verify data in analytics tables

2. **Deploy to production**
   - Deploy otel-collector to Cloud Run
   - Deploy telemetry-processor to Cloud Run
   - Update environment variables
   - Run migrations on production database

### Future Enhancements

1. **Analytics Dashboard**
   - Create Looker Studio dashboards
   - Set up retention cohort analysis
   - Monitor feature adoption rates

2. **Alerts & Monitoring**
   - Set up alerts for error rate spikes
   - Monitor telemetry service health
   - Track data volume and storage

3. **Advanced Analytics**
   - User journey analysis
   - Feature funnel visualization
   - A/B test support

## 📚 Documentation

- **TELEMETRY.md** - Comprehensive technical documentation
- **TELEMETRY_SETUP.md** - Step-by-step setup guide
- **API Reference** - Telemetry endpoints in TELEMETRY.md
- **Database Schema** - Analytics tables structure

## 🐛 Troubleshooting

Common issues and solutions are documented in `TELEMETRY_SETUP.md`.

Quick checks:
1. User has `telemetry_enabled = true`
2. Environment variables are set correctly
3. Collector is reachable (health check: `/health`)
4. Database tables exist (`analytics_*`)

## 🤝 Contributing

When adding new features:
1. Add telemetry tracking using `track_feature_usage()`
2. Document what data is collected
3. Ensure sensitive data is filtered
4. Test with telemetry enabled/disabled

## 📧 Support

- Email: support@rhesis.ai
- Docs: https://docs.rhesis.ai/telemetry
- Privacy: https://rhesis.ai/privacy

---

## File Structure

```
rhesis/
├── apps/
│   ├── otel-collector/          # OpenTelemetry Collector service
│   │   ├── Dockerfile
│   │   ├── otel-collector-config.yaml
│   │   └── README.md
│   │
│   ├── telemetry-processor/     # Telemetry data processor
│   │   ├── src/
│   │   │   └── processor.py
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── backend/
│   │   ├── src/rhesis/backend/
│   │   │   ├── telemetry/       # Telemetry instrumentation
│   │   │   │   ├── __init__.py
│   │   │   │   ├── instrumentation.py
│   │   │   │   └── middleware.py
│   │   │   ├── alembic/versions/ # Migrations
│   │   │   │   ├── a1b2c3d4e5f7_*.py
│   │   │   │   └── a1b2c3d4e5f8_*.py
│   │   │   └── app/
│   │   │       ├── models/user.py (updated)
│   │   │       └── routers/user.py (updated)
│   │   └── pyproject.toml (updated)
│   │
│   └── frontend/
│       ├── src/
│       │   ├── lib/
│       │   │   └── telemetry.ts # Telemetry SDK
│       │   └── components/
│       │       ├── settings/
│       │       │   └── TelemetrySettings.tsx
│       │       └── telemetry/
│       │           └── TelemetryOptInDialog.tsx
│       └── package.json (updated)
│
├── docs/
│   ├── TELEMETRY.md             # Comprehensive guide
│   ├── TELEMETRY_SETUP.md       # Setup instructions
│   └── telemetry/
│       └── README.md            # This file
│
└── docker-compose.yml (updated)
```

## Environment Variables Reference

### Backend
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=<collector-url>
OTEL_SERVICE_NAME=rhesis-backend
DEPLOYMENT_TYPE=self_hosted|cloud
```

### Frontend
```bash
NEXT_PUBLIC_OTEL_ENDPOINT=<collector-url>
NEXT_PUBLIC_DEPLOYMENT_TYPE=self_hosted|cloud
```

### Telemetry Services
```bash
TELEMETRY_PROCESSOR_ENDPOINT=<processor-url>
DATABASE_URL=<postgres-connection-string>
```

---

**Implementation Status:** ✅ Complete and ready for deployment
**Last Updated:** 2025-10-21
**Version:** 0.4.0

