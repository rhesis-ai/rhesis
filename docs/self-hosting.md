# 🐳 Self-Hosting Rhesis with Docker

This guide will help you run the entire Rhesis platform using Docker Compose for self-hosted deployments.

> 💡 **Important**: This guide uses Docker Compose V2 syntax (`docker compose` without hyphen). If you're using an older version of Docker, you may need to install Docker Compose V2 or use the legacy `docker compose` command.

## 📋 Prerequisites

- 🐳 Docker Desktop installed and running
- 📁 Git (to clone the repository)
- 🔌 Ports 3000, 8080, 8081, 5432, and 6379 available on your system

## 💻 System Requirements

### 🧪 Development Environment
For local development, testing, and evaluation:

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **💾 RAM** | 4 GB | 6 GB |
| **💿 Storage** | 8 GB free | 15 GB free |
| **🖥️ CPU** | 2 cores | 4 cores |
| **🌐 Network** | Stable internet | Broadband |

**Development Notes:**
- Includes hot-reload and development tools
- Lower concurrent user load
- Smaller dataset for testing
- Debug logging enabled

### 🚀 Production Environment
For production deployment with real users:

| Resource | Minimum | Recommended | High-Scale |
|----------|---------|-------------|------------|
| **💾 RAM** | 8 GB | 16 GB | 32 GB+ |
| **💿 Storage** | 20 GB SSD | 50 GB SSD | 100 GB+ SSD |
| **🖥️ CPU** | 4 cores | 8 cores | 16+ cores |
| **🌐 Network** | 50 Mbps | 100 Mbps | 1 Gbps+ |

**Production Notes:**
- Optimized builds without development overhead
- Higher concurrent user capacity
- Production logging levels
- Database connection pooling

### Detailed Resource Breakdown

**Memory Usage by Environment:**

| Service | Development | Production |
|---------|-------------|------------|
| 🐘 **PostgreSQL** | ~256 MB | ~1-2 GB |
| 🔴 **Redis** | ~50 MB | ~500 MB - 1 GB |
| ⚡ **Backend** | ~150 MB | ~500 MB - 1 GB |
| ⚙️ **Worker** | ~200 MB | ~1-2 GB |
| 🌐 **Frontend** | ~100 MB | ~200-400 MB |
| 🐳 **Docker Overhead** | ~300 MB | ~500 MB - 1 GB |
| **Total Estimated** | **~1.1 GB** | **~3.7-7.1 GB** |

**Storage Requirements:**

| Component | Development | Production |
|-----------|-------------|------------|
| 📁 **Application Code** | ~2 GB | ~2 GB |
| 🗄️ **Database** | ~500 MB | ~5-50 GB+ |
| 🐳 **Docker Images** | ~3 GB | ~3-4 GB |
| 📊 **Logs & Cache** | ~500 MB | ~2-10 GB |
| 💾 **Working Space** | ~1 GB | ~3-5 GB |
| **Total Estimated** | **~7 GB** | **~15-75 GB+** |

### Performance Characteristics

**CPU Usage Patterns:**
- 🔥 **High Load**: AI processing, bulk data operations, migrations
- 📊 **Normal Load**: API requests, background tasks, web serving
- 💤 **Idle**: Minimal CPU during low activity periods

**Scaling Factors:**
- 🤖 **AI Operations**: Memory spikes during model inference
- 👥 **Concurrent Users**: ~50-100 MB RAM per active user
- 📈 **Database Growth**: Storage scales with user data and analytics
- 🔄 **Background Tasks**: CPU-intensive during batch processing

### 🔄 Docker Compose Version Note

**Why `docker compose` instead of `docker-compose`?**

- **`docker-compose` (V1)**: The original standalone tool written in Python, **deprecated as of June 2023**
- **`docker compose` (V2)**: The modern version integrated into Docker CLI, written in Go with better performance

If you encounter errors with `docker-compose`, you're likely using the deprecated V1. Switch to `docker compose` (V2) for:
- ✅ Better performance and reliability
- ✅ Active maintenance and security updates  
- ✅ Support for newer Docker features
- ✅ Improved integration with Docker CLI

## 🚀 Quick Start

1. **📥 Clone the repository**
   ```bash
   git clone <repository-url>
   cd rhesis
   ```

2. **📄 Copy environment variables**
   ```bash
   cp env.example .env
   ```

3. **⚙️ Configure environment variables**
   
   Edit the `.env` file and update the following configurations:
   - Auth0 configuration
   - JWT configuration
   - Azure OpenAI configuration
   - Gemini configuration
   - SMTP configuration
   - NextAuth.js configuration
   - Any other environment variables as needed

4. **🚀 Start all services**
   ```bash
   docker compose up -d
   ```

5. **🌐 Access the applications**
   - 🌐 **Frontend**: http://localhost:3000
   - 📡 **Backend API**: http://localhost:8080/docs
   - ⚙️ **Worker Health**: http://localhost:8081/health/basic

## 🏗️ Architecture Overview

### 🔧 Services

The Rhesis platform consists of several interconnected services:

| Service | Port | Description | Health Check |
|---------|------|-------------|--------------|
| **PostgreSQL** | 5432 | Primary database | `pg_isready` |
| **Redis** | 6379 | Cache & message broker | `redis-cli ping` |
| **Backend** | 8080 | FastAPI application | `curl /health` |
| **Worker** | 8081 | Celery background tasks | `curl /health/basic` |
| **Frontend** | 3000 | Next.js application | `curl /api/auth/session` |

### 🔗 Service Dependencies

```
Frontend → Backend → PostgreSQL
             ↓
           Redis ← Worker 
```

## 🗄️ Automated Database Setup

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

## 🔐 Environment Configuration

### Required Environment Variables

Update your `.env` file with the following configurations:

#### 🔒 Authentication & Security
These variables configure user authentication and security for the platform:

```bash
# Auth0 Configuration
# Used for user authentication and authorization
AUTH0_DOMAIN=your-auth0-domain
AUTH0_AUDIENCE=your-auth0-audience
AUTH0_CLIENT_ID=your-auth0-client-id
AUTH0_CLIENT_SECRET=your-auth0-client-secret
AUTH0_SECRET_KEY=your-auth0-secret-key

# JWT Configuration
# Used for secure token generation and validation
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080

# NextAuth Configuration
# Required for Next.js authentication integration
NEXTAUTH_SECRET=your-nextauth-secret
NEXTAUTH_URL=http://localhost:3000

# Frontend Configuration
# Public variables accessible in the browser for Auth0 integration
NEXT_PUBLIC_AUTH0_DOMAIN=your-auth0-domain
NEXT_PUBLIC_AUTH0_CLIENT_ID=your-auth0-client-id
```

#### 🔑 OAuth Providers (Optional)
Additional authentication providers for user login options:

```bash
# Google OAuth (Optional)
# Enables Google sign-in for users
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

#### 📧 Email Configuration (Optional)
Required for sending system emails, notifications, and user communications:

```bash
# SMTP Configuration (Optional)
# Used for sending emails (notifications, invitations, etc.)
SMTP_HOST=your_smtp_host
SMTP_PORT=465
SMTP_USER=your_smtp_user
SMTP_PASSWORD=your_smtp_password
FROM_EMAIL=your_from_email
```

#### 🤖 AI Model Configuration (Optional)
Configure AI providers for natural language processing and content generation:

```bash
# Gemini AI Configuration (Optional)
# Google's Gemini AI for advanced language processing
GEMINI_API_KEY=your-gemini-api-key
GOOGLE_API_KEY=your-google-api-key
GEMINI_MODEL_NAME=gemini-2.0-flash-001

# Azure OpenAI Configuration (Optional)
# Microsoft Azure's OpenAI service for GPT models
AZURE_OPENAI_ENDPOINT=YOUR_AZURE_OPENAI_API_ENDPOINT
AZURE_OPENAI_API_KEY=YOUR_AZURE_OPENAI_API_KEY
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=YOUR_AZURE_OPENAI_API_VERSION

# OpenAI Configuration (Optional)
# Direct OpenAI API integration for GPT models
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL_NAME=gpt-4o
```

> 💡 **Note**: At least one AI provider configuration is recommended for full platform functionality. You can choose between Gemini, Azure OpenAI, or OpenAI based on your preferences and requirements.

## 🛠️ Management Commands

### 🎛️ Service Management

**▶️ Start services:**
```bash
# Start all services in detached mode
docker compose up -d

# Start with logs visible
docker compose up
```

**⏹️ Stop services:**
```bash
# Stop all services
docker compose down

# Stop and remove volumes (⚠️ deletes all data)
docker compose down -v
```

**🔄 Restart services:**
```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart backend
```

### 📊 Monitoring and Logs

**📋 View logs:**
```bash
# All services
docker compose logs

# Specific service
docker compose logs backend
docker compose logs frontend
docker compose logs worker

# Follow logs in real-time
docker compose logs -f backend
```

**✅ Check service status:**
```bash
# View running containers and their status
docker compose ps
```

### 🔨 Building and Updates

**🏗️ Rebuild services:**
```bash
# Rebuild all services
docker compose build

# Rebuild specific service
docker compose build backend

# Rebuild and restart
docker compose up -d --build
```

### 💾 Database Operations

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

## 🔧 Troubleshooting

### ⚠️ Common Issues

**🗄️ Database Migration Problems:**

1. Check migration status:
   ```bash
   docker exec rhesis-backend bash -c "cd src/rhesis/backend && alembic current"
   ```

2. View migration logs:
   ```bash
   docker compose logs backend | grep -i migration
   ```

3. Reset database (⚠️ deletes all data):
   ```bash
   docker compose down -v
   docker compose up -d
   ```

**🏥 Service Health Issues:**

1. Check service status:
   ```bash
   docker compose ps
   ```

2. Verify environment variables:
   ```bash
   docker exec rhesis-backend env | grep AUTH0
   ```

3. Check resource usage:
   ```bash
   docker stats
   ```

**🔌 Port Conflicts:**

If you encounter port conflicts, you can modify the ports in `docker compose.yml` or stop conflicting services:

```bash
# Check what's using a port (e.g., port 3000)
lsof -i :3000

# Kill process using the port
kill -9 <PID>
```

### ⚡ Performance Optimization

**💻 Resource Allocation:**
- Ensure Docker has at least 4GB RAM allocated
- Monitor disk space usage with `docker system df`
- Clean up unused resources with `docker system prune`

**🗄️ Database Performance:**
- Monitor PostgreSQL logs: `docker compose logs postgres`
- Check connection counts and slow queries

### 🛡️ Security Considerations

- 🔐 Change default passwords in production
- 🔑 Use strong JWT secrets
- 🧱 Configure proper firewall rules
- 🔒 Keep environment variables secure
- 🔄 Regularly update Docker images

## 💾 Backup and Recovery

### 🗄️ Database Backup

```bash
# Create database backup
docker exec rhesis-postgres pg_dump -U rhesis-user rhesis-db > backup.sql

# Restore from backup
docker exec -i rhesis-postgres psql -U rhesis-user -d rhesis-db < backup.sql
```

### 📦 Full System Backup

```bash
# Stop services
docker compose down

# Backup volumes
docker run --rm -v rhesis_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .
docker run --rm -v rhesis_redis_data:/data -v $(pwd):/backup alpine tar czf /backup/redis_backup.tar.gz -C /data .

# Restart services
docker compose up -d
```

## 🆘 Support and Resources

### 💬 Getting Help

If you encounter issues:

1. Check the logs: `docker compose logs`
2. Verify environment variables are set correctly
3. Ensure Docker has sufficient resources
4. Check if ports are available and not in use
5. Review the [main documentation](README.md) for additional guidance

### 📚 Additional Resources

- [Backend Documentation](backend/README.md)
- [Frontend Documentation](frontend/README.md)
- [Worker Documentation](worker/README.md)
- [Environment Setup Guide](environment-setup.md)

---

For development setup and local development without Docker, see the 🔧 [Environment Setup Guide](environment-setup.md).
