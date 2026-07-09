# Rhesis PRD Scaffold Skill

Turn a PRD or requirements document into fine-grained **behaviors**, **custom metrics**, **tags**, and **generated test sets** on the Rhesis platform.

Complements the main [`rhesis`](../rhesis) skill — use this one when requirements drive the design; use `rhesis` for endpoint exploration, test execution, and result analysis.

## Install

Install **both** skills for the full demo workflow:

```bash
# Main Rhesis platform skill
npx skills add rhesis-ai/rhesis -g

# PRD scaffold skill — symlink from this repo until bundled in the installer
ln -s "$(pwd)/skills/rhesis-prd-scaffold" ~/.cursor/skills/rhesis-prd-scaffold
```

Requires the Rhesis MCP server — see [`rhesis/README.md`](../rhesis/README.md#connect-the-mcp-server).

## Usage

This skill requires **explicit invocation** — it does not auto-activate when you paste a PRD.

```
/rhesis-prd-scaffold

Here is our agent PRD:
[paste requirements]
```

The agent will extract behaviors, propose metrics and tags, plan test sets, wait for approval, create everything via MCP, verify counts, and report with links.

## What's included

| File | Purpose |
|------|---------|
| `SKILL.md` | PRD → behaviors/metrics/tags/test sets workflow |
| `references/behavior-design.md` | Fine-grained behavior rules and anti-patterns |
