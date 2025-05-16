# Rhesis Application

## Description

Rhesis is an application that provides an interface for managing and testing various LLM configurations, prompts, templates, categories, responses, benchmarks, and test results.

## Setup

1. Clone the repository:

```sh
git clone <repository_url>
cd rhesis

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