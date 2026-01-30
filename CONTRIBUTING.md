# Contributing to Rhesis

Thank you for your interest in contributing to Rhesis! This guide will help you get started quickly.

## Quick Start

1. **Fork and clone the repository:**
```bash
git clone https://github.com/YOUR_USERNAME/rhesis.git
cd rhesis
```

2. **Set up local development environment:**
```bash
./rh dev init         # Initialize env files (one-time setup)
./rh dev up           # Start dev infrastructure (postgres + redis)
./rh dev backend      # Start backend server (auto-login enabled)
./rh dev frontend     # Start frontend server
```

3. **Access the application** at http://localhost:3000

Run `./rh help` to see all available commands.

## Component Guides

Each component has its own detailed contributing guide:

- [SDK Contributing Guide](sdk/CONTRIBUTING.md)
- [Backend Contributing Guide](apps/backend/CONTRIBUTING.md)
- [Frontend Contributing Guide](apps/frontend/CONTRIBUTING.md)

## Development Workflow

1. **Create a feature branch:**
```bash
git checkout -b feature/your-feature-name
```

2. **Enable pre-commit hooks:**
```bash
uvx pre-commit install
```

3. **Make your changes** and run checks:
```bash
make format && make lint && make test
```
> Run `make` commands from `apps/backend/` or `sdk/` directories.

4. **Commit your changes:**
```bash
git commit -m "feat: your descriptive commit message"
```

5. **Push and create a Pull Request:**
```bash
git push origin feature/your-feature-name
.github/pr
```

## Commit Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`

## Pull Request Checklist

- [ ] Code follows our coding standards
- [ ] Tests added/updated for changes
- [ ] Documentation updated if needed
- [ ] All CI checks pass

## Learn More

- [Development Setup](https://docs.rhesis.ai/development/contributing/development-setup) — Full environment setup guide
- [Coding Standards](https://docs.rhesis.ai/development/contributing/coding-standards) — Python and TypeScript standards
- [Release Process](RELEASING.md) — Versioning and release workflow

## Questions or Need Help?

- Check our [documentation](https://docs.rhesis.ai)
- Join our [Discord](https://discord.rhesis.ai)
- Create an [issue](https://github.com/rhesis-ai/rhesis/issues)
- Email us at support@rhesis.ai

---

## Legal Notice

By contributing to this project, you confirm that you have authored the content, have the necessary rights, and that your contribution may be provided under the project's [MIT License](LICENSE).

### Developer Certificate of Origin (DCO)

We encourage contributors to sign off on their commits to certify they have the right to submit their contributions under the project's open source license. We follow the [Developer Certificate of Origin (DCO)](https://developercertificate.org/) used by the Linux Foundation.

**Sign your commits** using the `-s` flag:

```bash
git commit -s -m "feat: add new feature"
```

This adds a `Signed-off-by` line to your commit:
```
Signed-off-by: Your Name <your.email@example.com>
```

Ensure your Git config matches:
```bash
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

---

Thank you for contributing to Rhesis!
