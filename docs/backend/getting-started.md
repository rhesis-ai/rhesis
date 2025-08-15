# Getting Started with Rhesis Backend

This guide will help you set up and run the Rhesis backend on your local machine for development purposes.

## Prerequisites

Before you begin, make sure you have the following installed:

- Python 3.10 or higher
- PostgreSQL 13 or higher
- [UV](https://github.com/astral-sh/uv) package installer
- Git

## Clone the Repository

```bash
git clone <repository_url>
cd rhesis
```

## Environment Setup

1. Navigate to the backend directory:

```bash
cd apps/backend
```

2. Create a Python virtual environment:

```bash
python -m venv .venv
```

3. Activate the virtual environment:

On Linux/macOS:
```bash
source .venv/bin/activate
```

On Windows:
```bash
.venv\Scripts\activate
```

4. Install dependencies using UV:

```bash
uv pip install -e .
```

## Database Setup

1. Create a PostgreSQL database:

```bash
createdb rhesis
```

2. Create a `.env` file based on the provided template:

```bash
cp .env.example .env
```

3. Update the database connection string in `.env`:

```
SQLALCHEMY_DATABASE_URL=postgresql://username:password@localhost:5432/rhesis
```

4. Run database migrations:

```bash
alembic upgrade head
```

## Running the Application

1. Start the FastAPI server:

```bash
uvicorn rhesis.backend.app.main:app --reload
```

The API will be available at http://localhost:8000

2. Open the API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Running Background Tasks

1. Start a Celery worker:

```bash
celery -A rhesis.backend.worker worker --loglevel=info
```

## Development Workflow

### Code Formatting

Format code using ruff:

```bash
uv run --all-groups ruff format .
```

### Linting

Run the linter:

```bash
uv run --all-groups ruff check .
```

Fix linting issues automatically:

```bash
uv run --all-groups ruff check --fix .
```

### Running Tests

Run the test suite:

```bash
pytest
```

## Authentication Setup

For local development, you can use Auth0 or set up a mock authentication system.

### Auth0 Configuration

1. Create an Auth0 application at https://auth0.com/
2. Update the Auth0 configuration in your `.env` file:

```
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_AUDIENCE=your-audience
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
AUTH0_SECRET_KEY=your-secret-key
```

## API Endpoints

Once the application is running, you can explore the available endpoints through the Swagger UI at http://localhost:8000/docs.

## Next Steps

Now that you have the backend running, you can:

1. Create your first organization and user
2. Explore the API endpoints
3. Set up the frontend application to interact with the backend
4. Start developing new features

For more detailed information about the backend architecture and components, refer to the other documentation files in this directory. 