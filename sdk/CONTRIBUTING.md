# 📦 Contributing to Rhesis SDK

Thank you for your interest in contributing to Rhesis SDK! This document provides guidelines for contributing to our Python SDK.

## Development Setup

> **ℹ️ Please Read:**  
Before contributing to the SDK, **read the main [`CONTRIBUTING.md`](../CONTRIBUTING.md)** at the root of the repository. It contains essential guidelines for all contributors, including details on development workflow, code style, and tooling.

**Before you start:**  
- Install [`uv`](https://docs.astral.sh/uv/) for Python environment management.

- **Formatting & Linting:**  
  - Use [Ruff](https://docs.astral.sh/ruff/) for formatting and linting Python code.
  - The use of Makefile targets (`make format`, `make lint`), pre-commit hooks, and the Ruff VS Code extension is described in the main `CONTRIBUTING.md` and is recommended for consistency.





### 📥 Clone the Repository

```bash
git clone https://github.com/rhesis-ai/rhesis.git
```

### 🐍 Create Virtual Environment

Create and activate a virtual environment using uv:

```bash
# Navigate to the SDK directory
cd rhesis/sdk
# Create a development virtual environment
uv sync --dev

# Activate the virtual environment
source .venv/bin/activate
```

You're now ready for development!

## 🧪 Testing

- ✍️ Write tests for all new features and bug fixes
- 📁 Place tests in the `../tests/sdk/` directory
- 🏃 Run tests with `make test` from the `sdk` directory


## ❓ Questions or Need Help?

If you have questions or need help with the contribution process:
- Contact us at support@rhesis.ai
- Create an issue in the repository
- Check our [documentation](https://docs.rhesis.ai)

Thank you for contributing to Rhesis! 🎉 