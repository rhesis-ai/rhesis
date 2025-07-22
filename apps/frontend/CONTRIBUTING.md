# Contributing to Rhesis Frontend

Thank you for your interest in contributing to the Rhesis frontend! This document provides guidelines and instructions to help you contribute effectively.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style and Standards](#code-style-and-standards)
- [Component Guidelines](#component-guidelines)
- [State Management](#state-management)
- [Testing](#testing)
- [Performance Considerations](#performance-considerations)
- [Accessibility](#accessibility)
- [Pull Request Process](#pull-request-process)
- [Documentation](#documentation)

## Code of Conduct

Please read and follow our [Code of Conduct](../../CODE_OF_CONDUCT.md) to maintain a respectful and inclusive environment for everyone.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/rhesis.git
   cd rhesis
   ```
3. **Set up the upstream remote**:
   ```bash
   git remote add upstream https://github.com/rhesis-ai/rhesis.git
   ```
4. **Navigate to frontend directory and install dependencies**:
   ```bash
   cd apps/frontend
   npm install
   ```
5. **Set up environment variables**:
   ```bash
   cp .env.example .env.local
   ```
   Fill in the necessary values in `.env.local`

6. **Start the development server** (choose one method):

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

## RH CLI Tool

The repository includes a unified CLI tool for managing development servers:

```bash
./rh frontend start   # Start the frontend server
./rh backend start    # Start the backend server
./rh help            # Show available commands
```

Run these commands from the repository root. The CLI provides a consistent interface for starting both services with beautiful, colorful output and proper error handling.

## Development Workflow

1. **Create a new branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
   or
   ```bash
   git checkout -b fix/issue-you-are-fixing
   ```

2. **Make your changes** and commit them with descriptive messages:
   ```bash
   git commit -m "feat: add new component for test visualization"
   ```

3. **Follow commit message conventions**:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `style:` for formatting changes
   - `refactor:` for code refactoring
   - `test:` for adding tests
   - `chore:` for maintenance tasks

4. **Keep your branch updated** with the upstream main branch:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

5. **Push your changes** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a pull request** from your fork to the main repository

## Code Style and Standards

We use ESLint and TypeScript for code quality and consistency:

- Run linting: `npm run lint`
- Run type checking: `npm run type-check`

Key principles:

- Use TypeScript for type safety
- Follow functional component patterns with hooks
- Use explicit return types for functions
- Prefer named exports over default exports
- Use destructuring for props
- Keep components focused and single-purpose
- Use proper semantic HTML elements

## Component Guidelines

### Component Structure

```tsx
// MyComponent.tsx
import * as React from 'react';
import { Box, Typography } from '@mui/material';
import { type MyComponentProps } from './types';

export function MyComponent({ 
  title, 
  description, 
  children 
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

### Best Practices

- Create smaller, reusable components
- Keep components under 200 lines of code
- Use proper prop typing with TypeScript interfaces
- Separate business logic from UI components
- Use React.memo() for performance optimization when appropriate
- Avoid inline styles; use MUI's styling system instead
- Extract complex logic into custom hooks

## State Management

- Use React Context API for global state
- Keep state as local as possible
- Use React Query for server state management
- Consider using reducers for complex state logic
- Avoid prop drilling by using context or composition

## Testing

We encourage writing tests for your components:

- Unit tests for utilities and hooks
- Component tests for UI components
- Integration tests for complex interactions

Run tests with:
```bash
npm run test
```

## Performance Considerations

- Use React.memo() for components that render often but rarely change
- Implement virtualization for long lists using react-window or similar
- Optimize images and assets
- Use Next.js dynamic imports for code splitting
- Implement proper memoization with useMemo and useCallback
- Monitor bundle size with built-in Next.js analytics

## Accessibility

All components should be accessible:

- Use semantic HTML elements
- Include proper ARIA attributes when necessary
- Ensure keyboard navigation works
- Maintain sufficient color contrast
- Test with screen readers
- Support reduced motion preferences

## Pull Request Process

1. Ensure your code passes all tests and linting
2. Update documentation if needed
3. Include screenshots for UI changes
4. Link to any related issues
5. Request review from at least one maintainer
6. Address review comments promptly

## Documentation

- Add JSDoc comments to functions and components
- Update README.md if you add new features or dependencies
- Document complex logic with inline comments
- Create or update Storybook stories for UI components

---

Thank you for contributing to Rhesis! If you have any questions, feel free to reach out to the maintainers or ask in our Discord community. 