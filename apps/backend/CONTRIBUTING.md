# 🚀 Contributing to Rhesis Backend

Thank you for your interest in contributing to the Rhesis backend! 🎉 This document provides comprehensive guidelines and instructions for contributing to our project.

## 🐍 Python Version Requirements

The Rhesis backend requires **Python 3.10** or newer. If you encounter issues with your system's Python version, we recommend using [pyenv](https://github.com/pyenv/pyenv) to manage Python versions.

### 📥 First, Clone the Repository

Before setting up Python, clone the repository so you can install everything in the correct location:

```bash
git clone https://github.com/rhesis-ai/rhesis.git
cd rhesis/apps/backend
```

### 🍎 macOS Installation

**Prerequisites**: Ensure you have [Homebrew](https://brew.sh/) and Xcode Command Line Tools installed.

```bash
# Install pyenv via Homebrew
brew install pyenv

# Install required dependency
brew install xz

# Configure your shell (choose one based on your shell)
# For zsh (default on macOS Catalina+):
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zprofile
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zprofile
echo 'eval "$(pyenv init -)"' >> ~/.zprofile

# For bash:
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bash_profile
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bash_profile
echo 'eval "$(pyenv init -)"' >> ~/.bash_profile

# Reload your shell configuration
source ~/.zprofile  # or source ~/.bash_profile for bash

# Install Python 3.10
pyenv install 3.10.17

# Set global or local Python version
pyenv global 3.10.17  # Sets as default for all projects
# OR
pyenv local 3.10.17   # Sets for current directory only

# Verify installation
python --version
```

### 🐧 Linux Installation

```bash
# Install pyenv
curl https://pyenv.run | bash

# Install build dependencies (Ubuntu/Debian)
sudo apt update && sudo apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev \
libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev python-openssl

# Add pyenv to your shell (the installer usually does this automatically)
# If needed, add these lines to your ~/.bashrc or ~/.zshrc:
# export PYENV_ROOT="$HOME/.pyenv"
# [[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
# eval "$(pyenv init -)"

# Reload your shell
source ~/.bashrc  # or ~/.zshrc

# Install Python 3.10
pyenv install 3.10.17

# Set local Python version
pyenv local 3.10.17

# Verify installation
python --version
```

**Important Notes:**
- **macOS users**: If you encounter permission issues, you may need to run `xcode-select --install` to ensure Xcode Command Line Tools are properly installed
- **Shell configuration**: Changes to shell configuration files won't take effect until you restart your terminal or run the `source` command
- **Verification**: Always verify your Python version with `python --version` after installation

This ensures you're using a clean Python environment without potential conflicts from other packages or Python installations.

## ⚡ UV Installation & Python Environment Setup

UV is a fast Python package installer and resolver that we use for dependency management and virtual environments. Install UV after setting up Python with pyenv.

### 🍎 macOS UV Installation

```bash
# Install UV via Homebrew (recommended)
brew install uv

# Or install via curl (alternative method)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### 🐧 Linux UV Installation

```bash
# Install UV via curl (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add UV to your PATH (the installer usually does this automatically)
# If needed, add this line to your ~/.bashrc or ~/.zshrc:
# export PATH="$HOME/.local/bin:$PATH"

# Reload your shell
source ~/.bashrc  # or ~/.zshrc

# Verify installation
uv --version
```

### 🐍 Create Virtual Environment

After installing UV, create and activate a virtual environment in the backend directory:

```bash
# Create a fresh virtual environment with UV
uv venv

# Activate the virtual environment
source .venv/bin/activate

# Verify you're in the virtual environment
which python
python --version
```

**Important Notes:**
- **Virtual environments**: Always activate your virtual environment before installing packages or running the backend
- **Deactivation**: Use `deactivate` command to exit the virtual environment when done
- **Reactivation**: Run `source .venv/bin/activate` each time you start working on the project

## ⚡ Development Setup

**Prerequisites**: You should have already completed:
- [Python Version Requirements](#python-version-requirements) - Repository cloned and Python/pyenv set up
- [UV Installation & Python Environment Setup](#uv-installation--python-environment-setup) - UV installed and virtual environment created

1. 🛠️ **Install GitHub CLI** (required for automated PR creation):
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install gh

# macOS
brew install gh

# Or download from: https://cli.github.com/
```

2. 🔐 **Authenticate with GitHub**:
```bash
gh auth login
```

3. 📦 **Install backend dependencies**:

   **⚠️ Important**: Ensure your virtual environment is activated before installing dependencies.

   ```bash
   # Verify you're in the virtual environment (should show .venv path)
   which python
   
   # Install dependencies
   uv sync --extra dev
   uv pip install -e .
   uv pip install -e ../../sdk
   ```
   This will:
   - **Sync dependencies**: Install all project dependencies, including development dependencies (such as Sphinx for docs, testing tools, linters)
   - **Install backend in editable mode** (`-e .`): The `-e` flag installs the current package (the `.` refers to current directory) in "editable" or "development" mode, meaning changes to the source code are immediately reflected without reinstalling
   - **Install Rhesis SDK dependency** (`-e ../../sdk`): The backend depends on the Rhesis SDK for client communication, data models, and shared utilities. Installing it in editable mode allows you to modify both backend and SDK code simultaneously during development

## ☁️ Cloud Database Setup (Currently Required for Backend)

**⚠️ Important**: The Cloud Database Setup is **currently required** before running the backend server. The backend cannot start without a properly configured database connection.

**🔮 Future Development**: This is a temporary requirement while the project uses a shared cloud database. In the future, developers will be able to run their own local database, making this setup optional.

**🖥️ Platform Support**: The automated database proxy service setup is **Linux-only**. macOS users can use the manual `db-proxy.sh` method described below, or alternative connection methods if needed.

### Prerequisites

1. **Google Cloud CLI**: Install the [gcloud CLI tool](https://cloud.google.com/sdk/docs/install)
2. **Project Access**: Ensure you have access to the Google Cloud project and appropriate permissions

### Obtaining Credentials

1. **Authenticate with Google Cloud**:
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

2. **Obtain the credentials file**:

   **Option A: Retrieve from Google Cloud Secrets Manager (Recommended)**:
   ```bash
   gcloud secrets versions access latest --secret="sql-proxy-key" --format="get(payload.data)" | base64 -d > sql-proxy-key.json
   ```

   **Option B: Generate new credentials** (only if Option A doesn't work or you need custom credentials):
   
   First, create a service account and grant permissions:
   ```bash
   # Create a Service Account
   gcloud iam service-accounts create sql-proxy-service \
       --description="Service account for Cloud SQL Proxy" \
       --display-name="SQL Proxy Service Account"
   
   # Grant necessary permissions
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
       --member="serviceAccount:sql-proxy-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/cloudsql.client"
   
   # Generate the credentials file
   gcloud iam service-accounts keys create sql-proxy-key.json \
       --iam-account=sql-proxy-service@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```

### Setting Up the Database Proxy

**⚠️ Important Binary Distinction**: 
- **Linux users**: Use `cloud_sql_proxy.linux.amd64` 
- **macOS users**: Use `cloud_sql_proxy.darwin.arm64` (Apple Silicon) or `cloud_sql_proxy.darwin.amd64` (Intel)
- **These are different binaries** - using the wrong one will result in "Bad CPU type" or similar errors.

#### For Linux Users (Automated Service Setup)

1. **Copy the credentials file** to the infrastructure scripts directory:
```bash
cp sql-proxy-key.json <repo root>/infrastructure/scripts/
```

2. **Download the Cloud SQL Proxy binary for Linux** (if not already present):
```bash
cd <repo root>/infrastructure/scripts
curl -L https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -o cloud-sql-proxy
chmod +x cloud-sql-proxy
```

   **Note**: This downloads the **Linux AMD64 binary**. macOS users should follow the macOS-specific instructions below.

3. **Install the database proxy service**:
```bash
cd <repo root>/infrastructure/scripts
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

#### For macOS Users (Manual Proxy Execution)

**Note**: macOS users cannot use `setup-db-proxy-service.sh` as it creates Linux systemd services. Instead, use the direct proxy script:

1. **Copy the credentials file** to the infrastructure scripts directory:
```bash
cp sql-proxy-key.json <repo root>/infrastructure/scripts/
```

2. **Download the Cloud SQL Proxy binary for macOS** (if not already present):

   **⚠️ Important**: macOS requires a **different binary** than Linux. Choose the correct macOS binary for your Mac's architecture.

   **First, check your Mac's architecture:**
   ```bash
   uname -m
   ```
   
   **Then download the correct macOS binary based on your result:**
   
   **For Apple Silicon Macs (M1/M2/M3) - if `uname -m` shows `arm64`:**
   ```bash
   cd <repo root>/infrastructure/scripts
   curl -L https://dl.google.com/cloudsql/cloud_sql_proxy.darwin.arm64 -o cloud-sql-proxy
   chmod +x cloud-sql-proxy
   ```
   
   **For Intel Macs - if `uname -m` shows `x86_64`:**
   ```bash
   cd <repo root>/infrastructure/scripts
   curl -L https://dl.google.com/cloudsql/cloud_sql_proxy.darwin.amd64 -o cloud-sql-proxy
   chmod +x cloud-sql-proxy
   ```

   **Note**: These are **macOS-specific binaries** (`.darwin.arm64` or `.darwin.amd64`), which are different from the Linux binary (`.linux.amd64`) used in the Linux setup above.

3. **Verify the download and run the database proxy:**
   ```bash
   # Verify the binary works
   ./cloud-sql-proxy --version
   
   # Run the database proxy directly (each time you need it)
   ./db-proxy.sh
   ```

**Important for macOS users**: You'll need to run `./db-proxy.sh` each time you start development, as it doesn't install as a persistent service like on Linux.

### Managing the Proxy Service (Linux Only)

For Linux users who installed the proxy as a service:

- **View logs**: `sudo ./setup-db-proxy-service.sh logs`
- **Follow logs in real-time**: `sudo ./setup-db-proxy-service.sh follow-logs`
- **Restart service**: `sudo ./setup-db-proxy-service.sh restart`
- **Stop service**: `sudo ./setup-db-proxy-service.sh stop`
- **Uninstall service**: `sudo ./setup-db-proxy-service.sh uninstall`

**For macOS users**: Since you're running the proxy manually with `./db-proxy.sh`, you can stop it with `Ctrl+C` and restart by running the script again.

### Environment Configuration

**⚠️ Required**: The environment must be properly configured before the backend can run. The `.env` file contains essential configuration including database credentials, API keys, and other environment-specific settings.

#### Option 1: Obtain from Google Cloud Secrets Manager (Recommended)

The complete `.env` file can be retrieved from Google Cloud Secrets Manager:

```bash
# Retrieve the .env file from Secrets Manager
gcloud secrets versions access latest --secret="env-backend" > .env

# Verify the file was created
ls -la .env
```

#### Option 2: Manual Configuration

If configuring manually, update your `.env` file to use the Unix socket created by the proxy:

```bash
# For Cloud SQL via Unix socket
DB_HOST=/cloudsql/YOUR_PROJECT_ID:REGION:INSTANCE_ID
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_username
DB_PASSWORD=your_password

# Additional required environment variables (examples)
# API_KEY=your_api_key
# JWT_SECRET=your_jwt_secret
# ENVIRONMENT=development
```

**Note**: Ensure your `.env` file is placed in the `apps/backend/` directory and never commit it to version control.

### Security Notes

- **Never commit** the `sql-proxy-key.json` file to version control
- **Never commit** the `.env` file to version control - it contains sensitive credentials
- **Rotate credentials** periodically for security
- **Use least privilege** - only grant necessary permissions to the service account
- **Monitor access** through Google Cloud Console audit logs
- **Secrets Manager access** - Ensure you have appropriate permissions to access the `env-backend` secret

### Troubleshooting

#### For Linux Users
- **Connection issues**: Check if the proxy service is running with `sudo systemctl status db-proxy`
- **Permission errors**: Verify the service account has `roles/cloudsql.client` role
- **Instance connection**: Ensure the Cloud SQL instance allows connections and is in the correct region

#### For macOS Users
- **Connection issues**: Ensure `./db-proxy.sh` is running in a terminal and hasn't stopped
- **Permission errors**: Verify the service account has `roles/cloudsql.client` role
- **Binary compatibility issues**: 
  - **Wrong architecture**: Check your Mac's architecture with `uname -m`
    - For Apple Silicon (arm64): Use `cloud_sql_proxy.darwin.arm64`
    - For Intel (x86_64): Use `cloud_sql_proxy.darwin.amd64`
  - **Wrong OS binary**: Ensure you downloaded the macOS binary (`.darwin.*`), not the Linux binary (`.linux.amd64`)
  - If you get "Bad CPU type in executable", you downloaded the wrong architecture or OS binary
- **Instance connection**: Ensure the Cloud SQL instance allows connections and is in the correct region

### Additional Options for macOS Users

If the direct `db-proxy.sh` method above doesn't work for your setup, you can:
1. **Use Docker**: Run the backend in a Docker container with Linux
2. **Manual Cloud SQL Proxy**: Download and run the [Cloud SQL Proxy](https://cloud.google.com/sql/docs/postgres/sql-proxy) manually
3. **Development Environment**: Use a Linux VM or cloud development environment

## 🔧 RH CLI Tool

The repository includes a unified CLI tool for managing development servers:

```bash
./rh backend start    # Start the backend server
./rh frontend start   # Start the frontend server
./rh help            # Show available commands
```

Run these commands from the repository root. The CLI provides a consistent interface for starting both services with beautiful, colorful output and proper error handling.

## 🤖 Automated PR Creation Tool

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

## 🔄 Development Workflow

**📋 Prerequisites**: Before starting development, ensure you have completed:
1. [Cloud Database Setup](#cloud-database-setup-currently-required-for-backend) - Currently required as the backend needs a database connection to run (local database support coming in the future)
2. [Environment Configuration](#environment-configuration) - The `.env` file must be properly configured with all required variables

1. 🌿 **Create a new branch for your feature**:
```bash
git checkout -b feature/your-feature-name
```

2. 🪝 **Enable pre-commit hooks**:
```bash
pre-commit install
```

3. 🚀 **Start the development server** (choose one method):

   **Option A: Use the unified CLI from repository root:**
   ```bash
   cd ../../  # Navigate back to repository root
   ./rh backend start
   ```

   **Option B: Use the backend start script directly (recommended since you're already in apps/backend):**
   ```bash
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

## 📝 Pull Request Guidelines

- ✅ Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification for commit messages
- 🧪 Include tests for new features
- 📚 Update documentation as needed
- ✔️ Ensure all checks pass before requesting review

## 🎨 Code Style

We use several tools to maintain code quality:
- [Ruff](https://docs.astral.sh/ruff/) for code formatting and linting
- [MyPy](https://mypy.readthedocs.io/) for static type checking
- [Pre-commit](https://pre-commit.com/) for automated checks

All formatting and linting is handled by Ruff. Use the Makefile targets for a consistent workflow.

## 🧪 Testing

- ✍️ Write tests for all new features and bug fixes
- 📁 Tests should be placed in the `tests/` directory (or as specified in the project)
- 🏃 Run the test suite with `make test` from the `apps/backend` directory

## 📚 Documentation

- 📝 Update documentation for any changed functionality
- 💬 Include docstrings for new functions and classes
- 🔄 Keep the README.md up to date with any user-facing changes

## ❓ Questions or Need Help?

If you have questions or need help with the contribution process:
- Contact us at support@rhesis.ai
- Create an issue in the repository
- Check our [documentation](https://docs.rhesis.ai)

## 🔒 Dependency Locking

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
