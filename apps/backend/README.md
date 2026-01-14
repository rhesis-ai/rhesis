# 🚀 Rhesis Backend

## Description

Rhesis is an application that provides an interface for managing and testing various LLM configurations, prompts, templates, categories, responses, benchmarks, and test results.

## 📚 Getting Started

**📋 For comprehensive setup instructions, see the [CONTRIBUTING.md](CONTRIBUTING.md) guide.**

### Quick Start

1. Clone the repository:

```sh
git clone <repository_url>
cd rhesis/apps/backend
```

## 🐍 Python Requirements

The Rhesis backend requires **Python 3.10** or newer. 

**📋 For detailed platform-specific Python and pyenv setup instructions, see [Python Version Requirements](CONTRIBUTING.md#python-version-requirements) in CONTRIBUTING.md.**

### 🍎 macOS Quick Setup
```sh
brew install pyenv
pyenv install 3.10.17
pyenv local 3.10.17
```

### 🐧 Linux Quick Setup  
```sh
curl https://pyenv.run | bash
# Install build dependencies (🐧 Ubuntu/Debian)
sudo apt update && sudo apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev curl llvm libncurses5-dev \
libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev python-openssl
pyenv install 3.10.17
pyenv local 3.10.17
```

## ⚡ UV Installation & Environment Setup

[UV](https://github.com/astral-sh/uv) is a fast Python package installer and resolver used for dependency management.

**📋 For detailed UV installation instructions, see [UV Installation & Python Environment Setup](CONTRIBUTING.md#uv-installation--python-environment-setup) in CONTRIBUTING.md.**

### Quick UV Setup

**🍎 macOS**
```sh
brew install uv
```

**🐧 Linux**  
```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Create Environment & Install Dependencies
```sh
# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync --extra dev
uv pip install -e .
uv pip install -e ../../sdk
```

## ☁️ Database Setup (Required)

**⚠️ Important**: The backend requires a database connection to run.

**📋 For complete database setup instructions including Cloud SQL Proxy configuration, see [Cloud Database Setup](CONTRIBUTING.md#cloud-database-setup-currently-required-for-backend) in CONTRIBUTING.md.**

Quick summary:
1. Set up Google Cloud CLI and authentication
2. Download Cloud SQL Proxy binary (platform-specific)
3. Configure database proxy service
4. Set up environment variables

## 🚀 Running the Backend Locally

**📋 For complete development workflow, see [Development Workflow](CONTRIBUTING.md#development-workflow) in CONTRIBUTING.md.**

### Option A: Use the Start Script (Recommended)
```sh
./start.sh
```

### Option B: Use the CLI Tool
```sh
cd ../../  # Navigate to repository root
./rh backend start
```

### Option C: Run Directly with Uvicorn
```sh
uvicorn rhesis.backend.app.main:app --host 0.0.0.0 --port 8080 --log-level debug --reload
```

### Running with Docker

To run the backend using Docker:

1. Build the Docker image:
```sh
docker build -t rhesis-backend:local .
```

2. Run the container:
```sh
docker run -p 8080:8080 --env-file apps/backend/.env.docker --add-host="host.docker.internal:host-gateway" rhesis-backend:local
```

This command:
- Maps port 8080 from the container to your host
- Uses environment variables from `.env.docker`
- Adds a host entry that allows the container to communicate with services on your host machine

## 🔧 Environment Configuration

**⚠️ Required**: The environment must be properly configured before the backend can run.

**📋 For complete environment setup, see [Environment Configuration](CONTRIBUTING.md#environment-configuration) in CONTRIBUTING.md.**

### Quick Setup

**Option 1: Retrieve from Google Cloud Secrets Manager (Recommended)**
```sh
gcloud secrets versions access latest --secret="env-backend" > .env
```

**Option 2: Manual Configuration**
```sh
cp .env.example .env
# Edit .env with your specific configuration values
```

**Note**: The `.env` file contains essential configuration including database credentials, API keys, and other environment-specific settings.

### Key Environment Variables

- `JWT_SECRET_KEY`: Required for authentication tokens and service delegation
- `POLYPHEMUS_URL`: URL of the Polyphemus service (default: `https://polyphemus.rhesis.ai`)
  - For local development: `http://localhost:8000`

## 📋 Need Help?

### Complete Setup Guide
For comprehensive setup instructions including:
- 🐍 Detailed Python/pyenv installation for your platform
- ⚡ UV installation and virtual environment setup  
- ☁️ Cloud database configuration and proxy setup
- 🔐 Secret Manager and environment configuration
- 🛠️ Development workflow and tools
- 🔄 Pull request creation and best practices
- 🧪 Testing and code quality checks

**👉 See the [CONTRIBUTING.md](CONTRIBUTING.md) guide**

### Quick Reference
- **Start the server**: `./start.sh` or `./rh backend start`
- **Run tests**: `make test`
- **Format code**: `make format`
- **Lint code**: `make lint`
- **All checks**: `make all`

## 📚 Documentation

### API Query Guide

The Rhesis backend supports OData filtering for powerful querying capabilities. See the [OData Query Guide](../../docs/backend/odata-guide.md) for comprehensive documentation including:

- Basic comparison operators (eq, ne, gt, lt, etc.)
- String functions (contains, startswith, endswith, tolower, toupper)
- Navigation properties for filtering across relationships
- Logical operators (and, or, not) with complex expressions
- Advanced features like sorting and pagination
- Best practices and complete examples

All examples in the guide have been tested and verified to work with the current implementation.