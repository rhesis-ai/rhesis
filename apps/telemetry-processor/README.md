# Telemetry Processor Service

gRPC service that receives OpenTelemetry traces from the OTel Collector and writes analytics data to a dedicated PostgreSQL database.

## Overview

The Telemetry Processor:
- Receives OTLP (OpenTelemetry Protocol) traces via gRPC
- Processes traces into structured analytics data
- Stores data in a separate PostgreSQL analytics database
- Provides privacy through ID hashing (SHA-256)

## Architecture

```
┌──────────┐      OTLP      ┌─────────────────┐     gRPC     ┌────────────────────┐
│ Backend  │─────────────►  │  OTel Collector │─────────────► │ Telemetry Processor│
│ Frontend │   HTTP/gRPC    └─────────────────┘               └────────────────────┘
└──────────┘                                                            │
                                                                        │ SQL
                                                                        ▼
                                                            ┌───────────────────────┐
                                                            │ postgres-analytics    │
                                                            │ (Separate Database)   │
                                                            └───────────────────────┘
```

## Separate Analytics Database

The telemetry processor uses a **dedicated PostgreSQL database** separate from the main application database.

### Why Separate Database?

✅ **Isolation**: Analytics data doesn't affect operational database performance  
✅ **Security**: Can be managed with different access controls  
✅ **Scalability**: Can scale independently based on analytics volume  
✅ **Backup**: Different backup/retention policies for analytics vs operational data  
✅ **Privacy**: Easier to manage data retention and compliance

### Database Configuration

The service connects to a separate database using these environment variables:

```bash
# Analytics Database Configuration
ANALYTICS_DB_USER=your-db-username        # Database user
ANALYTICS_DB_PASS=your-secure-password    # Database password
ANALYTICS_DB_HOST=your-database-host      # Database host (e.g., localhost, postgres-analytics)
ANALYTICS_DB_PORT=5432                    # Database port
ANALYTICS_DB_NAME=your-database-name      # Database name

# Or use full connection string
ANALYTICS_DATABASE_URL=postgresql://user:password@host:port/dbname
```

## Tables

The analytics database contains three tables:

### 1. `user_activity`
Tracks user engagement events (login, logout, sessions)

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | VARCHAR(32) | Hashed user ID (SHA-256, 16 chars) |
| `organization_id` | VARCHAR(32) | Hashed org ID |
| `event_type` | VARCHAR(50) | Event type (login, logout, etc.) |
| `timestamp` | TIMESTAMP | Event timestamp |
| `session_id` | VARCHAR(255) | Session identifier |
| `deployment_type` | VARCHAR(50) | cloud / self-hosted |
| `event_metadata` | JSONB | Additional event data |

### 2. `endpoint_usage`
Tracks API endpoint usage and performance

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `endpoint` | VARCHAR(255) | API endpoint path |
| `method` | VARCHAR(10) | HTTP method |
| `user_id` | VARCHAR(32) | Hashed user ID |
| `organization_id` | VARCHAR(32) | Hashed org ID |
| `status_code` | INTEGER | HTTP status code |
| `duration_ms` | DOUBLE PRECISION | Request duration |
| `timestamp` | TIMESTAMP | Event timestamp |
| `deployment_type` | VARCHAR(50) | cloud / self-hosted |
| `event_metadata` | JSONB | Additional metadata |

### 3. `feature_usage`
Tracks feature-specific usage patterns

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `feature_name` | VARCHAR(100) | Feature identifier |
| `user_id` | VARCHAR(32) | Hashed user ID |
| `organization_id` | VARCHAR(32) | Hashed org ID |
| `action` | VARCHAR(100) | Action (created, viewed, updated, deleted) |
| `timestamp` | TIMESTAMP | Event timestamp |
| `deployment_type` | VARCHAR(50) | cloud / self-hosted |
| `event_metadata` | JSONB | Additional metadata |

## Local Development

### Starting with Docker Compose

```bash
# Start all services including analytics database
docker-compose up -d postgres-analytics telemetry-processor

# View logs
docker-compose logs -f telemetry-processor

# Check analytics database
docker-compose exec postgres-analytics psql -U your-db-username -d your-database-name
```

### Environment Variables

Create a `.env` file from the template:

```bash
# Copy the example file
cp env.txt .env

# Edit with your values
vim .env
```

Required variables:
```bash
# Analytics Database (separate from main database)
ANALYTICS_DB_USER=your-db-username
ANALYTICS_DB_PASS=your-secure-password
ANALYTICS_DB_HOST=your-database-host      # e.g., localhost, postgres-analytics
ANALYTICS_DB_PORT=5432
ANALYTICS_DB_NAME=your-database-name

# Or use full connection string:
# ANALYTICS_DATABASE_URL=postgresql://username:password@host:port/dbname

# Service Configuration
PORT=4317  # gRPC port

# Logging
LOG_LEVEL=INFO
```

### Database Migrations

The analytics database uses **Alembic** for schema management (same as the backend).

Migrations are located at:
```
apps/telemetry-processor/alembic/versions/
```

Migrations run automatically when the container starts via the `migrate.sh` script.

#### Manual Migration Commands

```bash
# Run migrations
cd apps/telemetry-processor
./migrate.sh

# Or use alembic directly
alembic upgrade head

# Create a new migration
alembic revision -m "description"

# Rollback one migration
alembic downgrade -1

# Check current version
alembic current
```

## Privacy & Security

### ID Hashing

All user and organization IDs are hashed using SHA-256 before storage:

```python
# Backend (Python)
hashlib.sha256(id_str.encode()).hexdigest()[:16]

# Frontend (TypeScript)
crypto.subtle.digest('SHA-256', data).then(hash => hash.substring(0, 16))
```

**Properties:**
- ✅ One-way: Cannot recover original IDs
- ✅ Consistent: Same ID always produces same hash
- ✅ Anonymous: No PII stored
- ✅ Sufficient: 2^64 unique values (collision-resistant)

### Data Access

The analytics database should be:
- Accessible only to the telemetry processor service
- Not exposed to public internet
- Protected with strong authentication
- Regularly backed up with defined retention policies

## Cloud Deployment

### Google Cloud Run

The telemetry processor can be deployed to Cloud Run with Cloud SQL for the analytics database.

#### Environment Variables for Cloud

```bash
# Cloud SQL Connection
ANALYTICS_DATABASE_URL=postgresql://username:password@/dbname?host=/cloudsql/PROJECT-ID:REGION:INSTANCE-NAME

# Or use Cloud SQL Proxy
ANALYTICS_DB_HOST=/cloudsql/PROJECT-ID:REGION:INSTANCE-NAME
ANALYTICS_DB_NAME=your-database-name
```

#### Deployment Workflow

See `.github/workflows/telemetry-processor.yml` for automated deployment.

## Monitoring

### Health Check

The processor includes health monitoring. Check status:

```bash
# Docker
docker-compose ps telemetry-processor

# Logs
docker-compose logs telemetry-processor
```

### Database Queries

Check data collection:

```sql
-- Count events by type
SELECT 
    'user_activity' as table_name, 
    COUNT(*) as count 
FROM user_activity
UNION ALL
SELECT 
    'endpoint_usage', 
    COUNT(*) 
FROM endpoint_usage
UNION ALL
SELECT 
    'feature_usage', 
    COUNT(*) 
FROM feature_usage;

-- Recent user activity
SELECT 
    event_type,
    COUNT(*) as count,
    MAX(timestamp) as latest
FROM user_activity
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY event_type;

-- Top endpoints
SELECT 
    endpoint,
    method,
    COUNT(*) as hits,
    AVG(duration_ms) as avg_duration_ms
FROM endpoint_usage
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY endpoint, method
ORDER BY hits DESC
LIMIT 10;
```

## Troubleshooting

### Connection Issues

If the processor can't connect to the database:

```bash
# Check if analytics database is running
docker-compose ps postgres-analytics

# Check logs
docker-compose logs postgres-analytics

# Test connection manually
docker-compose exec postgres-analytics psql -U your-db-username -d your-database-name -c "SELECT 1;"
```

### No Data Appearing

1. Check if telemetry is enabled:
   ```bash
   # For self-hosted
   TELEMETRY_ENABLED=true
   DEPLOYMENT_TYPE=self-hosted
   ```

2. Verify OTel Collector is forwarding to processor:
   ```bash
   docker-compose logs otel-collector
   ```

3. Check processor logs for errors:
   ```bash
   docker-compose logs telemetry-processor
   ```

### Performance Issues

If the processor is slow:

1. Check database indexes:
   ```sql
   SELECT * FROM pg_indexes 
   WHERE tablename IN ('user_activity', 'endpoint_usage', 'feature_usage');
   ```

2. Monitor connection pool:
   ```sql
   SELECT * FROM pg_stat_activity 
   WHERE datname = 'your-database-name';
   ```

3. Consider increasing pool size in connection.py

## Development

### Project Structure

```
apps/telemetry-processor/
├── src/
│   └── processor/
│       ├── main.py                    # Entry point
│       ├── models/
│       │   ├── base.py                # Base model with common fields
│       │   └── analytics.py           # Analytics table models
│       ├── database/
│       │   └── connection.py          # Database connection manager
│       ├── services/
│       │   ├── base.py                # Base processor interface
│       │   ├── user_activity.py       # User activity processor
│       │   ├── endpoint_usage.py      # Endpoint usage processor
│       │   ├── feature_usage.py       # Feature usage processor
│       │   └── span_router.py         # Span routing logic
│       ├── grpc/
│       │   └── trace_service.py       # gRPC service implementation
│       └── utils/
│           └── attribute_extractor.py # Span attribute extraction
├── alembic/
│   ├── versions/                      # Database migrations
│   │   └── 001_initial_analytics_tables.py  # Creates: user_activity, endpoint_usage, feature_usage
│   ├── env.py                         # Alembic environment config
│   └── script.py.mako                 # Migration template
├── alembic.ini                        # Alembic configuration
├── migrate.sh                         # Migration runner script
├── Dockerfile                         # Container definition
├── pyproject.toml                     # Python dependencies
├── env.txt                            # Environment variables template
└── README.md                          # This file
```

### Adding New Analytics Tables

1. Add model to `src/processor/models/analytics.py`:
   ```python
   class NewAnalytics(AnalyticsBase):
       __tablename__ = "new_feature"
       
       # Add table-specific fields
       feature_field = Column(String(100))
   ```

2. Create Alembic migration:
   ```bash
   alembic revision -m "add new analytics table"
   ```

3. Edit the migration file to add the table:
   ```python
   def upgrade():
       op.create_table(
           'new_feature',
           sa.Column('id', postgresql.UUID(), ...),
           # ... columns
       )
   ```

4. Add processor service:
   ```python
   class NewAnalyticsProcessor(BaseSpanProcessor):
       def process_span(self, span, resource, session):
           # Process logic
   ```

5. Update `span_router.py` to route new events

6. Run migration:
   ```bash
   alembic upgrade head
   ```

## License

See LICENSE file in the repository root.
