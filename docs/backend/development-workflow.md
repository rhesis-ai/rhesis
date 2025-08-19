# Development Workflow

## Overview

This document outlines the recommended development workflow for working with the Rhesis backend. Following these practices will help maintain code quality and consistency across the project.

## Local Development Setup

### Initial Setup

1. Clone the repository
2. Set up your Python environment (Python 3.10+)
3. Install dependencies with UV: `uv pip install -e .`
4. Set up your local PostgreSQL database
5. Configure your `.env` file with local settings

### Running the Application

Start the FastAPI development server:

```bash
uvicorn rhesis.backend.app.main:app --reload
```

The `--reload` flag enables auto-reloading when code changes are detected.

## Code Style and Quality

### Formatting

The project uses `ruff` for code formatting. Format your code using:

```bash
uv run --all-groups ruff format .
```

This ensures consistent code style across the project.

### Linting

Run the linter to check for code quality issues:

```bash
uv run --all-groups ruff check .
```

Fix automatically fixable issues:

```bash
uv run --all-groups ruff check --fix .
```

### Type Checking

Although not strictly enforced, adding type hints to your code is encouraged for better IDE support and code quality.

## Database Changes

### Creating Models

When creating new database models:

1. Define your model in `app/models/`
2. Import it in `app/models/__init__.py`
3. Create corresponding Pydantic schemas in `app/schemas/`
4. Add CRUD operations in `app/crud.py`

### Database Migrations

For schema changes:

1. Make changes to your SQLAlchemy models
2. Generate a migration: `alembic revision --autogenerate -m "Description of changes"`
3. Review the generated migration file in `alembic/versions/`
4. Apply the migration: `alembic upgrade head`

## API Development

### Creating New Endpoints

When adding new API endpoints:

1. Create or modify a router file in `app/routers/`
2. Define your endpoint functions with appropriate decorators
3. Import and register your router in `app/routers/__init__.py`
4. Add necessary schemas, models, and CRUD operations

### Testing Endpoints

Test your endpoints using:

1. FastAPI's interactive documentation (Swagger UI) at `/docs`
2. API client tools like Postman or Insomnia
3. Automated tests (see Testing section)

## Background Tasks

### Creating Celery Tasks

When creating new background tasks:

1. Define your task in an appropriate file in `tasks/`
2. Import and register your task in `tasks/__init__.py`
3. Add any necessary database models and schemas

### Testing Tasks

Test your tasks using:

1. Direct invocation in development mode
2. Running a local Celery worker: `celery -A rhesis.backend.worker worker --loglevel=info`

## Testing

### Writing Tests

Tests are located in the `tests/backend/` directory. When writing tests:

1. Create test files that mirror the structure of the code being tested
2. Use pytest fixtures for common setup and teardown
3. Use a test database (configured in `conftest.py`)

### Running Tests

Run the test suite:

```bash
pytest
```

Run specific tests:

```bash
pytest tests/backend/test_specific_module.py
```

## Debugging

### Logging

Use the application's logging system for debugging:

```python
from rhesis.backend.logging import logger

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

### Interactive Debugging

For interactive debugging:

1. Add breakpoints using `breakpoint()` or your IDE's debugging tools
2. Run the application in debug mode through your IDE
3. Use `print()` statements judiciously for quick debugging

## Git Workflow

### Branching Strategy

1. `main`: Production-ready code
2. `develop`: Integration branch for feature development
3. Feature branches: Created from `develop` for new features
4. Hotfix branches: Created from `main` for urgent fixes

### Commit Guidelines

Follow these guidelines for commit messages:

1. Use present tense ("Add feature" not "Added feature")
2. First line is a summary (max 50 characters)
3. Optionally followed by a blank line and detailed description
4. Reference issue numbers where appropriate

Example:
```
Add user authentication endpoint

- Implement JWT token generation
- Add user validation
- Set up Auth0 integration

Fixes #123
```

### Pull Requests

When creating pull requests:

1. Provide a clear description of the changes
2. Reference any related issues
3. Ensure all tests pass
4. Request review from appropriate team members

## Deployment

### Preparing for Deployment

Before deploying:

1. Ensure all tests pass
2. Check for any security vulnerabilities in dependencies
3. Update documentation if necessary
4. Verify environment variables are correctly set

### Deployment Process

The deployment process varies by environment but typically involves:

1. Building a Docker image
2. Running database migrations
3. Deploying the new container
4. Verifying the deployment

## Troubleshooting

### Common Issues

1. **Database connection errors**: Check your database connection string and ensure PostgreSQL is running
2. **Missing environment variables**: Verify your `.env` file contains all required variables
3. **Import errors**: Check your Python path and virtual environment
4. **Authentication issues**: Verify Auth0 configuration and JWT settings

### Getting Help

If you encounter issues:

1. Check the project documentation
2. Review relevant code and comments
3. Ask for help in the project's communication channels
4. Create an issue on the project's issue tracker 