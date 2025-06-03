# Rhesis Backend Documentation

## Introduction

This documentation provides comprehensive information about the Rhesis backend application, which is built with FastAPI and PostgreSQL. It covers architecture, implementation details, and development workflows to help developers understand and contribute to the project.

## Documentation Structure

The documentation is organized into the following sections:

- [Getting Started](./getting-started.md) - Setup instructions for new developers
- [Architecture Overview](./architecture.md) - High-level architecture and design patterns
- [Database Models](./database-models.md) - Database schema and model relationships
- [API Structure](./api-structure.md) - API endpoints and request/response formats
- [Authentication](./authentication.md) - Auth0 integration and security mechanisms
- [Multi-tenancy](./multi-tenancy.md) - Organization isolation and row-level security
- [Background Tasks](./background-tasks.md) - Celery integration for asynchronous processing
- [Environment Configuration](./environment-config.md) - Environment variables and configuration
- [Security Features](./security.md) - Security best practices and implementations
- [Development Workflow](./development-workflow.md) - Guidelines for development
- [Deployment](./deployment.md) - Deployment instructions and considerations

## Key Features

The Rhesis backend provides:

1. **RESTful API** - A comprehensive API for managing AI model testing and evaluation
2. **Multi-tenancy** - Complete data isolation between organizations
3. **Authentication** - Secure authentication via Auth0
4. **Background Processing** - Asynchronous task execution with Celery
5. **Database Integration** - PostgreSQL with SQLAlchemy ORM
6. **Containerization** - Docker-based deployment

## Quick Links

- [API Documentation](http://localhost:8000/docs) (when running locally)
- [Project README](../../apps/backend/README.md)
- [Contributing Guidelines](../../apps/backend/CONTRIBUTING.md)

## Technology Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Auth0
- **Task Queue**: Celery with Redis broker
- **API Documentation**: Swagger UI (via FastAPI)
- **Package Management**: UV (Python package installer)

## Getting Help

If you encounter issues or have questions:

1. Check the relevant documentation section
2. Review the codebase for comments and docstrings
3. Reach out to the development team

## Contributing to Documentation

To improve this documentation:

1. Make your changes to the relevant Markdown files
2. Follow the existing style and formatting
3. Submit a pull request with your changes

## License

This documentation and the Rhesis application are proprietary and confidential. 