@AGENTS.md

## Scoped rules

Each area has its own `AGENTS.md` with rules specific to that part of the codebase, pulled in
automatically when you read files there via a sibling `CLAUDE.md`:

- `apps/backend/AGENTS.md` — ambient request scope, feature gating, codebase layout
- `apps/frontend/AGENTS.md` — affordances, TypeScript/ESLint conventions, codebase layout
- `sdk/AGENTS.md` — codebase layout, test invocation
- `docs/AGENTS.md` — Nextra/MDX rules
