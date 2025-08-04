# 📦 Contributing to Rhesis SDK

Thank you for your interest in contributing to Rhesis SDK! This document provides guidelines and instructions for contributing to our Python SDK.

## 🐍 Python Version Requirements

The Rhesis SDK requires **Python 3.10** or newer. If you encounter issues with your system's Python version, we recommend using [pyenv](https://github.com/pyenv/pyenv) to manage Python versions.

### 📥 First, Clone the Repository

Before setting up Python, clone the repository so you can install everything in the correct location:

```bash
git clone https://github.com/rhesis-ai/rhesis.git
cd rhesis/sdk
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

After installing UV, create and activate a virtual environment in the SDK directory:

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
- **Virtual environments**: Always activate your virtual environment before installing packages or running the SDK
- **Deactivation**: Use `deactivate` command to exit the virtual environment when done
- **Reactivation**: Run `source .venv/bin/activate` each time you start working on the project

## ⚡ Development Setup

**Prerequisites**: You should have already completed:
- [Python Version Requirements](#python-version-requirements) - Repository cloned and Python/pyenv set up
- [UV Installation & Python Environment Setup](#uv-installation--python-environment-setup) - UV installed and virtual environment created

1. 📦 **Install SDK dependencies**:

   **⚠️ Important**: Ensure your virtual environment is activated before installing dependencies.

   ```bash
   # Verify you're in the virtual environment (should show .venv path)
   which python
   
   # Install dependencies
   uv pip install hatch
   uv sync --extra dev
   uv pip install -e .
   ```
   This will:
   - **Install Hatch build tool**: Required for building and managing the SDK package
   - **Sync dependencies**: Install all project dependencies, including development dependencies (such as Sphinx for docs, testing tools, linters)
   - **Install SDK in editable mode** (`-e .`): The `-e` flag installs the current package (the `.` refers to current directory) in "editable" or "development" mode, meaning changes to the source code are immediately reflected without reinstalling

## 🔄 Development Workflow

**Prerequisites**: You should have completed the Python setup, UV installation, and SDK dependency installation from the sections above.

1. 🌿 **Create a new branch for your feature**:
```bash
git checkout -b feature/your-feature-name
```

2. 🪝 **Enable pre-commit hooks**:
```bash
pre-commit install
```

3. ✍️ **Make your changes and ensure all checks pass using the Makefile**:
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

4. 📝 **Commit your changes**:
```bash
git add .
git commit -m "feat: your descriptive commit message"
```

5. 📤 **Push your changes and create a Pull Request**:
```bash
git push origin feature/your-feature-name
```

## 📨 Pull Request Guidelines

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
- 📁 Tests should be placed in the `../tests/sdk/` directory
- 🏃 Run the test suite with `make test` from the `sdk` directory

## 📚 Documentation

- 📝 Update documentation for any changed functionality
- 💬 Include docstrings for new functions and classes
- 🔄 Keep the README.md up to date with any user-facing changes

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

**✨ Best Practice:**
- ✅ Always use `uv lock --extra dev` to ensure your lock file includes all development dependencies.
- ➕ Add more `--extra` flags as needed for other optional dependency groups.

## ❓ Questions or Need Help?

If you have questions or need help with the contribution process:
- 📧 Contact us at support@rhesis.ai
- 🐛 Create an issue in the repository
- 📖 Check our [documentation](https://docs.rhesis.ai) 