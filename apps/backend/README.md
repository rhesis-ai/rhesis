# Rhesis Application

## Description

Rhesis is an application that provides an interface for managing and testing various LLM configurations, prompts, templates, categories, responses, benchmarks, and test results.

## Setup

1. Clone the repository:

```sh
git clone <repository_url>
cd rhesis

```

## Python Requirements

Rhesis backend requires **Python 3.10** or newer. We recommend using [pyenv](https://github.com/pyenv/pyenv) to manage Python versions:

```sh
# Install pyenv
curl https://pyenv.run | bash

# Install build dependencies (Ubuntu/Debian)
sudo apt update && sudo apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev \
libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev python-openssl

# Install Python 3.10
pyenv install 3.10.17

# Set local Python version for backend
cd apps/backend
pyenv local 3.10.17

# Create a virtual environment with UV
uv venv
```

## Working with UV

[UV](https://github.com/astral-sh/uv) is a Python package installer and resolver that's used in this project. Here's how to use it:

```sh
# Install the project in development mode
uv pip install -e .

# Install a specific package
uv pip install <package_name>

# Install requirements
uv pip install -r requirements.txt

# Update dependencies
uv pip install --upgrade <package_name>
```

## Running the Backend Locally

### Running Directly with Uvicorn

After installing dependencies, you can run the backend directly using uvicorn:

```sh
uvicorn rhesis.backend.app.main:app --host 0.0.0.0 --port 8080 --log-level debug --reload
```

The `--reload` flag enables auto-reloading when code changes are detected, which is useful during development.

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

### Environment Variables

The backend requires certain environment variables to be set. For local development:

1. Copy the example environment file: 
```sh
cp apps/backend/.env.example apps/backend/.env
```

2. Edit the `.env` file with your specific configuration values.

For Docker, follow the same process but create an `.env.docker` file that's compatible with container environments.