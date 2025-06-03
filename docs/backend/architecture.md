# Backend Architecture

## Overview

The Rhesis backend is built with FastAPI, a modern Python web framework designed for building APIs with automatic OpenAPI documentation. The application follows a modular architecture with clear separation of concerns.

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Auth0
- **Task Queue**: Celery with Redis broker
- **API Documentation**: Swagger UI (via FastAPI)
- **Package Management**: UV (Python package installer)

## Directory Structure

```
apps/backend/
├── src/
│   └── rhesis/
│       ├── scripts.py           # CLI utility scripts
│       └── backend/
│           ├── __init__.py      # Package initialization
│           ├── app/             # Main application code
│           │   ├── main.py      # FastAPI application entry point
│           │   ├── database.py  # Database connection and session management
│           │   ├── crud.py      # CRUD operations
│           │   ├── models/      # SQLAlchemy models
│           │   ├── schemas/     # Pydantic schemas
│           │   ├── routers/     # API endpoints
│           │   ├── auth/        # Authentication logic
│           │   ├── utils/       # Utility functions
│           │   └── services/    # Business logic services
│           ├── alembic/         # Database migrations
│           ├── tasks/           # Celery background tasks
│           ├── metrics/         # Application metrics
│           └── logging/         # Logging configuration
├── pyproject.toml              # Project dependencies and configuration
└── .env                        # Environment variables
```

## Architectural Patterns

### 1. Model-View-Controller (MVC)

The backend follows an MVC-like pattern:
- **Models**: SQLAlchemy models in `app/models/`
- **Views**: FastAPI route handlers in `app/routers/`
- **Controllers**: Business logic in `app/services/` and CRUD operations in `app/crud.py`

### 2. Repository Pattern

The CRUD operations are abstracted into a repository layer, allowing for clean separation between database access and business logic.

### 3. Dependency Injection

FastAPI's dependency injection system is used extensively for:
- Database session management
- Authentication and authorization
- Feature toggles and configuration

## Key Components

### FastAPI Application

The main application is defined in `app/main.py`, which:
- Creates the FastAPI application
- Configures middleware (CORS, authentication)
- Registers all routers
- Sets up exception handlers

### Database Layer

The database layer consists of:
- Connection management in `app/database.py`
- SQLAlchemy models in `app/models/`
- Pydantic schemas for request/response validation in `app/schemas/`

### API Routers

API endpoints are organized into routers by resource type, with each router handling a specific domain entity (tests, prompts, users, etc.).

### Background Tasks

Long-running operations are handled by Celery tasks defined in the `tasks/` directory, which are executed asynchronously.

### Authentication

Authentication is handled through Auth0 integration, with custom middleware to enforce different authentication requirements based on route configuration.

## Communication Flow

1. Client sends request to API endpoint
2. FastAPI routes the request to the appropriate handler
3. Authentication middleware validates the request
4. Dependencies are resolved (database session, current user)
5. Request is validated using Pydantic schemas
6. Business logic is executed (via services or direct CRUD operations)
7. Response is generated and returned to the client

## Multi-tenancy

The application implements multi-tenancy through PostgreSQL row-level security, ensuring data isolation between different organizations.

## Scalability Considerations

- Database connection pooling
- Stateless API design for horizontal scaling
- Background task processing with Celery
- Caching strategies for frequently accessed data 