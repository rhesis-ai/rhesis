# Contributing to Rhesis SDK

Thank you for your interest in contributing to Rhesis SDK! This document provides guidelines and instructions for contributing.

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/rhesis-ai/rhesis.git
cd rhesis/sdk
```

2. Install dependencies and development tools using [uv](https://github.com/astral-sh/uv) and [Hatch](https://hatch.pypa.io/):
```bash
uv pip install hatch
uv sync --extra dev
uv pip install -e .
```
This will:
- Sync all dependencies, including development dependencies (such as Sphinx for docs)
- Install the SDK package in editable mode

## Python Version Requirements

The Rhesis SDK requires **Python 3.10** or newer. If you encounter issues with your system's Python version, we recommend using [pyenv](https://github.com/pyenv/pyenv) to manage Python versions:

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

## Development Workflow

1. Create a new branch for your feature:
```bash
git checkout -b feature/your-feature-name
```

2. Enable pre-commit hooks:
```bash
pre-commit install
```

3. Make your changes and ensure all checks pass using the Makefile:
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

4. Commit your changes:
```bash
git add .
git commit -m "feat: your descriptive commit message"
```

5. Push your changes and create a Pull Request:
```bash
git push origin feature/your-feature-name
```

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
- Tests should be placed in the `../tests/sdk/` directory
- Run the test suite with `make test` from the `sdk` directory

## Documentation

- Update documentation for any changed functionality
- Include docstrings for new functions and classes
- Keep the README.md up to date with any user-facing changes

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

## Questions or Need Help?

If you have questions or need help with the contribution process:
- Contact us at support@rhesis.ai
- Create an issue in the repository
- Check our [documentation](https://docs.rhesis.ai) 