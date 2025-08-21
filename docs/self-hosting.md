# Self-Hosting Rhesis with Docker

This guide will help you run the entire Rhesis project using Docker Compose for self-hosted deployments.

## Prerequisites

- Docker Desktop installed and running
- Git (to clone the repository)
- At least 4GB of available RAM
- Ports 3000, 8080, 8081, 5432, and 6379 available on your system

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd rhesis
   ```

2. **Copy environment variables**
   ```bash
   cp env.docker .env
   ```

3. **Configure environment variables**
   
   Edit the `.env` file and update the following configurations:
   - Auth0 configuration
   - JWT configuration
   - Azure OpenAI configuration
   - Gemini configuration
   - SMTP configuration
   - NextAuth.js configuration
   - Any other environment variables as needed

4. **Start all services**
   ```bash
   docker-compose up -d
   ```

5. **Access the applications**
   - **Frontend**: http://localhost:3000
   - **Backend API**: http://localhost:8080/docs
   - **Worker Health**: http://localhost:8081/health/basic

## Architecture Overview

### Services

The Rhesis platform consists of several interconnected services:

| Service | Port | Description | Health Check |
|---------|------|-------------|--------------|
| **PostgreSQL** | 5432 | Primary database | `pg_isready` |
| **Redis** | 6379 | Cache & message broker | `redis-cli ping` |
| **Backend** | 8080 | FastAPI application | `curl /health` |
| **Worker** | 8081 | Celery background tasks | `curl /health/basic` |
| **Frontend** | 3000 | Next.js application | `curl /api/auth/session` |

### Service Dependencies

```
Frontend → Backend → PostgreSQL
             ↓
           Redis → Worker 
```

## Automated Database Setup

**No manual database setup required!** The system automatically handles:

- ✅ PostgreSQL database and user creation
- ✅ Database ownership and permissions setup
- ✅ Automatic Alembic migration execution
- ✅ Table and relationship creation
- ✅ Migration status checking (prevents duplicate migrations)

The backend container startup process:
1. Waits for PostgreSQL to be ready
2. Sets proper database ownership
3. Runs all pending migrations
4. Starts the FastAPI application

## Environment Configuration

### Required Environment Variables

Update your `.env` file with the following configurations:

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

# SMTP Configuration
SMTP_HOST=your_smtp_host
SMTP_PORT=465
SMTP_USER=your_smtp_user
SMTP_PASSWORD=your_smtp_password
FROM_EMAIL=your_from_email

# Gemini AI Configuration
GEMINI_API_KEY=your-gemini-api-key
GOOGLE_API_KEY=your-google-api-key
GEMINI_MODEL_NAME=gemini-2.0-flash-001

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=YOUR_AZURE_OPENAI_API_ENDPOINT
AZURE_OPENAI_API_KEY=YOUR_AZURE_OPENAI_API_KEY
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=YOUR_AZURE_OPENAI_API_VERSION

# OpenAI Configuration
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL_NAME=gpt-4o

# Hugging Face Configuration
HF_API_TOKEN=YOUR_HUGGING_FACE_API_TOKEN
```

## Management Commands

### Service Management

**Start services:**
```bash
# Start all services in detached mode
docker-compose up -d

# Start with logs visible
docker-compose up
```

**Stop services:**
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes all data)
docker-compose down -v
```

**Restart services:**
```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend
```

### Monitoring and Logs

**View logs:**
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs backend
docker-compose logs frontend
docker-compose logs worker

# Follow logs in real-time
docker-compose logs -f backend
```

**Check service status:**
```bash
# View running containers and their status
docker-compose ps
```

### Building and Updates

**Rebuild services:**
```bash
# Rebuild all services
docker-compose build

# Rebuild specific service
docker-compose build backend

# Rebuild and restart
docker-compose up -d --build
```

### Database Operations

The database is automatically managed, but you can access it directly if needed:

```bash
# Connect to PostgreSQL
docker exec -it rhesis-postgres psql -U rhesis-user -d rhesis-db

# Check current migration status
docker exec rhesis-backend bash -c "cd src/rhesis/backend && alembic current"

# Run migrations manually (if needed)
docker exec rhesis-backend bash -c "cd src/rhesis/backend && alembic upgrade head"

# View migration history
docker exec rhesis-backend bash -c "cd src/rhesis/backend && alembic history"
```

## Troubleshooting

### Common Issues

**Database Migration Problems:**

1. Check migration status:
   ```bash
   docker exec rhesis-backend bash -c "cd src/rhesis/backend && alembic current"
   ```

2. View migration logs:
   ```bash
   docker-compose logs backend | grep -i migration
   ```

3. Reset database (⚠️ deletes all data):
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

**Service Health Issues:**

1. Check service status:
   ```bash
   docker-compose ps
   ```

2. Verify environment variables:
   ```bash
   docker exec rhesis-backend env | grep AUTH0
   ```

3. Check resource usage:
   ```bash
   docker stats
   ```

**Port Conflicts:**

If you encounter port conflicts, you can modify the ports in `docker-compose.yml` or stop conflicting services:

```bash
# Check what's using a port (e.g., port 3000)
lsof -i :3000

# Kill process using the port
kill -9 <PID>
```

### Performance Optimization

**Resource Allocation:**
- Ensure Docker has at least 4GB RAM allocated
- Monitor disk space usage with `docker system df`
- Clean up unused resources with `docker system prune`

**Database Performance:**
- Monitor PostgreSQL logs: `docker-compose logs postgres`
- Check connection counts and slow queries

### Security Considerations

- Change default passwords in production
- Use strong JWT secrets
- Configure proper firewall rules
- Keep environment variables secure
- Regularly update Docker images

## Backup and Recovery

### Database Backup

```bash
# Create database backup
docker exec rhesis-postgres pg_dump -U rhesis-user rhesis-db > backup.sql

# Restore from backup
docker exec -i rhesis-postgres psql -U rhesis-user -d rhesis-db < backup.sql
```

### Full System Backup

```bash
# Stop services
docker-compose down

# Backup volumes
docker run --rm -v rhesis_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .
docker run --rm -v rhesis_redis_data:/data -v $(pwd):/backup alpine tar czf /backup/redis_backup.tar.gz -C /data .

# Restart services
docker-compose up -d
```

## Support and Resources

### Getting Help

If you encounter issues:

1. Check the logs: `docker-compose logs`
2. Verify environment variables are set correctly
3. Ensure Docker has sufficient resources
4. Check if ports are available and not in use
5. Review the [main documentation](README.md) for additional guidance

### Additional Resources

- [Backend Documentation](backend/README.md)
- [Frontend Documentation](frontend/README.md)
- [Worker Documentation](worker/README.md)
- [Environment Setup Guide](environment-setup.md)

---

For development setup and local development without Docker, see the [Environment Setup Guide](environment-setup.md).
