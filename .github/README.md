# GitHub Automation Tools

This directory contains automation scripts and tools for GitHub workflows and repository management.

## 🚀 PR Creation Script

### `create-pr.sh`

An intelligent script that automates the creation of pull requests by analyzing your current branch and generating meaningful titles and descriptions.

#### Features

- ✅ **Automatic title generation** based on branch naming conventions
- ✅ **Rich PR descriptions** with commit details, file changes, and checklists
- ✅ **Smart branch detection** (feature/, fix/, hotfix/ prefixes)
- ✅ **Interactive browser opening** option
- ✅ **Error handling** and validation
- ✅ **Colorized output** for better UX

#### Usage

```bash
# Basic usage (compares current branch to main)
./.github/create-pr.sh

# Compare to a different base branch
./.github/create-pr.sh develop
```

#### Prerequisites

- [GitHub CLI (gh)](https://cli.github.com/) must be installed and authenticated
- Must be run from within a git repository
- Current branch must have commits that differ from the base branch

#### What it does

1. **Validates environment**: Checks for gh CLI and git repository
2. **Analyzes changes**: Gets commit history and file changes between branches
3. **Generates content**: Creates intelligent PR title and comprehensive description
4. **Creates PR**: Uses gh CLI to create the pull request
5. **Provides summary**: Shows PR details and optionally opens in browser

#### Branch Naming Conventions

The script intelligently handles different branch naming patterns:

- `feature/websocket-endpoint` → "Websocket Endpoint"
- `fix/authentication-bug` → "Fix: authentication bug"
- `hotfix/critical-security` → "Hotfix: critical security"
- `custom-branch-name` → "Custom Branch Name"

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

## 📁 Directory Structure

```
.github/
├── README.md           # This documentation
├── create-pr.sh        # PR automation script
├── workflows/          # GitHub Actions workflows
└── actions/            # Custom GitHub Actions
```

## 🛠 Contributing

When adding new automation tools:

1. Document the tool in this README
2. Include usage examples
3. Add error handling and validation
4. Use consistent styling and output formatting
5. Test thoroughly before committing

## 📚 Additional Resources

- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Git Best Practices](https://git-scm.com/book/en/v2) 