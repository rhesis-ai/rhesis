# 🚀 Contributing to Rhesis

Thank you for your interest in contributing to Rhesis! This document provides guidelines and instructions for contributing to our main repository.

## 📋 Table of Contents

- 📁 [Project Structure](#project-structure)
- 🔄 [Development Workflow](#development-workflow)
- 🎨 [Coding Standards](#coding-standards)
- 📝 [Commit Guidelines](#commit-guidelines)
- 🏷️ [Versioning and Release Process](#versioning-and-release-process)
- 📨 [Pull Request Process](#pull-request-process)
- 🤖 [GitHub Automation Tools](#github-automation-tools)
- 🧪 [Testing](#testing)
- 📚 [Documentation](#documentation)

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

## 🔄 Development Workflow

1. 🍴 Fork the repository
2. 🌿 Create a feature branch from `main`
3. ✍️ Make your changes
4. 🧪 Run tests
5. 📨 Submit a pull request

## 🎨 Coding Standards

Follow language-specific style guides:
- 🐍 **Python**: PEP 8
- 🟨 **JavaScript/TypeScript**: ESLint with our configuration

Key principles:
- 💬 Write meaningful comments and documentation
- 📏 Keep functions small and focused
- 🏷️ Use descriptive variable and function names

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

## 📨 Pull Request Process

1. ✅ Ensure your code adheres to our coding standards
2. 📚 Update documentation as necessary
3. 🧪 Include tests that verify your changes
4. 📝 Update the CHANGELOG.md file with details of changes
5. 👥 The PR must receive approval from at least one maintainer
6. 🔄 Once approved, a maintainer will merge your PR

## 🤖 GitHub Automation Tools

This repository includes automation scripts and tools for GitHub workflows and repository management located in the `.github/` directory.

> **📋 For comprehensive release information, see [RELEASING.md](RELEASING.md)**

### 🚀 PR Creation Script

#### 📝 `create-pr.sh`

An intelligent script that automates the creation of pull requests by analyzing your current branch and generating meaningful titles and descriptions. 

**🔍 New: Push Detection & Auto-Resolution**
The script now includes smart detection for unpushed content:
- **Branch Detection**: Automatically detects if your branch doesn't exist on remote
- **Change Detection**: Identifies local commits that haven't been pushed
- **Interactive Prompting**: Offers clear options to push content before PR creation
- **Force Mode**: Skip detection with `--force` flag for advanced users

### 🏷️ Release Management Script

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

## 🧪 Testing

- ✍️ Write unit tests for all new features and bug fixes
- ✅ Ensure all tests pass before submitting a PR
- 🔗 Include integration tests where appropriate

## 📚 Documentation

- 📝 Update documentation for any new features or changes
- 📋 Document public APIs and interfaces
- 💡 Include examples where appropriate

Thank you for contributing to Rhesis! 🎉 