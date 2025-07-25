# 🚀 Rhesis Release Guide

This guide covers the complete release process for the Rhesis platform, including individual component releases and coordinated platform-wide releases.

## 📋 Table of Contents

- [🔍 Overview](#overview)
- [🛠️ Release Tool](#release-tool)
- [⚡ Quick Start](#quick-start)
- [📦 Component Management](#component-management)
- [🎯 Platform Releases](#platform-releases)
- [💡 Release Examples](#release-examples)
- [🔧 Prerequisites](#prerequisites)
- [⚙️ Configuration](#configuration)
- [🔬 Advanced Usage](#advanced-usage)
- [✨ Best Practices](#best-practices)
- [🔍 Troubleshooting](#troubleshooting)

## 🔍 Overview

The Rhesis repository uses a **component-based release strategy** where each component can be versioned and released independently, while also supporting coordinated platform-wide releases.

### 📦 Supported Components

| Component | Config File | Changelog Path |
|-----------|-------------|----------------|
| backend | `apps/backend/pyproject.toml` | `apps/backend/CHANGELOG.md` |
| frontend | `apps/frontend/package.json` | `apps/frontend/CHANGELOG.md` |
| worker | `apps/worker/requirements.txt` | `apps/worker/CHANGELOG.md` |
| chatbot | `apps/chatbot/requirements.txt` | `apps/chatbot/CHANGELOG.md` |
| polyphemus | `apps/polyphemus/requirements.txt` | `apps/polyphemus/CHANGELOG.md` |
| sdk | `sdk/pyproject.toml` | `sdk/CHANGELOG.md` |
| platform | `VERSION` | `CHANGELOG.md` |

## 🛠️ Release Tool

The Rhesis release tool (`.github/release`) is a Python-based automation script that:

- 🔢 **Semantic version bumping** for all components (patch, minor, major)
- 🎯 **Multi-component releases** with single command
- 🤖 **Automatic changelog generation** using LLM (Gemini) or fallback
- 🏷️ **Git tag creation** with component-specific naming
- 🌐 **Platform-wide releases** that coordinate multiple components
- 🧠 **Smart environment detection** (uses SDK virtual environment when available)
- 👀 **Dry run mode** to preview changes
- 🛡️ **Rollback-safe operations** with comprehensive validation

## ⚡ Quick Start

### 📦 Individual Component Release

```bash
# Single component
./.github/release backend --minor
# → Creates branch: release/backend-v0.2.0

# Multiple components (no platform)
./.github/release backend --minor frontend --patch sdk --major
# → Creates branch: release/multi-a1b2c3 (or release/multi-v0.2.0 if same version)
# → Platform version remains unchanged

# Manual branch management (if preferred)
git checkout -b release/backend-v0.2.0
./.github/release --no-branch backend --minor
```

### 🌐 Platform-Wide Release

```bash
# Full coordinated release (all components + platform)
./.github/release backend --minor frontend --minor worker --minor chatbot --minor polyphemus --minor sdk --minor platform --minor
# → Creates branch: release/v0.2.0

# Platform-only release (just platform version)
./.github/release platform --minor
# → Creates branch: release/v0.2.0
# → Only updates platform, NOT individual components

# Major platform release with mixed component updates
./.github/release \
  backend --major \
  frontend --minor \
  worker --patch \
  chatbot --patch \
  polyphemus --minor \
  sdk --minor \
  platform --major
# → Creates branch: release/v1.0.0
```

### 👀 Dry Run (Recommended)

Always test first:

```bash
# Preview what would happen (shows branch name that would be created)
./.github/release --dry-run backend --minor frontend --patch
# → Would create release branch: release/backend-v0.2.0-frontend-v0.1.1
```

## 📦 Component Management

### 🔢 Version Types

- 🐛 `--patch` (0.0.X) - Bug fixes, small updates
- ✨ `--minor` (0.X.0) - New features, backward-compatible changes  
- 💥 `--major` (X.0.0) - Breaking changes, major updates

### 🔄 Component Separation

Each component maintains:
- 🔢 **Independent versions**: Backend can be v2.0.0 while frontend is v1.5.0
- 📝 **Separate changelogs**: Only relevant changes for each component
- 🏷️ **Component-specific git tags**: `backend-v1.0.0`, `frontend-v1.2.0`, etc.
- 🎯 **Path-based commit filtering**: Only commits affecting that component's directory

## 🎯 Platform Releases

Platform releases coordinate multiple components and create a snapshot of the entire system.

### ⚠️ **Important: Platform-Only Behavior**

**Platform releases do NOT automatically bump all components!**

```bash
# This ONLY bumps the platform version (VERSION file)
./.github/release platform --minor
# → Updates: VERSION (0.1.9 → 0.2.0) and CHANGELOG.md
# → Does NOT bump: backend, frontend, worker, chatbot, polyphemus, sdk

# To bump ALL components + platform, specify them explicitly:
./.github/release backend --minor frontend --minor worker --minor chatbot --minor polyphemus --minor sdk --minor platform --minor
# → Updates: All component versions AND platform version
```

### 🎨 Release Patterns

#### 🌐 **Platform-Only Release**
Use when you want to create a platform version that references existing component versions:
```bash
./.github/release platform --minor
# → Creates release/v0.2.0
# → References current component versions in platform changelog
```

#### 🔄 **Full Coordinated Release**
Use when all components should be updated together:
```bash
./.github/release backend --minor frontend --minor worker --minor chatbot --minor polyphemus --minor sdk --minor platform --minor
# → Creates release/v0.2.0
# → Updates ALL component versions + platform version
```

#### 🎯 **Mixed Release (with Platform)**
Use when specific components and platform need updates:
```bash
./.github/release backend --major sdk --minor platform --major
# → Creates release/v1.0.0
# → Updates backend, sdk, and platform versions
```

#### 📦 **Component-Only Release**
Use when only specific components need updates (no platform bump):
```bash
./.github/release backend --major sdk --minor
# → Creates release/multi-a1b2c3
# → Updates ONLY backend and SDK, platform version unchanged
```

### 🎯 When to Use Platform Releases

- 🎖️ **Major milestones**: Stable, tested combinations of all components
- 🚀 **Coordinated deployments**: When all components need to be updated together
- 👥 **Customer releases**: Providing vetted, "known-good" configurations
- 📚 **Documentation**: Clear versioning for external users

### 🔄 Platform Release Process

1. 📦 **Component Updates**: Only updates explicitly specified components
2. 🌐 **Platform Version**: Updates VERSION file and main CHANGELOG.md
3. 📝 **Unified Changelog**: Summarizes changes from updated components
4. 🔗 **Cross-references**: Links to individual component changelogs

## 💡 Release Examples

### 🐛 Scenario 1: Bug Fix Release

```bash
# Fix critical bug in backend only
./.github/release backend --patch
# → Creates branch: release/backend-v0.1.10
```

### ✨ Scenario 2: Feature Release

```bash
# New features in multiple components
./.github/release backend --minor frontend --minor sdk --minor
# → Creates branch: release/multi-v0.2.0
```

### 🎯 Scenario 3: Coordinated Platform Release

```bash
# Major platform milestone with all components
./.github/release \
  backend --minor \
  frontend --minor \
  worker --minor \
  chatbot --minor \
  polyphemus --minor \
  sdk --minor \
  platform --minor
# → Creates branch: release/v0.2.0
```

### 🌐 Scenario 3b: Platform-Only Release

```bash
# Platform milestone without component updates
./.github/release platform --minor
# → Creates branch: release/v0.2.0
# → Updates only platform version, references existing component versions
```

### 🎨 Scenario 4: Mixed Component Updates (with Platform)

```bash
# Different teams, different changes + platform update
./.github/release \
  backend --major \    # Breaking API changes
  frontend --patch \   # UI bug fixes
  sdk --minor \        # New utility functions
  platform --major     # Overall breaking changes
# → Creates branch: release/v1.0.0
```

### 📦 Scenario 5: Component-Only Updates (No Platform)

```bash
# Update specific components without bumping platform
./.github/release backend --major frontend --patch sdk --minor
# → Creates branch: release/multi-a1b2c3
# → Updates only specified components, platform version unchanged
```

## 🌳 Automatic Branch Creation

### ⚙️ How It Works

The release tool automatically creates appropriately named release branches based on the components and versions being released:

#### 📦 Single Component Releases
```bash
./.github/release backend --minor       # → release/backend-v0.2.0
./.github/release frontend --patch      # → release/frontend-v0.1.1  
./.github/release sdk --major          # → release/sdk-v1.0.0
```

#### 🔗 Multiple Component Releases
```bash
./.github/release backend --minor frontend --minor  # → release/multi-v0.2.0 (same version, no platform)
./.github/release backend --minor frontend --patch  # → release/multi-a1b2c3 (different versions, no platform)
```

#### 🌐 Platform Releases
```bash
./.github/release platform --minor      # → release/v0.2.0 (platform only)
./.github/release platform --major      # → release/v1.0.0 (platform only)

# Full platform release (all components + platform)
./.github/release backend --minor frontend --minor worker --minor chatbot --minor polyphemus --minor sdk --minor platform --minor
# → release/v0.2.0
```

### 🧠 Branch Naming Logic

The script automatically determines the appropriate branch name:

1. 📦 **Single component**: `release/{component}-v{new_version}`
2. 🌐 **Platform release**: `release/v{platform_version}` 
3. 🔗 **Multiple components, same version**: `release/multi-v{version}`
4. 🎯 **Multiple components, different versions**: `release/multi-{hash}`

### 🎛️ Manual Branch Control

If you prefer to manage branches manually:

```bash
# Create your own branch first
git checkout -b release/my-custom-name

# Then use --no-branch flag
./.github/release --no-branch backend --minor
```

### 🎉 Benefits

✅ **Zero manual work**: No need to predict versions or create branches  
✅ **Consistent naming**: Always follows the same pattern  
✅ **Descriptive branches**: Clear what's being released  
✅ **Git history**: Easy to understand in branch lists  

## 🔧 Prerequisites

### 🛠️ Required Tools

- 📂 **Git repository** with proper branch setup
- 🐍 **Python 3** with TOML library support
- 🔧 **jq** for JSON processing: `sudo apt install jq` or `brew install jq`

### 🐍 Python Environment

The script automatically detects and uses the best available Python environment:

1. 🎯 **SDK virtual environment** (recommended) - automatically detected
2. 🌍 **Global Python** with required libraries
3. ⚡ **Auto-installation** via uv (if available)

### 🔑 API Key for Enhanced Changelogs

For LLM-powered changelog generation, configure your Gemini API key using any of these methods:

#### 📄 Option 1: .env File (Recommended)

```bash
echo "GEMINI_API_KEY=your_api_key_here" >> .env
```

#### 🌍 Option 2: Environment Variable

```bash
export GEMINI_API_KEY=your_api_key_here
```

#### 📁 Option 3: Config File

```bash
mkdir -p ~/.config
echo "your_api_key_here" > ~/.config/gemini-api-key
```

#### ⌨️ Option 4: Command Line

```bash
./.github/release --gemini-key your_api_key_here backend --minor
```

## ⚙️ Configuration

### 📦 Component Configuration

Components are automatically detected based on their configuration files:

- 🐍 **Python projects**: `pyproject.toml` with `[project]` section
- 📦 **Node.js projects**: `package.json` with `version` field
- 📄 **Requirements-based**: `requirements.txt` (version tracked via git tags only)

### 🏷️ Tagging Strategy

The release tool uses a component-specific tagging strategy:

- 📦 **Component tags**: `{component}-v{version}` (e.g., `backend-v1.2.0`)
- 🌐 **Platform tags**: `v{version}` (e.g., `v1.0.0`)

### 📝 Changelog Format

All changelogs follow the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format with:

- 🔗 **Semantic versioning** links
- 📋 **Categories**: Added, Changed, Fixed, Removed, etc.
- ✨ **Professional formatting** via LLM or structured fallback

## 🔬 Advanced Usage

### ⌨️ Command Line Options

```bash
./.github/release [OPTIONS] [COMPONENT --VERSION_TYPE ...]

Options:
  --dry-run              Show what would be done without making changes
  --no-branch            Skip automatic release branch creation
  --gemini-key KEY       Gemini API key for changelog generation
  --help                 Show help message

Components:
  backend, frontend, worker, chatbot, polyphemus, sdk, platform

Version Types:
  --patch, --minor, --major
```

### 🧠 Environment Detection

The release tool automatically:

1. 📁 **Finds repository root** by locating `.git` directory
2. 🐍 **Activates SDK environment** if available (includes required TOML libraries)
3. ✅ **Validates prerequisites** before making any changes
4. 🛡️ **Sets up temporary directories** for safe operations

### 📝 Changelog Generation

#### 🤖 LLM-Powered (with Gemini API)

- ✨ **Professional formatting** with proper categorization
- 👥 **User-facing focus** highlighting important changes
- 📋 **Structured output** following Keep a Changelog format

#### 🔄 Fallback Mode (without API key)

- 📝 **Commit-based entries** with author and hash information
- ⏰ **Chronological listing** of all changes
- 📋 **Basic categorization** under "Changed" section

## ✨ Best Practices

### 📋 Release Planning

1. 👀 **Use dry run** always before actual release
2. 🧪 **Test locally** before pushing tags
3. 🤝 **Coordinate team** for platform releases
4. 📝 **Document breaking changes** clearly

### 🎯 Version Strategy

- 🐛 **Patch**: Bug fixes, security updates, documentation
- ✨ **Minor**: New features, enhancements, non-breaking changes
- 💥 **Major**: Breaking changes, architectural updates, API changes

### 🔄 Release Workflow

1. 🔑 **Setup API key** for enhanced changelogs (one-time setup)
2. 👀 **Run dry run** to preview changes
3. 🚀 **Execute release** command (automatically creates branch, updates versions and changelogs)
4. 👁️ **Review changes** (git status, git diff)
5. 📝 **Create PR** with version updates
6. 🏷️ **After PR merge**, create tags and GitHub releases using separate tooling

### 🎯 Example Complete Workflow

```bash
# Step 1: Setup Gemini API key (one-time setup)
echo "GEMINI_API_KEY=your_api_key_here" >> .env

# Step 2: Preview the release
./.github/release --dry-run backend --minor frontend --patch

# Step 3: Execute the release (automatically creates branch, updates versions and changelogs)
./.github/release backend --minor frontend --patch
# → Creates branch: release/backend-v0.2.0-frontend-v0.1.1

# Step 4: Review generated changes
git status
git diff

# Step 5: Create PR with version updates
git add .
git commit -m "Prepare release: backend v0.2.0, frontend v0.1.1"
git push origin $(git branch --show-current)
./.github/create-pr.sh

# Step 6: After PR is merged, create tags manually or with separate tooling
git checkout main && git pull
git tag -a backend-v0.2.0 -m "Release backend version 0.2.0"
git tag -a frontend-v0.1.1 -m "Release frontend version 0.1.1"
git push --tags

# Step 7: Create GitHub releases
gh release create backend-v0.2.0 --generate-notes
gh release create frontend-v0.1.1 --generate-notes
```

## 🔍 Troubleshooting

### ⚠️ Common Issues

#### 🐍 Missing TOML Library

```bash
# Error: No TOML library available
# Solution: Install using SDK environment
cd sdk && uv add tomli tomli-w

# Or install globally
pip3 install tomli tomli-w
```

#### 📂 Git Repository Issues

```bash
# Error: Not in a git repository
# Solution: Run from repository root
cd /path/to/rhesis

# Error: Uncommitted changes
# Solution: Commit or stash changes first
git add . && git commit -m "Pre-release commit"
```

#### 🔑 API Key Issues

```bash
# Warning: No Gemini API key provided
# Solution: Add to .env file
echo "GEMINI_API_KEY=your_key" >> .env
```

#### 🏷️ Tag Conflicts

```bash
# Error: Tag already exists
# Solution: Use different version or delete existing tag
git tag -d backend-v1.0.0  # Delete local tag
git push origin :refs/tags/backend-v1.0.0  # Delete remote tag
```

### 🆘 Getting Help

1. 🔧 **Check prerequisites** - ensure all tools are installed
2. 👀 **Use dry run** - preview what will happen
3. 📝 **Check logs** - review error messages carefully
4. ✅ **Verify environment** - ensure correct Python environment
5. 🧪 **Test manually** - try git commands individually if needed

### 🐛 Debug Mode

For detailed debugging, you can trace the release process:

```bash
# Enable verbose git output
GIT_TRACE=1 ./.github/release --dry-run backend --patch

# Check what the script is doing
bash -x ./.github/release --help
```

## 💬 Support

For issues with the release tool:

1. 📖 Check this guide first
2. 👁️ Review error messages carefully  
3. 🧪 Try with `--dry-run` to isolate issues
4. 📊 Check repository status with `git status`
5. 🤝 Consult the team for platform-wide releases

---

**📌 Note**: This release tool only updates versions and changelogs - it does NOT create git tags. This ensures a clean PR-first workflow where version changes are reviewed before any tagging occurs. Create tags manually or with separate tooling after PR merge. 🚀 