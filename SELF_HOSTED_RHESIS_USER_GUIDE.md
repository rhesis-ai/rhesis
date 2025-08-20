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

2. **Copy environment variables in the project root directory**
   ```bash
   cp env.docker .env
   ```

3. **Edit the `.env` file** 
   - Update the Auth0 configuration
   - Update the JWT configuration
   - Update Azure OpenAI configuration
   - Update Gemini configuration
   - Update SMTP base configuration
   - Update Next Auth Js configuration 
   - Update any other environment variables as needed

4. **Start all services**
   ```bash
   docker-compose up -d
   ```

5. **Access the applications**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8080/docs

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
| **Worker** | 8081 | Celery Background Tasks | `curl /health/basic` |
| **Frontend** | 3000 | Next.js Application | `curl /api/auth/session` |

### Service Dependencies

```
Frontend → Backend → PostgreSQL
             ↓
           Redis → Worker 
```

## Environment Variables

### Required Variables

update the `.env` file of the root directory with:

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

# Google OAuth 
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# SMTP 
SMTP_HOST=your_smtp_host
SMTP_PORT=465
SMTP_USER=your_smtp_user
SMTP_PASSWORD=your_smtp_password
FROM_EMAIL=your_from_email

# Add your Gemini API key here
GEMINI_API_KEY=your-gemini-api-key
GOOGLE_API_KEY=your-google-api-key
GEMINI_MODEL_NAME=gemini-2.0-flash-001

# AI model Configuration

#AZURE
AZURE_OPENAI_ENDPOINT=YOUR_AZURE_OPENAI_API_ENDPOINT
AZURE_OPENAI_API_KEY=YOUR_AZURE_OPENAI_API_KEY
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=YOUR_AZURE_OPENAI_API_VERSION

# OpenAI
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL_NAME=gpt-4o

# Hugging Face
HF_API_TOKEN=YOUR_HUGGING_FACE_API_TOKEN

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
docker exec -it rhesis-postgres psql -U rhesis-user -d rhesis-db

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


## Support

If you encounter issues:

1. Check the logs: `docker-compose logs`
2. Verify environment variables are set correctly
3. Ensure Docker has sufficient resources
4. Check if ports are available and not in use 