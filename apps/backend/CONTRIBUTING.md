# 🚀 Contributing to Rhesis Backend

Thank you for your interest in contributing to the Rhesis backend! 🎉 This document provides guidelines for contributing to our project.

### 📥 First, Clone the Repository

Before setting up Python, clone the repository so you can install everything in the correct location:

```bash
git clone https://github.com/rhesis-ai/rhesis.git
```

### ⚡ Development Setup

> **ℹ️ Please Read:**  
Before contributing to the backend, **read the main [`CONTRIBUTING.md`](../../CONTRIBUTING.md)** at the root of the repository. It contains essential guidelines for all contributors, including details on development workflow, code style, and tooling.

**Before you start:**  
- Install [`uv`](https://docs.astral.sh/uv/) for Python environment management.

- **Formatting & Linting:**  
  - Use [Ruff](https://docs.astral.sh/ruff/) for formatting and linting Python code.
  - The use of Makefile targets (`make format`, `make lint`), pre-commit hooks, and the Ruff VS Code extension is described in the main `CONTRIBUTING.md` and is recommended for consistency.


### 📥 Clone the Repository

```bash
git clone https://github.com/rhesis-ai/rhesis.git
```


Create and activate a virtual environment in the backend directory:

```bash
# Navigate to the backend directory
cd apps/backend

# Create a virtual environment with UV
uv sync --dev
# Activate the virtual environment
source .venv/bin/activate
```

This will:
- **Sync dependencies**: Install all project dependencies, including development dependencies (such as Sphinx for docs, testing tools, linters)
- **Install backend and SDK in editable mode** meaning changes to the source code are immediately reflected without reinstalling
- **Install Rhesis SDK dependency in editable mode** The backend depends on the Rhesis SDK for client communication, data models, and shared utilities. Installing it in editable mode allows you to modify both backend and SDK code simultaneously during development

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
- **🐧 Linux users**: Use `cloud_sql_proxy.linux.amd64` 
- **🍎 macOS users**: Use `cloud_sql_proxy.darwin.arm64` (Apple Silicon) or `cloud_sql_proxy.darwin.amd64` (Intel)
- **These are different binaries** - using the wrong one will result in "Bad CPU type" or similar errors.

#### 🐧 For Linux Users (Automated Service Setup)

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

#### 🍎 For macOS Users (Manual Proxy Execution)

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

### 🐧 Managing the Proxy Service (Linux Only)

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
# Navigate to the backend directory
cd apps/backend

# Retrieve the .env file from Secrets Manager
gcloud secrets versions access latest --secret="env-backend" > .env

# Verify the file was created
ls -la .env
```

#### Option 2: Manual Configuration

If configuring manually, create and update your `.env` file in the backend directory:

```bash
# Navigate to the backend directory
cd apps/backend

# Copy the example file (if it exists)
cp .env.example .env

# Edit the .env file with your configuration
# For Cloud SQL via Unix socket, include:
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

#### 🐧 For Linux Users
- **Connection issues**: Check if the proxy service is running with `sudo systemctl status db-proxy`
- **Permission errors**: Verify the service account has `roles/cloudsql.client` role
- **Instance connection**: Ensure the Cloud SQL instance allows connections and is in the correct region

#### 🍎 For macOS Users
- **Connection issues**: Ensure `./db-proxy.sh` is running in a terminal and hasn't stopped
- **Permission errors**: Verify the service account has `roles/cloudsql.client` role
- **Binary compatibility issues**: 
  - **Wrong architecture**: Check your Mac's architecture with `uname -m`
    - For Apple Silicon (arm64): Use `cloud_sql_proxy.darwin.arm64`
    - For Intel (x86_64): Use `cloud_sql_proxy.darwin.amd64`
  - **Wrong OS binary**: Ensure you downloaded the macOS binary (`.darwin.*`), not the Linux binary (`.linux.amd64`)
  - If you get "Bad CPU type in executable", you downloaded the wrong architecture or OS binary
- **Instance connection**: Ensure the Cloud SQL instance allows connections and is in the correct region

### 🍎 Additional Options for macOS Users

If the direct `db-proxy.sh` method above doesn't work for your setup, you can:
1. **Use Docker**: Run the backend in a Docker container with Linux
2. **Manual Cloud SQL Proxy**: Download and run the [Cloud SQL Proxy](https://cloud.google.com/sql/docs/postgres/sql-proxy) manually
3. **Development Environment**: Use a Linux VM or cloud development environment

## 🔧 RH CLI Tool

The repository includes a unified CLI tool for managing development servers.

**⚠️ Important**: These commands must be run from the **repository root** (not from `apps/backend`):

```bash
# Navigate to the repository root first
cd ../../  # If you're in apps/backend
# OR
cd <repo root>

# Then run the CLI commands
./rh backend start    # Start the backend server
./rh frontend start   # Start the frontend server
./rh help            # Show available commands
```

The CLI provides a consistent interface for starting both services with beautiful, colorful output and proper error handling.

## 🔄 Development Workflow

**📋 Prerequisites**: Before starting development, ensure you have completed:
1. [Cloud Database Setup](#cloud-database-setup-currently-required-for-backend) - Currently required as the backend needs a database connection to run (local database support coming in the future)
2. [Environment Configuration](#environment-configuration) - The `.env` file must be properly configured with all required variables

3. 🚀 **Start the development server** (choose one method):

   **Option A: Use the unified CLI from repository root:**
   ```bash
   cd ../../  # Navigate back to repository root
   ./rh backend start
   ```

   **Option B: Use the backend start script directly (recommended since you're already in apps/backend):**
   ```bash
   # Ensure virtual environment is activated
   source .venv/bin/activate
   
   ./start.sh
   ```

   **Option C: Run manually:**
   ```bash
   # From the backend directory, ensure virtual environment is activated
   source .venv/bin/activate
   
   uvicorn rhesis.backend.app.main:app --host 0.0.0.0 --port 8080 --log-level debug --reload
   ```

## 🧪 Testing

- ✍️ Write tests for all new features and bug fixes
- 📁 Place tests in the `tests/` directory (or as specified in the project)
- 🏃 Run tests with `make test` from the `apps/backend` directory

## ❓ Questions or Need Help?

If you have questions or need help with the contribution process:
- Contact us at support@rhesis.ai
- Create an issue in the repository
- Check our [documentation](https://docs.rhesis.ai)

Thank you for contributing to Rhesis! 🎉 