# Rhesis Project Rules

Read natively by Cursor and imported by Claude Code (`CLAUDE.md` → `@AGENTS.md`). This file holds
rules that apply repo-wide. Scoped rules live in each area's own `AGENTS.md`:
`apps/backend/AGENTS.md`, `apps/frontend/AGENTS.md`, `sdk/AGENTS.md`, `docs/AGENTS.md`.

## Technology Stack

Backend and Python SDK: Python 3.10+, `uv` with `pyproject.toml`, Pydantic 2.x, pytest.

## Local Development

- Always use `uv` to manage Python projects; run `uv` commands from the project root (`sdk/`,
  `apps/backend/`). Use `uv add <package>` to install deps, `uv run <script>` to run scripts.
- Use GitHub CLI (`gh`) whenever possible. If a GitHub link is pasted, open it with `gh`.

## Python Code Quality (Ruff)

Run ruff **only before pushing** (before `git push` or opening a PR), not after every file change:

```bash
uvx ruff check <path/to/file.py>
uvx ruff format <path/to/file.py>
uvx ruff check <path/to/file.py>   # verify
```

Max line length: 100 characters. Fix E501 by breaking long strings/f-strings/function calls across
lines.

## Testing

Tests live in `tests/backend/` and `tests/sdk/`, not next to source. See `apps/backend/AGENTS.md`
and `sdk/AGENTS.md` for exact invocation commands (backend and SDK have different working-directory
requirements).

## Git Commits

- **Never commit on `main`.** Check `git branch --show-current` first; if on `main`, create a
  branch before committing: `git fetch origin && git checkout main && git pull origin main &&
git checkout -b feature/short-description`.
- Stage changes selectively (`git add <file>` or `git add -p`), not `git add .`/`git add -A`.
- Group commits by logical change (feature, fix, refactor, docs, config, test) — don't mix them.
- Follow Conventional Commits: `<type>[optional scope]: <description>`
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
  - Scope: use only `backend`, `frontend`, `sdk`, `tests`, or `dev` — don't invent new scopes
  - Lowercase type/description, imperative mood, no trailing period, ≤50 chars
  - `BREAKING CHANGE:` in the footer for breaking changes
  - Example: `fix(backend): resolve timeout issue in user endpoint`

## Pull Requests

- **Small PRs, one logical change each.** Ideal 1-200 lines, acceptable 200-400, break down 400+.
- Branch from latest `main`: `git fetch origin && git checkout main && git pull origin main &&
git checkout -b feature/your-feature-name`.
- Title: action verb first (Add/Fix/Update/Remove), under 72 characters.
- Description must include these sections:

  ```markdown
  ## Purpose

  [Explain why this change is needed]

  ## What Changed

  - [Key change 1]

  ## Additional Context

  - [Links to issues, tickets, breaking changes]

  ## Testing

  [How to test these changes]
  ```

## GitHub Issues

1. Use GitHub CLI (`gh issue create`) with the appropriate template (Bug, Feature, Task) from
   `.github/ISSUE_TEMPLATE`.
2. List labels with `gh label list` and pick from that list — don't add issue-type labels
   (bug/feature/task).
3. Keep issues short; trim template sections that don't apply.
4. Ask the user for confirmation before creating.

## Playground Scripts (`playground/`, when present)

Ad-hoc scripts for manual testing/prototyping — not part of the production codebase or automated
test suite. They import from the SDK, so run them from `sdk/`:

```bash
cd sdk && uv run python ../playground/<script_name>.py
```

Each script needs a top docstring (purpose, prerequisites, how to run). Hardcoded local URLs/keys
are fine. Never add these scripts to the automated test suite.
