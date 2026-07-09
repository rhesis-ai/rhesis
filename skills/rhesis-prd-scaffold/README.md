# Rhesis PRD Scaffold Skill

Turn a PRD or requirements document into fine-grained **behaviors**, **custom metrics**, **tags**, and **generated test sets** on the Rhesis platform.

Complements the main [`rhesis`](../rhesis) skill — use this one when requirements drive the design; use `rhesis` for endpoint exploration, test execution, and result analysis.

## Install

```bash
# Install both skills (recommended for demos)
npx skills add rhesis-ai/rhesis -g
# Copy or symlink this skill to your skills directory, e.g.:
# ~/.cursor/skills/rhesis-prd-scaffold/
```

Requires the Rhesis MCP server — see [`rhesis/README.md`](../rhesis/README.md#connect-the-mcp-server).

## Usage

Paste a PRD and invoke the skill:

```
/rhesis-prd-scaffold

Here is our agent PRD:
[paste requirements]
```

The agent will extract behaviors, propose metrics and tags, plan test sets, wait for approval, then create everything via MCP.

## What's included

| File | Purpose |
|------|---------|
| `SKILL.md` | PRD → behaviors/metrics/tags/test sets workflow |
| `references/behavior-design.md` | Fine-grained behavior rules and anti-patterns |
