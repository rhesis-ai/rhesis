# Environment Configuration

## Overview

The Rhesis backend uses environment variables for configuration, allowing for different settings across development, testing, and production environments. This approach follows the [12-factor app](https://12factor.net/) methodology for configuration management.

## Environment Files

The application supports multiple environment files:

- `.env`: Default environment file for local development
- `.env.docker`: Environment configuration for Docker deployment
- `.env.test`: Environment configuration for testing (not committed to version control)

## Loading Environment Variables

Environment variables are loaded using the `python-dotenv` library:

```python
from dotenv import load_dotenv

load_dotenv()  # Loads variables from .env file
```

## Core Configuration Categories

### Database Configuration

```
# PostgreSQL Configuration
SQLALCHEMY_DB_DRIVER=postgresql
SQLALCHEMY_DB_USER=username
SQLALCHEMY_DB_PASS=password
SQLALCHEMY_DB_HOST=localhost
SQLALCHEMY_DB_NAME=rhesis
SQLALCHEMY_DATABASE_URL=postgresql://username:password@localhost:5432/rhesis
SQLALCHEMY_DATABASE_TEST_URL=postgresql://username:password@localhost:5432/rhesis-test
```

### Authentication Configuration

```
# Auth0 Configuration
AUTH0_DOMAIN=dev-rhesis.eu.auth0.com
AUTH0_AUDIENCE=audience-id
AUTH0_CLIENT_ID=client-id
AUTH0_CLIENT_SECRET=client-secret
AUTH0_SECRET_KEY=secret-key

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

### Application Configuration

```
# App & Logging Configuration
LOG_LEVEL=DEBUG
RHESIS_BASE_PATH=/path/to/rhesis/
FRONTEND_URL=http://localhost:3000
```

### AI Model Configuration

```
# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL_NAME=gpt-4o

# Hugging Face Configuration
HF_API_TOKEN=your-huggingface-token
```

### Background Task Configuration

```
# Celery Configuration
BROKER_URL=sqla+postgresql://celery-user:password@localhost:5432/celery
CELERY_RESULT_BACKEND=db+postgresql://celery-user:password@localhost:5432/celery
```

## Environment Variable Usage

Environment variables are accessed throughout the codebase using `os.getenv()`:

```python
import os

database_url = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite:///./test.db")
```

The second parameter provides a default value if the environment variable is not set.

## Sensitive Information

Sensitive information such as API keys and passwords should never be committed to version control. Instead:

1. Use placeholder values in `.env.example`
2. Document the required variables
3. Use secrets management in production environments

## Environment-Specific Configuration

The application can load different configuration based on the environment:

```python
import os

# Determine environment
ENV = os.getenv("ENV", "development")

# Load environment-specific settings
if ENV == "production":
    # Production settings
    DEBUG = False
    LOG_LEVEL = "INFO"
elif ENV == "testing":
    # Testing settings
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    # Use in-memory database
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
else:
    # Development settings
    DEBUG = True
    LOG_LEVEL = "DEBUG"
```

## Configuration Validation

The application validates critical configuration at startup:

```python
def validate_config():
    """Validate that all required configuration is present."""
    required_vars = [
        "SQLALCHEMY_DATABASE_URL",
        "JWT_SECRET_KEY",
        "AUTH0_DOMAIN",
        "AUTH0_CLIENT_ID",
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
```

## Docker Environment

When running in Docker, environment variables can be passed in several ways:

1. Through the `environment` section in `docker-compose.yml`
2. Using the `--env-file` flag with `docker run`
3. Setting individual variables with `-e` flags

Example Docker Compose configuration:

```yaml
services:
  backend:
    build: ./apps/backend
    env_file:
      - ./apps/backend/.env.docker
    environment:
      - SQLALCHEMY_DB_HOST=postgres
      - LOG_LEVEL=INFO
```

## Cloud Deployment

For cloud deployments, environment variables should be set using the cloud provider's secrets or environment configuration:

- Google Cloud: Secret Manager and environment variables in Cloud Run
- AWS: Parameter Store/Secrets Manager and environment variables in ECS/Lambda
- Azure: Key Vault and App Configuration 