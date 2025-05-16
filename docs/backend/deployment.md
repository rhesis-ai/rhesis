# Deployment

## Overview

This document outlines the process for deploying the Rhesis backend to various environments. The application is containerized using Docker, making it deployable to any environment that supports containers.

## Prerequisites

Before deploying, ensure you have:

- Access to the target environment
- Docker installed (for local builds)
- Required environment variables and secrets
- Database migration plan

## Docker Deployment

### Building the Docker Image

The application includes a `Dockerfile` that defines the container build:

```bash
# Build the Docker image
docker build -t rhesis-backend:latest ./apps/backend
```

### Running the Container

Run the container with appropriate environment variables:

```bash
docker run -p 8000:8000 \
  --env-file ./apps/backend/.env.docker \
  rhesis-backend:latest
```

## Environment Configuration

### Production Environment Variables

For production deployments, ensure these environment variables are configured:

```
# Database
SQLALCHEMY_DATABASE_URL=postgresql://user:password@host:port/database

# Authentication
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_AUDIENCE=your-audience
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
AUTH0_SECRET_KEY=your-secret-key

# Application
LOG_LEVEL=INFO
FRONTEND_URL=https://app.rhesis.ai

# Celery
BROKER_URL=sqla+postgresql://celery-user:password@host:port/celery
CELERY_RESULT_BACKEND=db+postgresql://celery-user:password@host:port/celery
```

## Deployment Environments

### Local Development

For local testing of the production build:

```bash
# Run the Docker container locally
docker run -p 8000:8000 --env-file ./apps/backend/.env.docker rhesis-backend:latest
```

### Google Cloud Run

Deploy to Google Cloud Run:

1. Build and push the image to Google Container Registry:

```bash
gcloud builds submit --tag gcr.io/project-id/rhesis-backend ./apps/backend
```

2. Deploy to Cloud Run:

```bash
gcloud run deploy rhesis-backend \
  --image gcr.io/project-id/rhesis-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "SQLALCHEMY_DB_HOST=/cloudsql/project-id:region:instance"
```

3. Set up Cloud SQL connection:

```bash
gcloud run services update rhesis-backend \
  --add-cloudsql-instances project-id:region:instance
```

### AWS Deployment

Deploy to AWS ECS:

1. Push the image to Amazon ECR:

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin account-id.dkr.ecr.us-east-1.amazonaws.com
docker tag rhesis-backend:latest account-id.dkr.ecr.us-east-1.amazonaws.com/rhesis-backend:latest
docker push account-id.dkr.ecr.us-east-1.amazonaws.com/rhesis-backend:latest
```

2. Update the ECS task definition and service

## Database Migrations

Before deploying a new version:

1. Apply database migrations:

```bash
# Inside the container or with access to the database
alembic upgrade head
```

For zero-downtime migrations:

1. Ensure migrations are backward compatible
2. Deploy the new version with migrations
3. Verify the application works correctly
4. If issues occur, be prepared to rollback

## Scaling

### Horizontal Scaling

The application is designed to scale horizontally:

- Stateless API design allows multiple instances
- Database connections use connection pooling
- Background tasks are handled by separate Celery workers

### Celery Workers

Deploy Celery workers separately:

```bash
docker run \
  --env-file ./apps/backend/.env.docker \
  rhesis-backend:latest \
  celery -A rhesis.backend.celery_app worker --loglevel=info
```

## Monitoring and Logging

### Application Logs

The application logs to stdout/stderr, which can be captured by container platforms:

```bash
# View logs in Docker
docker logs container_id
```

### Health Checks

The application provides a health check endpoint at `/health`:

```bash
curl http://localhost:8000/health
```

## Rollback Procedure

If deployment issues occur:

1. Identify the issue through logs and monitoring
2. Rollback to the previous known-good version by redeploying the previous image
3. If database migrations need to be reversed:

```bash
alembic downgrade -1  # Downgrade one version
```

## Security Considerations

- Store secrets securely using environment variables or secret management services
- Use HTTPS for all communications
- Implement network security policies to restrict access
- Regularly update dependencies to address security vulnerabilities 