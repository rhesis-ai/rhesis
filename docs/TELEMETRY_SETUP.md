# OpenTelemetry Setup Guide

This guide walks you through setting up the OpenTelemetry telemetry collection system for Rhesis.

## Quick Start

### For Self-Hosted Users (Opting In)

1. **Check Your Settings**
   - Telemetry is disabled by default
   - You need to opt-in to share anonymous usage data

2. **Optional: Set Environment Variables** (if you want to help improve Rhesis)
   
   Add to your `.env` file:
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=https://telemetry.rhesis.ai
   NEXT_PUBLIC_OTEL_ENDPOINT=https://telemetry.rhesis.ai
   DEPLOYMENT_TYPE=self_hosted
   ```

3. **Enable in Application**
   - Go to Settings → Privacy
   - Toggle "Share anonymous usage data" to ON
   - You're done! Thank you for helping improve Rhesis 🎉

### For Cloud/SaaS Deployment

1. **Deploy OpenTelemetry Services**
   
   Deploy the following services to Google Cloud Run:

   **OpenTelemetry Collector:**
   ```bash
   cd apps/otel-collector
   gcloud run deploy otel-collector \
     --source . \
     --port 4318 \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars TELEMETRY_PROCESSOR_ENDPOINT=telemetry-processor:4317
   ```

   **Telemetry Processor:**
   ```bash
   cd apps/telemetry-processor
   gcloud run deploy telemetry-processor \
     --source . \
     --port 4317 \
     --region us-central1 \
     --set-env-vars DATABASE_URL="postgresql://..."
   ```

2. **Configure Backend**
   
   Set environment variables in your backend deployment:
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
   OTEL_SERVICE_NAME=rhesis-backend-cloud
   DEPLOYMENT_TYPE=cloud
   ```

3. **Configure Frontend**
   
   Set environment variables in your frontend deployment:
   ```bash
   NEXT_PUBLIC_OTEL_ENDPOINT=https://telemetry.rhesis.ai
   NEXT_PUBLIC_DEPLOYMENT_TYPE=cloud
   ```

4. **Run Database Migrations**
   
   Apply the telemetry migrations:
   ```bash
   cd apps/backend
   source venv/bin/activate
   alembic upgrade head
   ```

## Database Setup

### Apply Migrations

The telemetry system requires three new database tables. Apply migrations:

```bash
cd apps/backend
source venv/bin/activate
cd src/rhesis/backend
alembic upgrade head
```

This will create:
- `analytics_user_activity` - User login/logout events
- `analytics_endpoint_usage` - API endpoint usage tracking
- `analytics_feature_usage` - Feature-specific usage tracking
- `user.telemetry_enabled` column - User opt-in preference

### Manual Table Creation (if needed)

If you prefer to create tables manually:

```sql
-- Create analytics tables
CREATE TABLE analytics_user_activity (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    organization_id UUID,
    event_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    session_id VARCHAR(255),
    deployment_type VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_activity_user_timestamp ON analytics_user_activity(user_id, timestamp);
CREATE INDEX idx_user_activity_deployment_timestamp ON analytics_user_activity(deployment_type, timestamp);

CREATE TABLE analytics_endpoint_usage (
    id UUID PRIMARY KEY,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10),
    user_id UUID,
    organization_id UUID,
    status_code INTEGER,
    duration_ms FLOAT,
    timestamp TIMESTAMP NOT NULL,
    deployment_type VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_endpoint_usage_endpoint_timestamp ON analytics_endpoint_usage(endpoint, timestamp);
CREATE INDEX idx_endpoint_usage_deployment_timestamp ON analytics_endpoint_usage(deployment_type, timestamp);

CREATE TABLE analytics_feature_usage (
    id UUID PRIMARY KEY,
    feature_name VARCHAR(100) NOT NULL,
    user_id UUID,
    organization_id UUID,
    action VARCHAR(100),
    timestamp TIMESTAMP NOT NULL,
    deployment_type VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_feature_usage_feature_timestamp ON analytics_feature_usage(feature_name, timestamp);
CREATE INDEX idx_feature_usage_deployment_timestamp ON analytics_feature_usage(deployment_type, timestamp);

-- Add telemetry_enabled to user table
ALTER TABLE "user" ADD COLUMN telemetry_enabled BOOLEAN DEFAULT FALSE;
CREATE INDEX idx_user_telemetry_enabled ON "user"(telemetry_enabled);
```

## Google Looker Studio Setup

### 1. Connect to PostgreSQL

1. Open Google Looker Studio
2. Create a new data source
3. Select "PostgreSQL"
4. Enter your database connection details:
   - Host: Your PostgreSQL host
   - Port: 5432
   - Database: rhesis-db
   - Table: Start with `analytics_user_activity`

### 2. Create Custom Queries

Create data sources with custom SQL queries:

**Daily Active Users:**
```sql
SELECT 
    DATE(timestamp) as date,
    deployment_type,
    COUNT(DISTINCT user_id) as daily_active_users
FROM analytics_user_activity
WHERE event_type = 'login'
    AND timestamp >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY date, deployment_type
ORDER BY date DESC
```

**Feature Adoption:**
```sql
SELECT 
    feature_name,
    deployment_type,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(*) as total_uses
FROM analytics_feature_usage
WHERE timestamp >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY feature_name, deployment_type
ORDER BY unique_users DESC
```

**API Performance:**
```sql
SELECT 
    endpoint,
    method,
    AVG(duration_ms) as avg_duration,
    COUNT(*) as request_count,
    deployment_type
FROM analytics_endpoint_usage
WHERE timestamp >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY endpoint, method, deployment_type
ORDER BY request_count DESC
```

### 3. Create Dashboards

Create dashboards with the following charts:

**Retention Dashboard:**
- Daily/Weekly/Monthly Active Users (line chart)
- Retention cohorts (table)
- User growth rate (scorecard)

**Feature Usage Dashboard:**
- Most used features (bar chart)
- Feature adoption over time (line chart)
- Cloud vs Self-hosted usage split (pie chart)

**Performance Dashboard:**
- Average response time by endpoint (bar chart)
- P95 response time trend (line chart)
- Error rate by endpoint (table)

## Testing

### Test Telemetry Locally

1. **Enable Telemetry Locally** (optional for testing)
   
   Uncomment the otel-collector services in `docker-compose.yml`:
   ```yaml
   otel-collector:
     build:
       context: ./apps/otel-collector
       dockerfile: Dockerfile
     # ... rest of config
   ```

2. **Set Environment Variables**
   ```bash
   OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
   NEXT_PUBLIC_OTEL_ENDPOINT=http://localhost:4318
   ```

3. **Start Services**
   ```bash
   docker-compose up -d
   ```

4. **Enable Telemetry in UI**
   - Log in to the application
   - Go to Settings → Privacy
   - Enable telemetry

5. **Generate Test Data**
   - Navigate around the application
   - Create test runs, metrics, etc.
   - Check the `analytics_*` tables for data

6. **Verify Data**
   ```sql
   SELECT * FROM analytics_user_activity ORDER BY timestamp DESC LIMIT 10;
   SELECT * FROM analytics_endpoint_usage ORDER BY timestamp DESC LIMIT 10;
   SELECT * FROM analytics_feature_usage ORDER BY timestamp DESC LIMIT 10;
   ```

## Troubleshooting

### Telemetry Data Not Appearing

1. **Check User Setting**
   ```sql
   SELECT id, email, telemetry_enabled FROM "user";
   ```
   Ensure `telemetry_enabled` is `true` for your test user.

2. **Check Environment Variables**
   ```bash
   docker exec rhesis-backend env | grep OTEL
   docker exec rhesis-frontend env | grep OTEL
   ```

3. **Check Collector Logs**
   ```bash
   docker logs rhesis-otel-collector
   docker logs rhesis-telemetry-processor
   ```

4. **Test Collector Endpoint**
   ```bash
   curl http://localhost:13133  # Health check
   ```

### Performance Issues

If telemetry is causing performance issues:

1. **Check Timeout Settings**
   - Telemetry requests timeout after 5 seconds
   - They should not block the main application

2. **Check Network Connectivity**
   ```bash
   curl -I https://telemetry.rhesis.ai
   ```

3. **Disable Temporarily**
   ```bash
   unset OTEL_EXPORTER_OTLP_ENDPOINT
   unset NEXT_PUBLIC_OTEL_ENDPOINT
   ```

### Database Issues

1. **Check Tables Exist**
   ```sql
   SELECT table_name FROM information_schema.tables 
   WHERE table_name LIKE 'analytics_%';
   ```

2. **Check Indexes**
   ```sql
   SELECT indexname FROM pg_indexes 
   WHERE tablename LIKE 'analytics_%';
   ```

3. **Check Data Volume**
   ```sql
   SELECT 
       schemaname,
       tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables
   WHERE tablename LIKE 'analytics_%'
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
   ```

## Privacy Considerations

### What We Collect

✅ **Anonymous usage patterns**
✅ **Performance metrics**
✅ **Feature adoption rates**
✅ **Error rates**

### What We Don't Collect

❌ **Email addresses or names**
❌ **Test data or prompts**
❌ **API keys or credentials**
❌ **IP addresses**
❌ **Any PII**

### Data Retention

- Raw telemetry data: 12 months
- Aggregated analytics: Indefinitely
- User IDs are one-way hashed before transmission

## Support

For help with telemetry setup:
- Email: support@rhesis.ai
- Documentation: https://docs.rhesis.ai/telemetry
- GitHub Issues: https://github.com/rhesis/rhesis/issues

