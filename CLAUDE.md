# Rhesis Project Rules

## Technology Stack

### Backend
- **Language**: Python 3.10+
- **Package Manager**: uv with pyproject.toml
- **Validation**: Pydantic 2.x
- **Testing**: pytest

### Python SDK
- **Language**: Python 3.10+
- **Package Manager**: uv with pyproject.toml
- **Validation**: Pydantic 2.x
- **Testing**: pytest

---

## Python Code Quality

### Ruff Linting and Formatting

When modifying Python files, always run ruff checks and formatting:

```bash
# Check for linting issues
uvx ruff check <path/to/file.py>

# Auto-format the code
uvx ruff format <path/to/file.py>

# Check again to verify
uvx ruff check <path/to/file.py>
```

Run ruff:
- **Always** after creating or modifying Python files
- **Before** completing a task involving Python code

### Fixing Line Length Issues

If ruff reports line length violations (E501), fix them by:

1. Breaking long strings into multiple lines
2. Breaking long f-strings
3. Breaking long function calls

Maximum line length: 100 characters

---

## Local Development

### UV Package Manager
1. Always use uv to manage Python projects
2. Execute uv command in the root of the projects (SDK, Backend)
3. Use `uv add <package>` to install dependencies
4. Use `uv test` to run tests
5. Use `uv run <script>` to run scripts

### Backend Debugging
When debugging, add the following at the end of `apps/backend/src/rhesis/backend/app/main.py`:
```python
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rhesis.backend.app.main:app", host="0.0.0.0", port=8080, reload=True, log_level="debug")
```

### GitHub CLI
Use GitHub CLI whenever possible. If a GitHub link is pasted, use GitHub CLI to open it.

---

## Testing

### SDK Tests

1. Tests are stored in `<project_root>/tests/sdk` directory
2. Run unit tests:
```bash
cd sdk
make test
```

3. Run integration tests (starts backend):
```bash
cd sdk
make test-integration
```

4. Check backend logs:
```bash
docker compose -f tests/docker-compose.test.yml --profile sdk logs sdk-test-backend
```

5. Run single tests:
```bash
cd sdk
uv run pytest ../tests/sdk/integration/test_entities.py::test_endpoint
```

---

## Git Commits

### Pre-Commit Workflow

1. Check current status:
```bash
git status
git diff
```

2. Review and analyze changes - group by:
   - Feature additions
   - Bug fixes
   - Refactoring
   - Documentation updates
   - Configuration changes
   - Test modifications

3. Stage changes strategically (avoid `git add .`):
```bash
git add <file1> <file2>
git add -p <filename>  # Stage parts of files
```

### Conventional Commits

Format:
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types:
- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Formatting changes (no code meaning change)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Performance improvement
- **test**: Adding or correcting tests
- **build**: Build system or dependency changes
- **ci**: CI configuration changes
- **chore**: Other changes that don't modify src or test files
- **revert**: Reverts a previous commit

Rules:
1. Use lowercase for type and description
2. No period at the end of the description
3. Use imperative mood ("add" not "adds" or "added")
4. Limit description to 50 characters or less
5. Use scope to specify component (e.g., `feat(auth): add login validation`)
6. Use `BREAKING CHANGE:` in footer for breaking changes

Examples:
- `feat: add user authentication`
- `fix(api): resolve timeout issue in user endpoint`
- `docs: update installation guide`
- `feat!: remove deprecated API endpoints` (! indicates breaking change)

---

## Pull Requests

### Core Principles

1. **Write Small PRs**: Easier to review, less bugs, clearer history
2. **One Logical Change Per PR**: Avoid mixing unrelated changes

### Branch Creation
```bash
git fetch origin
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

### PR Title Guidelines
- Use clear, descriptive titles
- Start with action verb (Add, Fix, Update, Remove)
- Keep under 72 characters

### PR Description Template
```markdown
## Purpose
[Explain why this change is needed]

## What Changed
- [Key change 1]
- [Key change 2]

## Additional Context
- [Links to issues, tickets]
- [Breaking changes or migration notes]

## Testing
[How to test these changes]
```

### Size Guidelines
- **Ideal**: 1-200 lines
- **Acceptable**: 200-400 lines
- **Large**: 400+ lines (break down if possible)

---

## GitHub Issues

When creating issues:
1. Use appropriate template (Bug, Feature, or Task) from `.github/ISSUE_TEMPLATE`
2. Use GitHub CLI: `gh issue create`
3. List existing labels: `gh label list` and select appropriate ones (don't add issue type labels)
4. Keep issues short and to the point
5. Ask user for confirmation before creating

---

## Documentation (docs/ directory)

### Framework
Nextra for documentation (MDX files).

### Critical Rules

**Escape Curly Braces**: MDX interprets `{...}` as JSX expressions.
```mdx
✅ GOOD: API PUT /test_results/\{id\}
❌ BAD:  API PUT /test_results/{id}
```

**When NOT to escape**:
- Inside code blocks (fenced with ```)
- Inside inline code with backticks

### Style Guidelines
- Remove decorative emojis (use "Note:", "Warning:", "Tip:" instead)
- Follow existing documentation style
- Include code examples with language tags
- Test that documentation builds without errors

### Material-UI Icons in MDX
Never import `@mui/icons-material/*` directly in `.mdx` files. Create a JSX component in `/docs/src/components/` and register it in `/docs/src/mdx-components.js`.

---

## Codebase Structure

### Backend (`apps/backend/`)
FastAPI-based REST API with Celery task processing.

Key directories:
- `src/rhesis/backend/app/` - FastAPI application core
  - `models/` - SQLAlchemy ORM models
  - `schemas/` - Pydantic request/response schemas
  - `routers/` - FastAPI route handlers
  - `services/` - Business logic layer
  - `auth/` - Authentication & authorization
- `alembic/` - Database migrations
- `tasks/` - Celery background tasks
- `metrics/` - Evaluation metrics

Key patterns:
- Layered Architecture: routers → services → models/crud
- Multi-tenancy: Organization-based data isolation
- Background Processing: Celery tasks for test execution

### SDK (`sdk/`)
Python SDK for interacting with Rhesis platform.

Key directories:
- `src/rhesis/sdk/`
  - `client.py` - Main RhesisClient
  - `entities/` - API entity wrappers
  - `decorators/` - `@endpoint` and `@observe` decorators
  - `connector/` - Bidirectional connector for test execution
  - `metrics/` - Evaluation metrics
  - `models/` - LLM model providers
  - `synthesizers/` - Test data generation
  - `telemetry/` - OpenTelemetry integration

Key patterns:
- Entity Pattern: Pythonic wrappers for API resources
- Provider Pattern: Pluggable LLM and metric providers
- Decorator Pattern: `@endpoint` and `@observe` for instrumentation

### Frontend (`apps/frontend/`)
Next.js 14+ with App Router and Material UI.

Key directories:
- `src/app/` - Next.js App Router pages
  - `(protected)/` - Authenticated routes
- `src/components/` - Shared components
  - `common/` - Reusable UI components
- `src/utils/api-client/` - Backend API clients
- `src/hooks/` - Custom React hooks

Key patterns:
- App Router: File-based routing with layouts
- Route Groups: `(protected)` for authenticated routes
- Dynamic Routes: `[identifier]` for entity pages
