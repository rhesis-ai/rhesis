# Rhesis Project Rules

Read natively by Cursor and imported by Claude Code (`CLAUDE.md` → `@AGENTS.md`). This file holds
rules that apply repo-wide. Each area has its own `AGENTS.md` for rules scoped to it, pulled in
automatically when you read files there via a sibling `CLAUDE.md`:

- `apps/backend/AGENTS.md` — ambient request scope, usage attribution, feature gating
- `apps/frontend/AGENTS.md` — affordances, BFF auth, TypeScript/ESLint conventions
- `sdk/AGENTS.md` — imports, test invocation
- `docs/AGENTS.md` — docs writing rules, Nextra/MDX mechanics
- `skills/rhesis/AGENTS.md` — the published public skill (everything there ships to users)

## Answering

Write answers in simple, plain language. Short sentences, everyday words. Say what you did and what
it means — skip the buildup.

Technical terms are fine when they're the real name for something: codebase names
(`bind_scope_to_session`, test set, affordances), everyday dev words (endpoint, migration, fixture,
race condition), and framework/infra terms (GUC, RLS policy, `ContextVar`, Celery worker). Avoid
abstract engineering-speak that carries no information — "leverage the abstraction", "surface area",
"idiomatic", "orthogonal concerns", "non-trivial", "first-class citizen".

## Code Comments

Keep comments concise — usually one line, and only where the code can't say it itself: a non-obvious
"why", or a real trap. Multi-line is fine when the thing is genuinely complex or hard to follow, but
not for ordinary code. Never restate what the next line does.

## Technology Stack

Backend and Python SDK: Python 3.12+, `uv` with `pyproject.toml`, Pydantic 2.x, pytest.

### Python imports

**Always absolute, never relative.** Write the full dotted path, including for a module's own
siblings and inside a package's own `__init__.py`:

```python
from rhesis.backend.app.services.explorer.utils import build_test_tree  # yes
from .utils import build_test_tree  # no
from ..database import get_db  # no
```

Existing relative imports are being converted as the files around them are touched.

## Local Development

- Always use `uv` to manage Python projects; run `uv` commands from the project root (`sdk/`,
  `apps/backend/`). Use `uv add <package>` to install deps, `uv run <script>` to run scripts.
- Use GitHub CLI (`gh`) whenever possible. If a GitHub link is pasted, open it with `gh`.
- Every dev port is defined in `scripts/rh/ports.sh`. A worktree runs on its own block of them:
  `./rh worktree <name>` writes `RHESIS_PORT_OFFSET` and `RHESIS_WORKTREE_NAME` to `.rhesis-ports`
  at the worktree root, and `./rh dev *` reads it from there. So don't assume 8080/3000 — run
  `./rh dev status` to see this checkout's ports, containers and offset.

## Worktrees

Every worktree must come from `./rh worktree`, never from a bare `git worktree add`. Only
`./rh worktree` symlinks `playground/`, `simulations/` and `domain.local/` back to the main
checkout, so notes written there survive the worktree being removed — they're gitignored, so
nothing else preserves them. It also gives the worktree its own dev ports and container names; a
worktree without `.rhesis-ports` shares the main checkout's stack, and `./rh dev clean` in one
would delete main's dev database.

A worktree that already exists without that setup isn't stuck — run `./rh worktree --init` from
inside it.

The `WorktreeCreate` hook in `.claude/settings.json` handles this for you. It replaces Claude Code's
git logic everywhere worktrees are created — `--worktree`, `isolation: worktree` subagents,
background sessions, and the `EnterWorktree` tool — so **call `EnterWorktree` with a `name`
normally** and it routes through `./rh worktree`. Don't pass `EnterWorktree` a path to work around
it: paths under `~/worktrees/rhesis/` are only accepted from the main checkout, not from a session
that's already in a worktree.

Port blocks run out after 20 concurrent worktrees, so remove yours when done:

```bash
./rh worktree <name> --remove
```

## Testing

Tests live under `tests/` — `backend/`, `sdk/`, `frontend/`, plus `k6/`, `load/`, `notifications/`,
`penelope/`, `polyphemus/`, `release_tools/` — never next to source.

Each suite has different working-directory and Docker requirements. Backend: invoke the
`backend-testing` skill. SDK: see `sdk/AGENTS.md`.

## Git Commits

- **Never commit, push, or open a PR without asking first.** Show what changed, then wait for the
  user to say go. An approved plan that mentions commits is not the confirmation — ask again when
  the code is actually ready. This includes every follow-up commit on a branch or PR that's already
  open — a prior push is not standing approval for the next one, even a small fix.
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

## Updating a Branch

- **Rebase a feature branch onto `main`; don't merge `main` into it:**
  `git fetch origin && git rebase origin/main`. Merging leaves a merge commit and interleaves
  unrelated `main` changes into the branch's history, which makes the PR diff noisy and stops the
  branch's own commits from reading as a clean sequence.
- On conflicts: fix the files, `git add <file>`, then `git rebase --continue`. `git rebase --abort`
  puts the branch back the way it was.
- A rebase rewrites history, so pushing an already-pushed branch needs
  `git push --force-with-lease` — it refuses to overwrite commits someone else pushed, which plain
  `--force` will do. On a branch someone else is working on, tell them before you force-push.
- **Never force-push `main`.**

## Task-specific workflows

Opening a pull request, filing a GitHub issue, writing playground scripts, linting Python, and
running `./rh worktree` each have their own skill — invoke `pull-request`, `github-issue`,
`playground-script`, `python-linting`, or `worktree` when doing that task.
