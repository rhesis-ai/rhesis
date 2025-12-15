# Rhesis Documentation

This directory contains documentation for the Rhesis platform. The full documentation is hosted at [docs.rhesis.ai](https://docs.rhesis.ai).

## Contents

- [Self-Hosting Guide](https://docs.rhesis.ai/getting-started/self-hosting): Complete guide for running Rhesis with Docker Compose
- [Environment Setup](https://docs.rhesis.ai/development/environment-setup): Local development environment setup
- [Backend](https://docs.rhesis.ai/development/backend): Documentation for the backend API and services
- [Frontend](https://docs.rhesis.ai/development/frontend): Documentation for the frontend application
- [SDK](https://docs.rhesis.ai/sdk): Documentation for the SDK libraries
- [Worker](https://docs.rhesis.ai/development/worker): Documentation for the background processing and task system

## Getting Started

### For Self-Hosted Deployment
If you want to run Rhesis in production or for evaluation, start with the [Self-Hosting Guide](https://docs.rhesis.ai/getting-started/self-hosting).

### For Development
If you're contributing to Rhesis or setting up a local development environment, see the [Environment Setup Guide](https://docs.rhesis.ai/development/environment-setup).

### For Integration
If you're building applications that integrate with Rhesis, check out the [SDK Documentation](https://docs.rhesis.ai/sdk).

## Local Development

To work on the documentation locally:

```bash
cd docs/src

# Install dependencies
make install

# Run development server
npm run dev

# Linting and formatting
make lint         # Run all checks (ESLint + Prettier)
make lint-fast    # Same as lint (no build needed)
make format       # Auto-fix formatting issues
make format-check # Check formatting only
make eslint       # Run ESLint only
```

The documentation site will be available at `http://localhost:3001`.

## Additional Resources

- [Full Documentation](https://docs.rhesis.ai)
- [Getting Started](https://docs.rhesis.ai/getting-started)
- [Platform Overview](https://docs.rhesis.ai/platform)
- [Development Guide](https://docs.rhesis.ai/development)

Please refer to [docs.rhesis.ai](https://docs.rhesis.ai) for the complete and up-to-date documentation. Each section has detailed information with guides, tutorials, and API references.
