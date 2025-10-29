# 🎨 Contributing to Rhesis Frontend

Thank you for your interest in contributing to the Rhesis frontend! 🚀 This document provides comprehensive guidelines and instructions to help you contribute effectively to our React application.

## 📋 Table of Contents

- 📜 [Code of Conduct](#code-of-conduct)
- 🟢 [Node.js Version Requirements](#nodejs-version-requirements)
- 🚀 [Getting Started](#getting-started)
- 🔒 [Environment Security Notes](#environment-security-notes)
- 🔄 [Development Workflow](#development-workflow)
- 🎨 [Code Style and Standards](#code-style-and-standards)
- 🧩 [Component Guidelines](#component-guidelines)
- 🗂️ [State Management](#state-management)
- 🧪 [Testing](#testing)
- ⚡ [Performance Considerations](#performance-considerations)
- ♿ [Accessibility](#accessibility)
- 📝 [Pull Request Process](#pull-request-process)
- 📚 [Documentation](#documentation)

## 📜 Code of Conduct

Please read and follow our [Code of Conduct](../../CODE_OF_CONDUCT.md) to maintain a respectful and inclusive environment for everyone.

## 🟢 Node.js Version Requirements

The Rhesis frontend requires **Node.js v18.20.5**. If you encounter issues with your system's Node.js version, we recommend using [nvm](https://github.com/nvm-sh/nvm) to manage Node.js versions:

```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.4/install.sh | bash

# Reload your shell configuration (or restart your terminal)
source ~/.bashrc
# or for zsh users:
# source ~/.zshrc

# Install and use the required Node.js version
nvm install 18.20.5
nvm use 18.20.5

# Set as default (optional)
nvm alias default 18.20.5

# Verify the installation
node --version  # Should output v18.20.5
npm --version   # Should output the corresponding npm version
```

For macOS users, you can also install nvm via Homebrew:

```bash
# Alternative installation via Homebrew
brew install nvm

# Create NVM's working directory
mkdir ~/.nvm

# Add nvm to your shell profile (choose your shell)
# For zsh users (default on macOS):
echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.zshrc
echo '[ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"  # This loads nvm' >> ~/.zshrc
echo '[ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"  # This loads nvm bash_completion' >> ~/.zshrc

# For bash users:
# echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.bashrc
# echo '[ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"  # This loads nvm' >> ~/.bashrc
# echo '[ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"  # This loads nvm bash_completion' >> ~/.bashrc

# Reload your shell configuration
source ~/.zshrc
# or for bash users: source ~/.bashrc

# Verify nvm is installed
nvm --version

# Install the required Node.js version
nvm install 18.20.5
nvm use 18.20.5
```

This ensures you're using the exact Node.js version that the project is designed and tested with, avoiding potential compatibility issues.

## 🚀 Getting Started

1. ✅ **Ensure you have the correct Node.js version** (see [Node.js Version Requirements](#nodejs-version-requirements)):

   ```bash
   node --version  # Should output v18.20.5
   ```

   If you don't have the correct version, install it using nvm as described above.

2. 🍴 **Fork the repository** on GitHub

3. 📥 **Clone your fork** locally:

   ```bash
   git clone https://github.com/YOUR-USERNAME/rhesis.git
   cd rhesis
   ```

4. 🔗 **Set up the upstream remote**:

   ```bash
   git remote add upstream https://github.com/rhesis-ai/rhesis.git
   ```

5. 🛠️ **Install GitHub CLI** (required for automated PR creation):

   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install gh

   # macOS
   brew install gh

   # Or download from: https://cli.github.com/
   ```

6. 🔐 **Authenticate with GitHub**:

   ```bash
   gh auth login
   ```

7. 📦 **Navigate to frontend directory and install dependencies**:

   ```bash
   cd apps/frontend
   # Ensure you're using the correct Node.js version
   node --version  # Should be v18.20.5
   npm install
   ```

8. **Set up environment variables**:

   **Option A: Obtain from Google Cloud Secrets Manager (Recommended)**:

   ```bash
   # Authenticate with Google Cloud (if not already done)
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID

   # Retrieve the .env.local file from Secrets Manager
   gcloud secrets versions access latest --secret="env-frontend" > .env.local

   # Verify the file was created
   ls -la .env.local
   ```

   **Option B: Manual Configuration**:
   Create a `.env.local` file manually with the required environment variables. Contact the team or check the project documentation for the specific variables needed for your development environment.

   **Note**: Ensure your `.env.local` file is placed in the `apps/frontend/` directory and never commit it to version control.

9. **Environment Configuration Requirements**:

   **⚠️ Important**: Proper environment configuration is required for the frontend to connect to backend services and external APIs. The `.env.local` file contains essential configuration including API endpoints, authentication keys, and feature flags.

10. **Start the development server** (choose one method):

    **Option A: Use the unified CLI from repository root:**

```bash
./rh frontend start
```

**Option B: Use the frontend start script directly:**

```bash
cd apps/frontend
./start.sh
```

**Option C: Run manually:**

```bash
npm run dev --host
```

## 🔒 Environment Security Notes

- 🚫 **Never commit** the `.env.local` file to version control - it contains sensitive configuration
- 🔑 **Secrets Manager access** - Ensure you have appropriate permissions to access the `env-frontend` secret
- 📁 **Environment-specific files** - Use `.env.local` for local development, never share these files
- ☁️ **Google Cloud Prerequisites** - You'll need Google Cloud CLI installed and authenticated to retrieve secrets

## 🔧 RH CLI Tool

The repository includes a unified CLI tool for managing development servers:

```bash
./rh frontend start   # Start the frontend server
./rh backend start    # Start the backend server
./rh help            # Show available commands
```

Run these commands from the repository root. The CLI provides a consistent interface for starting both services with beautiful, colorful output and proper error handling.

## 🤖 Automated PR Creation Tool

The repository includes an intelligent PR creation tool that streamlines the pull request process:

```bash
.github/pr [base-branch] [options]
```

**🔍 Enhanced Features**
The tool now prevents common PR creation failures and handles updates:

- **Push Detection**: Detects unpushed branches and commits
- **Interactive Prompting**: Clear options to push content before PR creation
- **PR Updates**: Updates existing PRs instead of failing when PR already exists

**Features:**

- 🎯 **Smart title generation** - Automatically formats branch names into proper titles
- 📝 **Detailed descriptions** - Includes commit summaries, changed files, and checklists
- 🔤 **Proper capitalization** - Handles technical abbreviations (API, UI, DB, etc.)
- ✅ **Ready-to-use templates** - Pre-filled checklists and sections
- 🌐 **Browser integration** - Option to open PR in browser after creation
- 🛡️ **Push validation** - Ensures all content is pushed before PR creation
- 🚀 **Auto-push option** - Can push changes for you with confirmation

**Prerequisites:**

- GitHub CLI (`gh`) must be installed and authenticated (see setup steps above)
- Must be run from a feature branch (not main/master)

**Examples:**

```bash
.github/pr                  # Create PR against main branch (with push detection)
.github/pr develop         # Create PR against develop branch
.github/pr --force         # Skip push detection (advanced users)
.github/pr --help          # Show all available options
```

**Note:** If GitHub CLI is not installed, the tool will display an error and guide you to install it first.

## 🔄 Development Workflow

**📋 Prerequisites**: Before starting development, ensure you have completed the environment configuration by obtaining your `.env.local` file from Google Cloud Secrets Manager or configuring it manually.

1. 🌿 **Create a new branch** for your feature or bugfix:

   ```bash
   git checkout -b feature/your-feature-name
   ```

   or

   ```bash
   git checkout -b fix/issue-you-are-fixing
   ```

2. ✍️ **Make your changes** and commit them with descriptive messages:

   ```bash
   git commit -m "feat: add new component for test visualization"
   ```

3. 📝 **Follow commit message conventions**:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `style:` for formatting changes
   - `refactor:` for code refactoring
   - `test:` for adding tests
   - `chore:` for maintenance tasks

4. 🔄 **Keep your branch updated** with the upstream main branch:

   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

5. 📤 **Push your changes** to your fork:

   ```bash
   git push origin feature/your-feature-name
   ```

6. 🔗 **Create a pull request** using the automated PR tool:

   ```bash
   .github/pr
   ```

   This tool will:
   - 🔍 **Check if your changes are pushed** to remote
   - 🤝 **Prompt you to push** if needed (with option to push automatically)
   - 📝 **Generate a professional PR** with proper title formatting, detailed description, commit summaries, and comprehensive checklist

7. **Submit the pull request** from your fork to the main repository

## 🎨 Code Style and Standards

We use ESLint and TypeScript for code quality and consistency:

- 🔍 Run linting: `npm run lint`
- 🔧 Run type checking: `npm run type-check`

Key principles:

- 🛡️ Use TypeScript for type safety
- 🪝 Follow functional component patterns with hooks
- 📝 Use explicit return types for functions
- 📤 Prefer named exports over default exports
- 🔄 Use destructuring for props
- 🎯 Keep components focused and single-purpose
- 🏷️ Use proper semantic HTML elements

## 🧩 Component Guidelines

### Component Structure

```tsx
// MyComponent.tsx
import * as React from 'react';
import { Box, Typography } from '@mui/material';
import { type MyComponentProps } from './types';

export function MyComponent({
  title,
  description,
  children,
}: MyComponentProps): React.ReactElement {
  // Component logic here

  return (
    <Box>
      <Typography variant="h2">{title}</Typography>
      {description && <Typography>{description}</Typography>}
      {children}
    </Box>
  );
}
```

### ✨ Best Practices

- 🧱 Create smaller, reusable components
- 📏 Keep components under 200 lines of code
- 🏷️ Use proper prop typing with TypeScript interfaces
- 🔀 Separate business logic from UI components
- ⚡ Use React.memo() for performance optimization when appropriate
- 🎨 Avoid inline styles; use MUI's styling system instead
- 🪝 Extract complex logic into custom hooks

## 🗂️ State Management

- 🌐 Use React Context API for global state
- 📍 Keep state as local as possible
- 🔄 Use React Query for server state management
- 🧮 Consider using reducers for complex state logic
- 🚫 Avoid prop drilling by using context or composition

## 🧪 Testing

We encourage writing tests for your components:

- 🔧 Unit tests for utilities and hooks
- 🧩 Component tests for UI components
- 🔗 Integration tests for complex interactions

Run tests with:

```bash
npm run test
```

## ⚡ Performance Considerations

- 🎭 Use React.memo() for components that render often but rarely change
- 📜 Implement virtualization for long lists using react-window or similar
- 🖼️ Optimize images and assets
- 📦 Use Next.js dynamic imports for code splitting
- 🧠 Implement proper memoization with useMemo and useCallback
- 📊 Monitor bundle size with built-in Next.js analytics

## ♿ Accessibility

All components should be accessible:

- 🏷️ Use semantic HTML elements
- 🎯 Include proper ARIA attributes when necessary
- ⌨️ Ensure keyboard navigation works
- 🎨 Maintain sufficient color contrast
- 🔊 Test with screen readers
- 🎬 Support reduced motion preferences

## 📝 Pull Request Process

1. ✅ Ensure your code passes all tests and linting
2. 📚 Update documentation if needed
3. 🤖 **Use the automated PR tool** (`.github/pr`) for consistent PR formatting
4. 📸 Include screenshots for UI changes
5. 🔗 Link to any related issues
6. 👥 Request review from at least one maintainer
7. 💬 Address review comments promptly

## 📚 Documentation

- 💬 Add JSDoc comments to functions and components
- 📝 Update README.md if you add new features or dependencies
- 🧠 Document complex logic with inline comments
- 📖 Create or update Storybook stories for UI components

---

Thank you for contributing to Rhesis! If you have any questions, feel free to reach out to the maintainers or ask in our Discord community.
