# Rhesis PRD Scaffold Skill

Turn **your PRD or requirements** into a **test foundation** on Rhesis — fine-grained behaviors, custom metrics, tags, and generated test sets — using the Rhesis MCP server from Cursor, Claude Code, or any compatible agent.

Everything created lives in **your Rhesis organization** — reusable and refinable, not a one-off.

Complements the main [`rhesis`](../rhesis) skill:
- **`rhesis-prd-scaffold`** — requirements → test foundation
- **`rhesis`** — endpoint exploration, execution, result analysis

## What you get

| Asset | Purpose |
|---|---|
| **Behaviors** | Fine-grained expectations from your PRD — not generic quality labels |
| **Custom metrics** | Judge-as-model evaluators tuned to each behavior |
| **Tags** | Organize by theme (functional, safety, compliance, etc.) |
| **Test sets** | Generated prompts targeting your behaviors, ready to run |
| **Mappings** | Each behavior linked to the metric that scores it |

Iterate over time (add behaviors, tighten metrics, regenerate tests) and run against your endpoint via the `rhesis` skill.

## How it works

1. **You provide requirements** — paste or attach your PRD
2. **Agent reads and extracts** — capabilities, guardrails, quality bars, out-of-scope rules
3. **Agent proposes a plan** — behaviors, metrics, tags, test sets; reuses what you already have on Rhesis
4. **You approve** — nothing is created until you confirm
5. **Agent creates via MCP** — behaviors → metrics → links → tags → test sets
6. **Agent verifies** — counts match the plan, spot-checks generated tests, summarizes with links

## What it's good at

- **PRD → specific behaviors** — splits broad requirements ("handle flights and hotels") into testable pieces
- **Avoiding vague behaviors** — no umbrella names like "Reliability" or "Robustness"
- **Metrics that match the PRD** — guardrails get pass/fail categories; quality gets scored metrics
- **Tags for organization** — consistent taxonomy from your requirements
- **Test generation aligned to requirements** — jailbreaks, off-topic asks, refusals where your PRD calls for them

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

Explicit invocation is required — the skill creates platform entities via MCP and waits for your approval before writing anything.

## What's included

| File | Purpose |
|------|---------|
| `SKILL.md` | PRD → test foundation workflow |
| `references/behavior-design.md` | Fine-grained behavior rules and anti-patterns |
