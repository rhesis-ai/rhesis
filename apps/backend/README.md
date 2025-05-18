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