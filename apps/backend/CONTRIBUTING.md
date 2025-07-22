# Contributing to Rhesis Backend

Thank you for your interest in contributing to the Rhesis backend! This document provides guidelines and instructions for contributing.

## Python Version Requirements

The Rhesis backend requires **Python 3.10** or newer. If you encounter issues with your system's Python version, we recommend using [pyenv](https://github.com/pyenv/pyenv) to manage Python versions:

```bash
# Install pyenv
curl https://pyenv.run | bash

# Install build dependencies (Ubuntu/Debian)
sudo apt update && sudo apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev \
libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev python-openssl

# Install Python 3.10
pyenv install 3.10.17

# Set local Python version
pyenv local 3.10.17

# Create a fresh virtual environment with UV
uv venv

# Activate the virtual environment
source .venv/bin/activate
```

This ensures you're using a clean Python environment without potential conflicts from other packages or Python installations.

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/rhesis-ai/rhesis.git
cd rhesis
```

2. **Install GitHub CLI** (required for automated PR creation):
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install gh

# macOS
brew install gh

# Or download from: https://cli.github.com/
```

3. **Authenticate with GitHub**:
```bash
gh auth login
```

4. **Set up the backend** dependencies:
```bash
cd apps/backend
uv pip install hatch
uv sync --extra dev
uv pip install -e .
```
This will:
- Sync all dependencies, including development dependencies (such as Sphinx for docs)
- Install the backend package in editable mode

## RH CLI Tool

The repository includes a unified CLI tool for managing development servers:

```bash
./rh backend start    # Start the backend server
./rh frontend start   # Start the frontend server
./rh help            # Show available commands
```

Run these commands from the repository root. The CLI provides a consistent interface for starting both services with beautiful, colorful output and proper error handling.

## Automated PR Creation Tool

The repository includes an intelligent PR creation tool that streamlines the pull request process:

```bash
.github/pr [base-branch]
```

**Features:**
- 🎯 **Smart title generation** - Automatically formats branch names into proper titles
- 📝 **Detailed descriptions** - Includes commit summaries, changed files, and checklists
- 🔤 **Proper capitalization** - Handles technical abbreviations (API, UI, DB, etc.)
- ✅ **Ready-to-use templates** - Pre-filled checklists and sections
- 🌐 **Browser integration** - Option to open PR in browser after creation

**Prerequisites:**
- GitHub CLI (`gh`) must be installed and authenticated (see setup steps above)
- Must be run from a feature branch (not main/master)

**Examples:**
```bash
.github/pr          # Create PR against main branch
.github/pr develop  # Create PR against develop branch
```

**Note:** If GitHub CLI is not installed, the tool will display an error and guide you to install it first.

## Development Workflow

1. Create a new branch for your feature:
```bash
git checkout -b feature/your-feature-name
```

2. Enable pre-commit hooks:
```bash
pre-commit install
```

3. **Start the development server** (choose one method):

   **Option A: Use the unified CLI from repository root:**
   ```bash
   ./rh backend start
   ```

   **Option B: Use the backend start script directly:**
   ```bash
   cd apps/backend
   ./start.sh
   ```

   **Option C: Run manually:**
   ```bash
   uvicorn rhesis.backend.app.main:app --host 0.0.0.0 --port 8080 --log-level debug --reload
   ```

4. Make your changes and ensure all checks pass (if a Makefile is present, use it):
```bash
make format      # Format code with Ruff
make lint        # Lint code with Ruff
make type-check  # Type check with mypy
make test        # Run tests
```
Or run all checks at once:
```bash
make all
```

5. Commit your changes:
```bash
git add .
git commit -m "feat: your descriptive commit message"
```

6. Push your changes and create a Pull Request:
```bash
git push origin feature/your-feature-name
```

7. **Create a Pull Request** using the automated PR tool:
```bash
.github/pr
```
This tool will automatically generate a professional PR with proper title formatting, detailed description, commit summaries, and a comprehensive checklist.

## Pull Request Guidelines

- Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification for commit messages
- Include tests for new features
- Update documentation as needed
- Ensure all checks pass before requesting review

## Code Style

We use several tools to maintain code quality:
- [Ruff](https://docs.astral.sh/ruff/) for code formatting and linting
- [MyPy](https://mypy.readthedocs.io/) for static type checking
- [Pre-commit](https://pre-commit.com/) for automated checks

All formatting and linting is handled by Ruff. Use the Makefile targets for a consistent workflow.

## Testing

- Write tests for all new features and bug fixes
- Tests should be placed in the `tests/` directory (or as specified in the project)
- Run the test suite with `make test` from the `apps/backend` directory

## Documentation

- Update documentation for any changed functionality
- Include docstrings for new functions and classes
- Keep the README.md up to date with any user-facing changes

## Cloud Database Setup (Google Cloud SQL)

For developers working with cloud-based databases on Google Cloud, you'll need to set up the Cloud SQL Proxy to securely connect to the database.

### Prerequisites

1. **Google Cloud CLI**: Install the [gcloud CLI tool](https://cloud.google.com/sdk/docs/install)
2. **Project Access**: Ensure you have access to the Google Cloud project and appropriate permissions

### Generating Credentials

1. **Authenticate with Google Cloud**:
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

2. **Create a Service Account** (if not already created):
```bash
gcloud iam service-accounts create sql-proxy-service \
    --description="Service account for Cloud SQL Proxy" \
    --display-name="SQL Proxy Service Account"
```

3. **Grant necessary permissions**:
```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:sql-proxy-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"
```

4. **Generate and download the credentials file**:
```bash
gcloud iam service-accounts keys create sql-proxy-key.json \
    --iam-account=sql-proxy-service@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### Setting Up the Database Proxy

1. **Copy the credentials file** to the infrastructure scripts directory:
```bash
cp sql-proxy-key.json rhesis/infrastructure/scripts/
```

2. **Download the Cloud SQL Proxy binary** (if not already present):
```bash
cd rhesis/infrastructure/scripts
wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O cloud-sql-proxy
chmod +x cloud-sql-proxy
```

3. **Install the database proxy service**:
```bash
cd rhesis/infrastructure/scripts
sudo ./setup-db-proxy-service.sh install
```

4. **Start the proxy service**:
```bash
sudo ./setup-db-proxy-service.sh start
```

5. **Verify the service is running**:
```bash
sudo ./setup-db-proxy-service.sh status
```

### Managing the Proxy Service

- **View logs**: `sudo ./setup-db-proxy-service.sh logs`
- **Follow logs in real-time**: `sudo ./setup-db-proxy-service.sh follow-logs`
- **Restart service**: `sudo ./setup-db-proxy-service.sh restart`
- **Stop service**: `sudo ./setup-db-proxy-service.sh stop`
- **Uninstall service**: `sudo ./setup-db-proxy-service.sh uninstall`

### Environment Configuration

Update your `.env` file to use the Unix socket created by the proxy:

```bash
# For Cloud SQL via Unix socket
DB_HOST=/cloudsql/YOUR_PROJECT_ID:REGION:INSTANCE_ID
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_username
DB_PASSWORD=your_password
```

### Security Notes

- **Never commit** the `sql-proxy-key.json` file to version control
- **Rotate credentials** periodically for security
- **Use least privilege** - only grant necessary permissions to the service account
- **Monitor access** through Google Cloud Console audit logs

### Troubleshooting

- **Connection issues**: Check if the proxy service is running with `sudo systemctl status db-proxy`
- **Permission errors**: Verify the service account has `roles/cloudsql.client` role
- **Instance connection**: Ensure the Cloud SQL instance allows connections and is in the correct region

## Questions or Need Help?

If you have questions or need help with the contribution process:
- Contact us at support@rhesis.ai
- Create an issue in the repository
- Check our [documentation](https://docs.rhesis.ai)

## Dependency Locking

We use `uv lock` to generate a lock file for reproducible installs. By default, `uv lock` only locks main dependencies. To include dev dependencies (and any other optional groups), use the `--extra` flag:

```bash
uv lock --extra dev
```

You can specify multiple extras if needed:
```bash
uv lock --extra dev --extra docs
```

| Command                                 | Locks main deps | Locks dev deps | Locks other extras |
|------------------------------------------|:--------------:|:--------------:|:------------------:|
| `uv lock`                               |      ✅        |      ❌        |        ❌          |
| `uv lock --extra dev`                   |      ✅        |      ✅        |        ❌          |
| `uv lock --extra dev --extra docs`      |      ✅        |      ✅        |        ✅          |

**Best Practice:**
- Always use `uv lock --extra dev` to ensure your lock file includes all development dependencies.
- Add more `--extra` flags as needed for other optional dependency groups.
