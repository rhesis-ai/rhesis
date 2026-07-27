---
name: python-linting
description: Runs Ruff linting and formatting on Python files. Use only before pushing changes (e.g. before git push or creating a PR).
---

# Python Linting (Ruff)


## Workflow

### 1. Check for linting issues
```bash
uvx ruff check <path/to/file.py>
```

### 2. Auto-format the code
```bash
uvx ruff format <path/to/file.py>
```

### 3. Check again to verify
```bash
uvx ruff check <path/to/file.py>
```

### 4. Fix remaining issues
Review any issues not fixed by the auto-formatter and fix them manually.

## When to apply

- **Only** before pushing (e.g. before `git push` or creating a pull request)
