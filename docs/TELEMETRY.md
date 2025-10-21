# OpenTelemetry Integration for Rhesis

This document describes how telemetry data collection works in Rhesis and how to configure it.

## Overview

Rhesis uses OpenTelemetry to collect anonymous usage data that helps us understand how the product is used and where we can improve. This works for both our cloud-hosted web app and self-hosted installations.

### What Data is Collected?

**We DO collect:**
- Feature usage statistics (which features are used and how often)
- API endpoint usage and response times
- Page views and navigation patterns
- Error rates and performance metrics
- User retention patterns (login frequency, session duration)

**We DON'T collect:**
- Email addresses, names, or any personally identifiable information (PII)
- Test data, prompts, or LLM responses
- API keys, tokens, or credentials
- IP addresses
- Any sensitive business data

All user and organization IDs are one-way hashed before being sent, ensuring anonymity.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER'S ENVIRONMENT                            │
│  ┌──────────────┐              ┌──────────────┐                │
│  │  Frontend    │              │   Backend    │                │
│  │  + OTEL SDK  │              │  + OTEL SDK  │                │
│  └──────┬───────┘              └──────┬───────┘                │
│         │                             │                         │
│         │ (If telemetry_enabled=true) │                         │
│         └──────────OTLP/HTTPS────────┘                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ Internet
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RHESIS CLOUD INFRASTRUCTURE                    │
│  ┌────────────────────────────────────────────┐                │
│  │  OpenTelemetry Collector (Cloud Run)       │                │
│  │  https://telemetry.rhesis.ai               │                │
│  └────────────────────┬───────────────────────┘                │
│                       │                                          │
│                       ▼                                          │
│  ┌────────────────────────────────────────────┐                │
│  │  Telemetry Processor (gRPC Service)        │                │
│  └────────────────────┬───────────────────────┘                │
│                       │                                          │
│                       ▼                                          │
│  ┌────────────────────────────────────────────┐                │
│  │  PostgreSQL (Analytics Database)           │                │
│  │  - analytics_user_activity                 │                │
│  │  - analytics_endpoint_usage                │                │
│  │  - analytics_feature_usage                 │                │
│  └────────────────────┬───────────────────────┘                │
│                       │                                          │
│                       ▼                                          │
│  ┌────────────────────────────────────────────┐                │
│  │  Google Looker Studio                      │                │
│  └────────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

## User Controls

### For Self-Hosted Users

Telemetry is **disabled by default** for self-hosted installations. Users must explicitly opt-in.

**To opt-in:**
1. Navigate to Settings → Privacy
2. Toggle "Share anonymous usage data"
3. Optionally set environment variables:
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=https://telemetry.rhesis.ai
   NEXT_PUBLIC_OTEL_ENDPOINT=https://telemetry.rhesis.ai
   DEPLOYMENT_TYPE=self_hosted
   ```

### For Cloud/SaaS Users

Telemetry is **enabled by default** (with user notice), but users can opt-out at any time.

**To opt-out:**
1. Navigate to Settings → Privacy
2. Toggle off "Share anonymous usage data"

## Configuration

### Environment Variables

#### Backend Configuration

```bash
# OpenTelemetry Collector endpoint
# Leave empty to disable telemetry entirely
OTEL_EXPORTER_OTLP_ENDPOINT=https://telemetry.rhesis.ai

# Service name for telemetry
OTEL_SERVICE_NAME=rhesis-backend

# Deployment type (cloud, self_hosted)
DEPLOYMENT_TYPE=self_hosted
```

#### Frontend Configuration

```bash
# OpenTelemetry Collector endpoint (public)
# Leave empty to disable telemetry entirely
NEXT_PUBLIC_OTEL_ENDPOINT=https://telemetry.rhesis.ai

# Deployment type (cloud, self_hosted)
NEXT_PUBLIC_DEPLOYMENT_TYPE=self_hosted
```

### For Self-Hosted Installations

Add to your `.env` file:

```bash
# Telemetry (Optional - only if you want to help improve Rhesis)
# Leave empty to disable telemetry
OTEL_EXPORTER_OTLP_ENDPOINT=
NEXT_PUBLIC_OTEL_ENDPOINT=

# If you opt-in, uncomment below:
# OTEL_EXPORTER_OTLP_ENDPOINT=https://telemetry.rhesis.ai
# NEXT_PUBLIC_OTEL_ENDPOINT=https://telemetry.rhesis.ai
# DEPLOYMENT_TYPE=self_hosted
```

### For Cloud Deployment

Set in your infrastructure configuration:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318  # Internal service
NEXT_PUBLIC_OTEL_ENDPOINT=https://telemetry.rhesis.ai   # Public endpoint
DEPLOYMENT_TYPE=cloud
```

## Database Schema

### analytics_user_activity

Tracks user login, logout, and session events.

| Column           | Type      | Description                        |
|------------------|-----------|------------------------------------|
| id               | UUID      | Primary key                        |
| user_id          | UUID      | Hashed user ID                     |
| organization_id  | UUID      | Hashed organization ID             |
| event_type       | String    | login, logout, session_start, etc. |
| timestamp        | DateTime  | Event timestamp                    |
| session_id       | String    | Session identifier                 |
| deployment_type  | String    | cloud or self_hosted               |
| metadata         | JSONB     | Additional event data              |

### analytics_endpoint_usage

Tracks API endpoint calls and performance.

| Column           | Type      | Description                        |
|------------------|-----------|------------------------------------|
| id               | UUID      | Primary key                        |
| endpoint         | String    | API endpoint path                  |
| method           | String    | HTTP method (GET, POST, etc.)      |
| user_id          | UUID      | Hashed user ID                     |
| organization_id  | UUID      | Hashed organization ID             |
| status_code      | Integer   | HTTP status code                   |
| duration_ms      | Float     | Request duration in milliseconds   |
| timestamp        | DateTime  | Request timestamp                  |
| deployment_type  | String    | cloud or self_hosted               |
| metadata         | JSONB     | Additional request data            |

### analytics_feature_usage

Tracks feature-specific usage events.

| Column           | Type      | Description                        |
|------------------|-----------|------------------------------------|
| id               | UUID      | Primary key                        |
| feature_name     | String    | Feature name                       |
| user_id          | UUID      | Hashed user ID                     |
| organization_id  | UUID      | Hashed organization ID             |
| action           | String    | Action performed (created, viewed) |
| timestamp        | DateTime  | Event timestamp                    |
| deployment_type  | String    | cloud or self_hosted               |
| metadata         | JSONB     | Additional feature data            |

## API Endpoints

### Get Telemetry Status

```http
GET /api/users/telemetry/status
Authorization: Bearer <session_token>
```

**Response:**
```json
{
  "telemetry_enabled": false,
  "user_id": "uuid"
}
```

### Enable Telemetry

```http
PUT /api/users/telemetry/enable
Authorization: Bearer <session_token>
```

**Response:**
```json
{
  "telemetry_enabled": true,
  "message": "Thank you for helping improve Rhesis!"
}
```

### Disable Telemetry

```http
PUT /api/users/telemetry/disable
Authorization: Bearer <session_token>
```

**Response:**
```json
{
  "telemetry_enabled": false,
  "message": "Telemetry has been disabled."
}
```

## Implementation Details

### Backend

The backend uses conditional span processing to respect user preferences:

```python
from rhesis.backend.telemetry import track_feature_usage, track_user_activity

# Track user login
track_user_activity("login", session_id=session.id)

# Track feature usage
track_feature_usage("test_run", "created", test_id=test_run.id)
```

### Frontend

The frontend provides telemetry utilities:

```typescript
import { trackPageView, trackEvent, trackFeatureUsage } from '@/lib/telemetry';

// Track page view
trackPageView('/dashboard', userId, organizationId);

// Track custom event
trackEvent('button_click', { button_id: 'create_test' }, userId, organizationId);

// Track feature usage
trackFeatureUsage('test_run', 'created', { test_id: '123' }, userId, organizationId);
```

## Privacy & Compliance

### GDPR Compliance

- **Right to opt-out**: Users can disable telemetry at any time
- **Data minimization**: We collect only anonymous, aggregated data
- **Purpose limitation**: Data is used solely for product improvement
- **Transparency**: Clear disclosure of what data is collected

### Data Retention

- Telemetry data is retained for 12 months
- Aggregated analytics are retained indefinitely
- Users can request data deletion by contacting support

## Looker Studio Queries

### Daily Active Users (DAU)

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
    deployment_type,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(*) as total_uses
FROM analytics_feature_usage
WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY feature_name, deployment_type
ORDER BY unique_users DESC;
```

### API Endpoint Performance

```sql
SELECT 
    endpoint,
    method,
    AVG(duration_ms) as avg_duration,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration,
    COUNT(*) as request_count,
    SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) as error_count
FROM analytics_endpoint_usage
WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY endpoint, method
ORDER BY request_count DESC;
```

### 7-Day Retention Rate

```sql
WITH first_login AS (
    SELECT user_id, MIN(timestamp) as first_login_date
    FROM analytics_user_activity
    WHERE event_type = 'login'
    GROUP BY user_id
),
return_users AS (
    SELECT 
        f.user_id,
        f.first_login_date,
        MAX(a.timestamp) as last_login_date
    FROM first_login f
    LEFT JOIN analytics_user_activity a 
        ON f.user_id = a.user_id 
        AND a.event_type = 'login'
        AND a.timestamp > f.first_login_date
        AND a.timestamp <= f.first_login_date + INTERVAL '7 days'
    GROUP BY f.user_id, f.first_login_date
)
SELECT 
    COUNT(DISTINCT user_id) as total_users,
    COUNT(DISTINCT CASE WHEN last_login_date IS NOT NULL THEN user_id END) as retained_users,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN last_login_date IS NOT NULL THEN user_id END) / COUNT(DISTINCT user_id), 2) as retention_rate
FROM return_users
WHERE first_login_date >= CURRENT_DATE - INTERVAL '30 days';
```

## Troubleshooting

### Telemetry not working

1. Check environment variables are set correctly
2. Verify user has telemetry enabled in settings
3. Check network connectivity to telemetry endpoint
4. Review backend logs for telemetry errors

### Performance issues

If telemetry is causing performance issues:
1. Telemetry requests timeout after 5 seconds and don't block the app
2. Consider temporarily disabling telemetry
3. Report the issue to the Rhesis team

## Support

For questions or issues related to telemetry:
- Email: support@rhesis.ai
- Documentation: https://docs.rhesis.ai/telemetry
- Privacy Policy: https://rhesis.ai/privacy

