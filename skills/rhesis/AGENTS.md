# Published Skill Rules

This directory is the **source** of the public Rhesis agent skill. It is mirrored to
[`rhesis-ai/skills`](https://github.com/rhesis-ai/skills) by `.github/workflows/sync-skill.yml`
on every push to `main` that touches `skills/rhesis/**`. See root `AGENTS.md` for repo-wide rules.

## What this means when you edit here

- **Everything you write ships publicly.** Treat this as customer-facing documentation, not
  internal notes.
- **Nothing outside this directory comes with it.** A relative link to `../../apps/backend/...`
  works locally and 404s for every user. `scripts/skill/validate.py` fails the PR on this.
- **Don't add plugin manifests.** `.claude-plugin/` and `.cursor-plugin/` are generated at sync
  time by `scripts/skill/build_mirror.py`. Edit that script to change them.
- **Don't add a `version` field anywhere.** Claude Code falls back to the source commit SHA, so
  users get an update on every sync. Adding a version pins them until someone bumps it by hand.

## Keeping the tool catalog honest

`references/tool-catalog.md` is hand-maintained against the MCP server's tool definitions in
`apps/backend/src/rhesis/backend/app/mcp_server/mcp_tools.yaml`. There is no generator and no
automated check — when you add, rename, or remove a tool there, update the catalog in the same PR.

## Checking your work

```bash
python scripts/skill/validate.py
python scripts/skill/build_mirror.py --out /tmp/skills-mirror   # preview what users receive
```
