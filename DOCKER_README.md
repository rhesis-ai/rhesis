# Rhesis Docker Setup

This guide will help you run the entire Rhesis project using Docker Compose.

## Prerequisites

- Docker Desktop installed and running
- Git (to clone the repository)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd rhesis
   ```

2. **Copy environment variables**
   ```bash
   cp env.example .env
   ```

3. **Edit the `.env` file** (optional)
   - Update the Auth0 configuration
   - Update any other environment variables as needed

4. **Start all services**
   ```bash
   docker-compose up -d
   ```

5. **Access the applications**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8080

## 🚀 Automated Database Migration

**No manual database setup required!** The system automatically:

- ✅ Creates the PostgreSQL database and user
- ✅ Sets proper database ownership and permissions
- ✅ Runs all Alembic migrations automatically
- ✅ Creates all necessary tables and relationships
- ✅ Handles migration status checking (won't re-run if already migrated)

The backend container will:
1. Wait for PostgreSQL to be ready
2. Set database ownership
3. Run all pending migrations
4. Start the FastAPI application

## Services Overview

### Core Services

| Service | Port | Description | Health Check |
|---------|------|-------------|--------------|
| **PostgreSQL** | 5432 | Database | `pg_isready` |
| **Redis** | 6379 | Cache & Message Broker | `redis-cli ping` |
| **Backend** | 8080 | FastAPI Application | `curl /health` |
| **Worker** | 8081 | Celery Background Tasks | - |
| **Frontend** | 3000 | Next.js Application | - |

### Service Dependencies

```
Frontend → Backend → PostgreSQL
    ↓         ↓
Worker → Redis
```

## Environment Variables

### Required Variables

Create a `.env` file in the root directory with:

```bash
# Auth0 Configuration
AUTH0_DOMAIN=your-auth0-domain
AUTH0_AUDIENCE=your-auth0-audience
AUTH0_CLIENT_ID=your-auth0-client-id
AUTH0_CLIENT_SECRET=your-auth0-client-secret
AUTH0_SECRET_KEY=your-auth0-secret-key

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080

# NextAuth Configuration
NEXTAUTH_SECRET=your-nextauth-secret
NEXTAUTH_URL=http://localhost:3000

# Frontend Configuration
NEXT_PUBLIC_AUTH0_DOMAIN=your-auth0-domain
NEXT_PUBLIC_AUTH0_CLIENT_ID=your-auth0-client-id
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080
NEXT_PUBLIC_APP_URL=http://localhost:3000

# Google OAuth (optional)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

## Management Commands

### Start Services
```bash
# Start all services
docker-compose up -d

# Start with logs
docker-compose up
```

### Stop Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes all data)
docker-compose down -v
```

### View Logs
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs backend
docker-compose logs frontend

# Follow logs
docker-compose logs -f backend
```

### Rebuild Services
```bash
# Rebuild all services
docker-compose build

# Rebuild specific service
docker-compose build backend
```

### Database Operations

The database is automatically managed, but you can access it directly:

```bash
# Connect to PostgreSQL
docker exec -it rhesis-postgres psql -U rhesis_user -d rhesis

# Check migration status
docker exec rhesis-backend bash -c "cd src/rhesis/backend && alembic current"

# Run migrations manually (if needed)
docker exec rhesis-backend bash -c "cd src/rhesis/backend && alembic upgrade head"
```

## Troubleshooting

### Database Migration Issues

If you encounter database issues:

1. **Check migration status**:
   ```bash
   docker exec rhesis-backend bash -c "cd src/rhesis/backend && alembic current"
   ```

2. **View migration logs**:
   ```bash
   docker-compose logs backend | grep -i migration
   ```

3. **Reset database** (⚠️ deletes all data):
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

### Service Health Checks

Check if all services are healthy:
```bash
docker-compose ps
```

### Environment Variables

Verify environment variables are loaded:
```bash
docker exec rhesis-backend env | grep AUTH0
```

## Development

### Adding New Migrations

1. Create a new migration:
   ```bash
   docker exec rhesis-backend bash -c "cd src/rhesis/backend && alembic revision --autogenerate -m 'description'"
   ```

2. The migration will run automatically on next startup, or run manually:
   ```bash
   docker exec rhesis-backend bash -c "cd src/rhesis/backend && alembic upgrade head"
   ```

### Hot Reload (Development)

For development with hot reload:

```bash
# Override the backend command for development
docker-compose run --service-ports backend uvicorn rhesis.backend.app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Production Considerations

- Use proper secrets management
- Set up proper logging
- Configure SSL/TLS
- Set up monitoring and alerting
- Use external database and Redis instances
- Configure proper backup strategies

## Support

If you encounter issues:

1. Check the logs: `docker-compose logs`
2. Verify environment variables are set correctly
3. Ensure Docker has sufficient resources
4. Check if ports are available and not in use 