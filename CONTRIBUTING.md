# Contributing to Rhesis

Thank you for your interest in contributing to Rhesis! This document provides guidelines and instructions for contributing to our main repo.

## Table of Contents

- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Commit Guidelines](#commit-guidelines)
- [Versioning and Release Process](#versioning-and-release-process)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Documentation](#documentation)

## Project Structure

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

## Development Workflow

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Run tests
5. Submit a pull request

## Coding Standards

- Follow language-specific style guides:
  - Python: PEP 8
  - JavaScript/TypeScript: ESLint with our configuration
- Write meaningful comments and documentation
- Keep functions small and focused
- Use descriptive variable and function names

## Commit Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types include:
- feat: A new feature
- fix: A bug fix
- docs: Documentation only changes
- style: Changes that do not affect the meaning of the code
- refactor: A code change that neither fixes a bug nor adds a feature
- perf: A code change that improves performance
- test: Adding missing tests or correcting existing tests
- build: Changes that affect the build system or external dependencies
- ci: Changes to our CI configuration files and scripts

## Versioning and Release Process

### Versioning Strategy

We follow [Semantic Versioning](https://semver.org/) (SemVer) for all components in the monorepo:

- **Major version (X.0.0)**: Incompatible API changes
- **Minor version (0.X.0)**: New functionality in a backward-compatible manner
- **Patch version (0.0.X)**: Backward-compatible bug fixes

Each component (backend, frontend, SDK, etc.) maintains its own version number.

### Tagging Strategy

Since we use a monorepo structure, we employ a component-specific tagging strategy to distinguish between releases of different components:

#### Component-Specific Tags

We use prefixed tags to identify which component a version belongs to:
- `backend-v1.0.0` - For backend releases
- `frontend-v2.3.1` - For frontend releases
- `sdk-v0.5.2` - For SDK releases
- `worker-v1.1.0` - For worker service releases
- `chatbot-v0.9.0` - For chatbot application releases
- `polyphemus-v0.3.2` - For monitoring service releases

#### Platform-Wide Versioning

For the entire platform, we use a combination approach:

1. Use component-specific tags for regular development (`backend-v1.2.0`, `frontend-v1.1.0`, `sdk-v0.2.5`)
2. Periodically create platform-wide version tags (`v1.0.0`, `v2.0.0`) for major milestones

This gives us the flexibility of independent component development while still providing stable, well-documented platform releases for users who want a known-good configuration.

#### Implementation

When releasing a component:

1. Update the component's version in its respective configuration file (e.g., `pyproject.toml`, `package.json`)
2. Update the component's CHANGELOG.md
3. Create a tag with the component prefix and version:
   ```
   git tag <component>-v<version>
   git push origin <component>-v<version>
   ```

4. Reference these tags in your changelogs:
   ```
   [0.1.0]: https://github.com/rhesis-ai/rhesis/releases/tag/backend-v0.1.0
   ```

When creating a platform-wide release:

1. Update the main CHANGELOG.md with details of all component versions included
2. Create a platform-wide tag:
   ```
   git tag v<version>
   git push origin v<version>
   ```

3. Document the specific component versions included in this platform release

#### Advanced Patterns

For more complex scenarios:

- **Platform-wide releases**: These are significant milestones where all components have reached a stable, compatible state. They represent "known good" configurations of the entire platform:
  - Use simple version tags without component prefixes (e.g., `v1.0.0`, `v2.0.0`)
  - Document in the main CHANGELOG.md which specific component versions are included
  - Create these less frequently than component-specific releases
  - Example: `v1.0.0` might include `backend-v1.2.0`, `frontend-v1.1.5`, and `sdk-v0.2.3`
  - These releases are particularly useful for users who want a vetted, stable configuration

- **Coordinated component releases**: When multiple components need to be released together due to interdependencies:
  - Create individual component tags for each component being released
  - Document the interdependencies in each component's CHANGELOG.md
  - Consider creating a platform-wide tag if the changes are significant enough

- **Hotfixes**: For urgent fixes, use the format `<component>-v<version>-hotfix.<number>` (e.g., `backend-v1.0.0-hotfix.1`)

## Pull Request Process

1. Ensure your code adheres to our coding standards
2. Update documentation as necessary
3. Include tests that verify your changes
4. Update the CHANGELOG.md file with details of changes
5. The PR must receive approval from at least one maintainer
6. Once approved, a maintainer will merge your PR

## Testing

- Write unit tests for all new features and bug fixes
- Ensure all tests pass before submitting a PR
- Include integration tests where appropriate

## Documentation

- Update documentation for any new features or changes
- Document public APIs and interfaces
- Include examples where appropriate

Thank you for contributing to Rhesis! 