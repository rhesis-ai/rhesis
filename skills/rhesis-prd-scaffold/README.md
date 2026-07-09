# Rhesis PRD Scaffold Skill

Turn **your PRD or requirements** into a **test foundation** on Rhesis — fine-grained behaviors, custom metrics, tags, and generated test sets — using the Rhesis MCP server from Cursor, Claude Code, or any compatible agent.

Complements the main [`rhesis`](../rhesis) skill:
- **`rhesis-prd-scaffold`** — requirements → test foundation
- **`rhesis`** — endpoint exploration, execution, result analysis

## Install

Install both skills for the full workflow (foundation + run/analyze):

```bash
# Platform operations (MCP tools, execution, analysis)
npx skills add rhesis-ai/rhesis -g

# PRD → test foundation — symlink from this repo until bundled in the installer
ln -s "$(pwd)/skills/rhesis-prd-scaffold" ~/.cursor/skills/rhesis-prd-scaffold
```

Connect the Rhesis MCP server — see [`rhesis/README.md`](../rhesis/README.md#connect-the-mcp-server).

## Usage

```
/rhesis-prd-scaffold

Here is our agent PRD:
[paste your product requirements]
```

The agent extracts expectations from your PRD, proposes behaviors and custom metrics, plans tags and test sets, waits for your approval, then creates everything on your Rhesis organization via MCP.

You get a durable test foundation to run against your endpoint, iterate on, and extend as requirements change.

## What's included

| File | Purpose |
|------|---------|
| `SKILL.md` | PRD → test foundation workflow |
| `references/behavior-design.md` | Fine-grained behavior rules and anti-patterns |
