# Environment Setup Guide

This guide explains how to configure the environment variables for both the backend and frontend applications.

## Backend Environment Variables

Create a `.env` file in `apps/backend/` with the following variables:

### Database Configuration
```bash
# PostgreSQL database connection
SQLALCHEMY_DATABASE_URL=postgresql://username:password@host:port/database
SQLALCHEMY_DB_MODE=develop
SQLALCHEMY_DB_DRIVER=postgresql
SQLALCHEMY_DB_USER=your_db_user
SQLALCHEMY_DB_PASS=your_db_password
SQLALCHEMY_DB_HOST=your_database_host
SQLALCHEMY_DB_NAME=your_database_name
```

### Logging
```bash
# Application logging level
LOG_LEVEL=DEBUG
```

### Authentication (Auth0)
```bash
# Auth0 configuration
AUTH0_DOMAIN=your-tenant.region.auth0.com
AUTH0_AUDIENCE=your_auth0_audience
AUTH0_CLIENT_ID=your_auth0_client_id
AUTH0_CLIENT_SECRET=your_auth0_client_secret
AUTH0_SECRET_KEY=your_auth0_secret
```

### JWT Configuration
```bash
# JWT token settings
JWT_SECRET_KEY=your_very_long_random_secret_key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

### Application URLs
```bash
# Frontend application URL
FRONTEND_URL=http://localhost:3000
RHESIS_BASE_URL=http://localhost:8080
```

### AI Services
```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_openai_key
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_API_VERSION=2024-10-21

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL_NAME=gemini-2.0-flash-001
```

### Email Configuration
```bash
# SMTP settings (e.g., SendGrid)
SMTP_HOST=your_smtp_host
SMTP_PORT=587
SMTP_USER=your_smtp_user
SMTP_PASSWORD=your_smtp_password
```

### Celery Configuration
```bash
# Task queue configuration
BROKER_URL=your_celery_broker_url
CELERY_RESULT_BACKEND=your_celery_result_backend
CELERY_WORKER_CONCURRENCY=8
CELERY_WORKER_PREFETCH_MULTIPLIER=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
```

## Frontend Environment Variables

Create a `.env.local` file in `apps/frontend/` with the following variables:

### NextAuth Configuration
```bash
# NextAuth.js settings
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your_nextauth_secret
AUTH_SECRET=your_auth_secret
```

### Public Variables (Exposed to Browser)
```bash
# API and application URLs
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080
NEXT_PUBLIC_APP_URL=http://localhost:3000

# Auth0 public configuration
NEXT_PUBLIC_AUTH0_CLIENT_ID=your_auth0_frontend_client_id
NEXT_PUBLIC_AUTH0_DOMAIN=your-domain.auth0.com
```

### OAuth Configuration
```bash
# Google OAuth credentials
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

### Database (if needed)
```bash
# Database connection for frontend operations
DATABASE_URL=postgresql://username:password@host:port/database
```

### Email Configuration (if needed)
```bash
# SMTP settings
SMTP_HOST=your_smtp_host
SMTP_PORT=587
SMTP_USER=your_smtp_user
SMTP_PASSWORD=your_smtp_password
```

## Setup Instructions

### 1. Database Setup
- Set up PostgreSQL database
- Create separate databases for main app and Celery if needed
- Configure connection details in environment variables

### 2. Auth0 Setup
- Create Auth0 application
- Configure callback URLs and settings
- Get client credentials and domain

### 3. Google OAuth Setup
- Create project in Google Cloud Console
- Enable Google+ API
- Create OAuth 2.0 credentials
- Configure authorized redirect URIs

### 4. AI Services Setup
- **Azure OpenAI**: Create resource in Azure, deploy models, get API keys
- **Google Gemini**: Get API key from Google AI Studio

### 5. Email Setup
- Configure SMTP service (e.g., SendGrid)
- Get API keys and SMTP credentials

### 6. Generate Secrets
```bash
# Generate NextAuth secret
openssl rand -base64 32

# Generate JWT secret
openssl rand -hex 64
```

## Security Notes

- Never commit actual environment files (`.env`, `.env.local`) to version control
- Use different secrets for different environments
- Rotate secrets regularly
- Use environment-specific configurations for production

## Development vs Production

Make sure to use appropriate values for each environment:
- **Development**: `localhost` URLs, development databases
- **Production**: Production URLs, production databases, stronger secrets 