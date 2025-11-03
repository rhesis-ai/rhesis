# 🚀 Contributing to Rhesis

Thank you for your interest in contributing to Rhesis! This document provides **general guidelines and instructions** for contributing to our main repository.

## 📋 Table of Contents

- 📖 [Component-Specific Contributing Guides](#component-specific-contributing-guides)
- 📁 [Project Structure](#project-structure)
- 🐧 [Tools Installation on Linux](#tools-installation-on-linux)
- 🐍 [Python Environment Setup](#python-environment-setup)
- 🧹 [Coding Standards, Linting and Formatting](#coding-standards-linting-and-formatting)
- 📚 [Documentation](#documentation)
- 🧪 [Testing](#testing)
- 🔄 [Development Workflow](#development-workflow)
- 📝 [Commit Guidelines](#commit-guidelines)
- 🔀 [Pull Request Process](#pull-request-process)
- 🤖 [GitHub Automation Tools](#github-automation-tools)
- 🏷️ [Versioning and Release Process](#versioning-and-release-process)
- ❓ [Questions or Need Help?](#questions-or-need-help)

<a id="component-specific-contributing-guides"></a>
## 📖 Component-Specific Contributing Guides

This is the **general contributing guide** for the Rhesis monorepo. Each component has its own detailed contributing guide:

- 📦 **[SDK Contributing Guide](sdk/CONTRIBUTING.md)**
- 🔙 **[Backend Contributing Guide](apps/backend/CONTRIBUTING.md)**
- 🎨 **[Frontend Contributing Guide](apps/frontend/CONTRIBUTING.md)**

**Please read this general guide first, then read the specific guide for the component you're contributing to.**





<a id="project-structure"></a>
## 📁 Project Structure

The Rhesis repository is organized as a monorepo containing multiple applications and packages:

```
rhesis/
├── apps/
│   ├── backend/       # FastAPI backend service
│   ├── frontend/      # React frontend application
│   ├── worker/        # Celery worker service
│   ├── chatbot/       # Chatbot application
│   └── polyphemus/    # Monitoring service
├── sdk/               # Python SDK for Rhesis
├── infrastructure/    # Infrastructure as code
├── scripts/           # Utility scripts
└── docs/              # Documentation
```

<a id="tools-installation-on-linux"></a>
## 🐧 Tools Installation on Linux

These are the following tools that are required for development:
```bash
# Install build dependencies (Ubuntu/Debian)
sudo apt update && sudo apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev \
libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev python-openssl

```


<a id="python-environment-setup"></a>
## 🐍 Python Environment Setup

Both backend and SDK use Python as the primary language. We utilize the `uv` tool for Python version and package management. UV is a fast Python package installer and resolver that handles dependency management and virtual environments efficiently.

UV is our recommended solution for all development tasks. While it differs from traditional package managers, it offers superior performance and ease of use. For comprehensive information, refer to the [uv documentation](https://docs.astral.sh/uv/).


### 🍎 macOS UV Installation
**Prerequisites**: Ensure you have [Homebrew](https://brew.sh/) and Xcode Command Line Tools installed. Install Xcode Command Line Tools using `xcode-select --install`
```bash
# Install UV via Homebrew (recommended)
brew install uv

# Alternative installation via curl
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### 🐧 Linux UV Installation

```bash
# Install UV via curl (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add UV to your PATH (usually handled automatically by the installer)
# If manual configuration is needed, add this line to your ~/.bashrc or ~/.zshrc:
# export PATH="$HOME/.local/bin:$PATH"

# Reload your shell configuration
source ~/.bashrc  # or ~/.zshrc

# Verify installation
uv --version
```


<!-- to do: add instructions for frontend -->

<a id="coding-standards-linting-and-formatting"></a>
## 🎨 Coding Standards, Linting and Formatting

**Key principles:**
- 💬 Write meaningful comments and comprehensive documentation
- 📏 Maintain focused, single-responsibility functions
- 🏷️ Use descriptive variable and function names

**Follow language-specific style guides:**
- 🐍 **Python**: We adhere to PEP 8 standards and utilize [Ruff](https://docs.astral.sh/ruff/) for both
formatting and linting.
- 🟨 **JavaScript/TypeScript**: We use ESLint for linting

**Our code quality toolchain includes:**
- 🖥️ VS Code / Cursor Configuration
- 🛠️ Makefile: Linting & Formatting with Ruff
- 📝 Pre-commit hooks

**Note:** All tools utilize identical Ruff settings and configuration for consistency.

### 🖥️ VS Code / Cursor Configuration

The repository includes a `.vscode/settings.json` file that automatically configures your editor with the Ruff formatter and linter. Installation of the **[Ruff](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff)** extension is required.

The extension automatically executes Ruff formatting and linting on file save.

### 🛠️ Makefile: Linting & Formatting with Ruff

We use a `Makefile` to streamline common development tasks such as linting, formatting, type checking, and testing.

The SDK and backend employ different Makefile configurations but share identical targets:

Available targets include:
- `make format` &mdash; Formats **all** Python files using Ruff
- `make format_diff` &mdash; Formats only **modified files** using Ruff
- `make lint` &mdash; Lints **all** Python files using Ruff
- `make lint_diff` &mdash; Lints only **modified files** using Ruff
- `make test` &mdash; Executes the test suite
- `make all` &mdash; Runs all checks (format_diff, lint_diff, test)


> **ℹ️ Note:**
> You must execute all `make` commands from within either the `apps/backend/` or `sdk/` directories.
> Running `make` from the repository root directory is **not supported** and will not work as expected.


### 📝 Pre-commit Hooks
We implement pre-commit hooks to automatically execute formatting and linting scripts before each commit.
It also checks for secrets in the code using TruffleHog.

Before installing the pre-commit hooks, you need to install TruffleHog:
```bash
# Install TruffleHog on macOS
brew install trufflehog
# Install TruffleHog on Linux
curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin
```


Installation requires the following command:
```bash
uvx pre-commit install
```

On every commit, pre-commit hooks automatically run Ruff formatting and linting on modified files.
When issues are detected, the system attempts automatic resolution. Unresolved issues appear in the commit message and require manual attention. To proceed with the commit, resolve all issues and stage the modified files using the `git add` command. You can then retry the commit or manually execute checks using `make format` and `make lint` commands.


If you want to disable pre-commit hooks for a specific commit, you can use the following command:
```bash
git commit --no-verify
```

To remove pre-commit hooks, execute:
```bash
uvx pre-commit uninstall
```




<a id="documentation"></a>
## 📚 Documentation

- 📝 Update documentation for any modified functionality
- 💬 Include comprehensive docstrings for new functions and classes
- 🔄 Maintain README.md currency with user-facing changes

<a id="testing"></a>
## 🧪 Testing

- ✍️ Write unit tests for all new features and bug fixes
- ✅ Ensure all tests pass before submitting a PR
- 🔗 Include integration tests where appropriate

<a id="development-workflow"></a>
## 🔄 Development Workflow


1. 🌿 **Create a feature branch**:
```bash
git checkout -b feature/your-feature-name
```

2. 🪝 **Enable pre-commit hooks**:
```bash
uvx pre-commit install
```

3. ✍️ **Implement changes and verify all checks pass using the Makefile**:
```bash
make format      # Format code with Ruff
make format_diff # Show formatting differences without applying
make lint        # Lint code with Ruff
make lint_diff   # Lint only modified files with Ruff
make test        # Execute tests
```

Alternatively, run all checks simultaneously:
```bash
make all
```


4. 📝 **Commit your changes**:
```bash
git add .
git commit -m "feat: your descriptive commit message"
```

5. 📤 **Push changes and create a Pull Request**:
```bash
git push origin feature/your-feature-name
```

6. **Generate a Pull Request** using our automated PR tool:
```bash
# Navigate to the repository root first
cd <repo_root>

# Then create the PR
.github/pr
```


<a id="commit-guidelines"></a>
## 📝 Commit Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types include:
- ✨ `feat`: A new feature
- 🐛 `fix`: A bug fix
- 📚 `docs`: Documentation only changes
- 🎨 `style`: Changes that do not affect the meaning of the code
- ♻️ `refactor`: A code change that neither fixes a bug nor adds a feature
- ⚡ `perf`: A code change that improves performance
- 🧪 `test`: Adding missing tests or correcting existing tests
- 🔨 `build`: Changes that affect the build system or external dependencies
- 👷 `ci`: Changes to our CI configuration files and scripts


<a id="pull-request-process"></a>
## 📨 Pull Request Process

1. ✅ Ensure code adherence to our coding standards
2. 📚 Update documentation as necessary
3. 🧪 Include tests that verify your changes
4. 📝 Update the CHANGELOG.md file with change details
5. 👥 Obtain approval from at least one maintainer
6. 🔄 Maintainers will merge approved PRs

**Additional requirements:**
- ✅ Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification for commit messages
- 🧪 Include tests for new features
- 📚 Update documentation as needed
- ✔️ Ensure all checks pass before requesting review

<a id="github-automation-tools"></a>
## 🤖 GitHub Automation Tools

This repository includes automation scripts and tools for GitHub workflows and repository management located in the `.github/` directory.

To utilize these tools, you must install and authenticate the GitHub CLI tool:

1. 🛠️ **Install GitHub CLI** (required for automated PR creation):
```bash
# 🐧 Ubuntu/Debian
sudo apt update && sudo apt install gh

# 🍎 macOS
brew install gh

# Or download from: https://cli.github.com/
```

2. 🔐 **Authenticate with GitHub**:
```bash
gh auth login
```




### 🚀 PR Creation Script

#### 📝 `create-pr.sh`

An intelligent script that automates the creation of pull requests by analyzing your current branch and generating meaningful titles and descriptions.

**🔍 Enhanced Features**
The script now includes smart detection and update capabilities:
- **Push Detection**: Automatically detects if your branch or changes aren't pushed
- **Interactive Prompting**: Offers clear options to push content before PR creation
- **PR Update**: Updates existing PRs instead of failing when a PR already exists
- **Force Mode**: Skip detection with the `--force` flag for advanced users

#### Usage

```bash
# Basic usage (compares current branch to main)
./.github/create-pr.sh

# Compare to a different base branch
./.github/create-pr.sh develop

# Skip push detection (for advanced users)
./.github/create-pr.sh --force

# Get help and see all options
./.github/create-pr.sh --help

# Short alias (supports all options)
./.github/pr
./.github/pr --force
./.github/pr develop --force
```

#### Prerequisites

- [GitHub CLI (gh)](https://cli.github.com/) must be installed and authenticated
- Must be run from within a git repository
- Current branch must have commits that differ from the base branch

#### What it does

1. **Validates environment**: Checks for gh CLI and git repository
2. **🔍 Detects unpushed content**: Checks if branch/changes exist on remote (unless `--force` is used)
3. **🤝 Interactive resolution**: Prompts to push content if needed, with options to push now or exit
4. **Analyzes changes**: Gets commit history and file changes between branches
5. **Generates content**: Creates intelligent PR title and comprehensive description
6. **Creates PR**: Uses gh CLI to create the pull request
7. **Provides summary**: Shows PR details and optionally opens in browser

#### 🚨 Push Detection Scenarios

The script will detect and handle these common scenarios:

**Scenario 1: Branch doesn't exist on remote**
```
⚠️  [WARNING] The branch 'feature/new-functionality' doesn't exist on the remote repository.
   This means the entire branch needs to be pushed before creating a PR.

Options:
  1) Push now and continue with PR creation
  2) Exit and push manually later

What would you like to do? (1/2):
```

**Scenario 2: Branch exists but has unpushed commits**
```
⚠️  [WARNING] There are unpushed commits on branch 'feature/new-functionality'.
   You have local commits that haven't been pushed to the remote repository.

Options:
  1) Push now and continue with PR creation
  2) Exit and push manually later

What would you like to do? (1/2):
```

**Scenario 3: Everything is up to date**
```
ℹ️  [PR-Creator] Branch and all changes are already pushed to remote.
ℹ️  [PR-Creator] Generated PR title: New Functionality
```

**Scenario 4: PR already exists**
```
ℹ️  [PR-Creator] Found existing PR for branch 'feature/new-functionality'
ℹ️  [PR-Creator] Updating existing PR...
✅  [SUCCESS] Pull request updated successfully!
```

#### Branch Naming Conventions

The script intelligently handles different branch naming patterns and properly capitalizes common abbreviations:

- `feature/websocket-endpoint` → "Websocket Endpoint"
- `feature/api-dev-environment` → "API DEV Environment"
- `feature/ui-ux-improvements` → "UI UX Improvements"
- `fix/authentication-bug` → "Fix: authentication bug"
- `fix/auth-jwt-bug` → "Fix: AUTH JWT Bug"
- `hotfix/critical-security` → "Hotfix: critical security"
- `hotfix/prod-db-issue` → "Hotfix: PROD DB Issue"
- `custom-branch-name` → "Custom Branch Name"

**Supported Abbreviations:**
- **Infrastructure**: DEV, STG, STAGING, PROD, PRD, PRODUCTION, AWS, GCP, AZURE, K8S, DOCKER
- **APIs & Protocols**: API, REST, HTTP, HTTPS, URL, URI, GRPC, TCP, UDP, SSH, FTP, SMTP
- **Frontend**: UI, UX, CSS, HTML, JS, TS, JSX, TSX
- **Backend**: DB, SQL, JWT, AUTH, OAUTH, SSO, LDAP
- **Data**: JSON, XML, YAML, YML, CSV, PDF
- **DevOps**: CI, CD, QA, QC, PR
- **Tools**: SDK, CLI, GUI, IDE, VM, VPC, DNS
- **Business**: CRM, ERP, SAAS, PAAS, IAAS
- **Tech**: ML, AI, NLP, OCR, IOT, AR, VR

#### Generated PR Template

The script creates a comprehensive PR description including:

- 📝 Summary section for manual description
- 🔄 List of commits with hashes
- 📁 Files changed with count
- 📋 Detailed commit information
- ✅ Standard checklist for reviews
- 🧪 Testing section placeholder
- 📸 Screenshots section for UI changes
- 🔗 Related issues section

#### Example Output

```
[PR-Creator] Current branch: feature/websocket-endpoint
[PR-Creator] Base branch: main
[PR-Creator] Found 4 commit(s) to include in PR
[PR-Creator] Generated PR title: Websocket Endpoint
[PR-Creator] Creating PR...
[SUCCESS] Pull request created successfully!
[SUCCESS] URL: https://github.com/rhesis-ai/rhesis/pull/36
```


### 🏷️ Release Management Script
> **📋 For comprehensive release information, see [RELEASING.md](RELEASING.md)**

#### 🔄 `release`

A comprehensive release automation tool that manages version bumping, changelog generation, and tagging for individual components and platform-wide releases.

For detailed information about the release process, see **[RELEASING.md](RELEASING.md)**.

#### Quick Examples

```bash
# The release script automatically creates appropriate release branches

# Individual component release (updates versions and changelogs only)
./.github/release backend --minor
# → Creates branch: release/backend-v0.2.0

# Multiple components
./.github/release backend --minor frontend --patch
# → Creates branch: release/backend-v0.2.0-frontend-v0.1.1 (or release/multi-a1b2c3)

# All components + platform
./.github/release backend --minor frontend --minor worker --minor chatbot --minor polyphemus --minor sdk --minor platform --minor
# → Creates branch: release/v0.2.0

# Always test first (shows what branch would be created)
./.github/release --dry-run backend --minor
# → Would create release branch: release/backend-v0.2.0
```

### 📁 Automation Directory Structure

```
.github/
├── create-pr.sh        # Main PR automation script
├── pr                  # Short alias for create-pr.sh
├── release             # Main release management script
├── workflows/          # GitHub Actions workflows
└── actions/            # Custom GitHub Actions
```

### 🛠️ Adding New Automation Tools

When contributing new automation tools to the `.github/` directory:

1. 📝 Document the tool in this CONTRIBUTING.md section
2. 💡 Include usage examples and prerequisites
3. 🛡️ Add comprehensive error handling and validation
4. 🎨 Use consistent styling and output formatting
5. 🧪 Test thoroughly before committing
6. 📋 Follow the existing script patterns for consistency




<a id="versioning-and-release-process"></a>
## 🏷️ Versioning and Release Process

### 📊 Versioning Strategy

We follow [Semantic Versioning](https://semver.org/) (SemVer) for all components in the monorepo:

- 🔴 **Major version (X.0.0)**: Incompatible API changes
- 🟡 **Minor version (0.X.0)**: New functionality in a backward-compatible manner
- 🟢 **Patch version (0.0.X)**: Backward-compatible bug fixes

Each component (backend, frontend, SDK, etc.) maintains its own version number.

### 🏷️ Tagging Strategy

Since we use a monorepo structure, we employ a component-specific tagging strategy to distinguish between releases of different components:

#### 🎯 Component-Specific Tags

We use prefixed tags to identify which component a version belongs to:
- 🔙 `backend-v1.0.0` - For backend releases
- 🎨 `frontend-v2.3.1` - For frontend releases
- 📦 `sdk-v0.5.2` - For SDK releases
- ⚙️ `worker-v1.1.0` - For worker service releases
- 🤖 `chatbot-v0.9.0` - For chatbot application releases
- 👁️ `polyphemus-v0.3.2` - For monitoring service releases

#### 🌐 Platform-Wide Versioning

For the entire platform, we use a combination approach:

1. 🔧 Use component-specific tags for regular development (`backend-v1.2.0`, `frontend-v1.1.0`, `sdk-v0.2.5`)
2. 🎯 Periodically create platform-wide version tags (`v1.0.0`, `v2.0.0`) for major milestones

This gives us the flexibility of independent component development while still providing stable, well-documented platform releases for users who want a known-good configuration.

#### 🔧 Implementation

When releasing a component:

1. 📝 Update the component's version in its respective configuration file (e.g., `pyproject.toml`, `package.json`)
2. 📋 Update the component's CHANGELOG.md
3. 🏷️ Create a tag with the component prefix and version:
   ```
   git tag <component>-v<version>
   git push origin <component>-v<version>
   ```

4. 🔗 Reference these tags in your changelogs:
   ```
   [0.1.0]: https://github.com/rhesis-ai/rhesis/releases/tag/backend-v0.1.0
   ```

When creating a platform-wide release:

1. 📝 Update the main CHANGELOG.md with details of all component versions included
2. 🏷️ Create a platform-wide tag:
   ```
   git tag v<version>
   git push origin v<version>
   ```

3. 📋 Document the specific component versions included in this platform release

#### 🔄 Advanced Patterns

For more complex scenarios:

- 🌐 **Platform-wide releases**: These are significant milestones where all components have reached a stable, compatible state. They represent "known good" configurations of the entire platform:
  - Use simple version tags without component prefixes (e.g., `v1.0.0`, `v2.0.0`)
  - Document in the main CHANGELOG.md which specific component versions are included
  - Create these less frequently than component-specific releases
  - Example: `v1.0.0` might include `backend-v1.2.0`, `frontend-v1.1.5`, and `sdk-v0.2.3`
  - These releases are particularly useful for users who want a vetted, stable configuration

- 🔗 **Coordinated component releases**: When multiple components need to be released together due to interdependencies:
  - Create individual component tags for each component being released
  - Document the interdependencies in each component's CHANGELOG.md
  - Consider creating a platform-wide tag if the changes are significant enough

- 🚨 **Hotfixes**: For urgent fixes, use the format `<component>-v<version>-hotfix.<number>` (e.g., `backend-v1.0.0-hotfix.1`)



<a id="questions-or-need-help"></a>
## ❓ Questions or Need Help?

If you have questions or need help with the contribution process:
- Contact us at support@rhesis.ai
- Create an issue in the repository
- Check our [documentation](https://docs.rhesis.ai)

Thank you for contributing to Rhesis! 🎉
