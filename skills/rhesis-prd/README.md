# Rhesis PRD Skill

Turn **your PRD or requirements** into a **test foundation** on Rhesis — fine-grained behaviors, custom metrics, tags, and generated test sets — using the Rhesis MCP server from Cursor, Claude Code, or any compatible agent.

Everything created lives in **your Rhesis organization** — reusable and refinable, not a one-off.

Complements the main [`rhesis`](../rhesis) skill:
- **`rhesis-prd`** — requirements → test foundation
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

- **PRD → specific behaviors** — unpacks bundled user stories and policy bullets into independently testable expectations
- **Avoiding vague behaviors** — no section titles, NFR hand-waving, or umbrella names like "Reliability" or "Robustness"
- **Metrics from acceptance criteria** — binary gates, named states, counts, and limits in the PRD drive score type and pass rules
- **Tags for organization** — consistent taxonomy from your requirements
- **Test generation aligned to requirements** — jailbreaks, off-topic asks, refusals where your PRD calls for them

## Install

Install both skills for the full workflow (foundation + run/analyze):

```bash
# Platform operations (MCP tools, execution, analysis)
npx skills add rhesis-ai/rhesis -g

# PRD skill — symlink from this repo until bundled in the installer
ln -s "$(pwd)/skills/rhesis-prd" ~/.cursor/skills/rhesis-prd
```

Connect the Rhesis MCP server — see [`rhesis/README.md`](../rhesis/README.md#connect-the-mcp-server).

The `compatibility` field in `SKILL.md` frontmatter follows the [Agent Skills](https://agentskills.io/specification) open standard and is supported by Cursor.

## Usage

```
/rhesis-prd

Here is our agent PRD:
[paste your product requirements]
```

Explicit invocation is required — the skill creates platform entities via MCP and waits for your approval before writing anything.

## What's included

| File | Purpose |
|------|---------|
| `SKILL.md` | PRD → test foundation workflow |
| `references/prd-anatomy.md` | How real PRDs are structured (stakeholders, stories, FRs) |
| `references/behavior-design.md` | Splitting bundled PRD text into behaviors |
| `references/metric-design.md` | FR/AC-driven metrics: binary, categorical, numeric |
