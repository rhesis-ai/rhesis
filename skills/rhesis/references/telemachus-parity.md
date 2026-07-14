# Telemachus (Architect) parity plan

The **Rhesis agent skill** and **Telemachus** (native Architect) share operational knowledge from `skills/rhesis/references/`. Telemachus includes those files at runtime via `prompt_loader.py`; the coding agent reads them via `SKILL.md` routing.

| | Agent skill | Telemachus |
|---|---|---|
| Instructions | `SKILL.md` + `references/` | `system_prompt.j2` includes same `references/` |
| Docs (canonical) | Links to `docs.rhesis.ai/llms.txt` | Same content in repo refs |
| Tools | MCP over HTTP | `LocalToolProvider` + `mcp_tools.yaml` |
| Write safety | Prompt + user approval | `save_plan`, Accept/Change UI, modes |

## Implemented on this branch

### Phase 1 — Telemachus references skills

- [x] `prompt_loader.py` — Jinja `ChoiceLoader` for `skills/rhesis/references/`
- [x] `system_prompt.j2` — slim shell + shared refs via includes
- [x] `telemachus-*.j2` — runtime-only partials
- [x] Four-path menu in `workflow-routing.j2`

### Lazy phase loading

- [x] Phase knowledge injected in `iteration_prompt.j2` per `mode` + `workflow_path`
- [x] Fixed system prompt: routing, entity model, resolution, security only
- [x] `workflow.py` — path inference from user message
- [x] `WorkflowPath` persisted in agent state snapshot

### Phase 2 — Docs as source of truth

- [x] `docs/agent-skill/for-agents.mdx`, `docs/metrics/metric-scope.mdx`
- [x] Terminology: [Glossary](/glossary) canonical; `definitions.md` confusions only
- [x] `llms.txt` — **For AI agents** section with machine-reading rules
- [x] Slim `SKILL.md` — router + docs URLs; `use-case-bracketfeld.md` stays in repo
- [x] Skill refs link to canonical docs URLs at top of key files

### metric_scope (critical)

- [x] `plan.py` — `MetricSpec.metric_scope` + `save_plan` coverage validation
- [x] `metric-scope.md` included in Telemachus prompt
- [x] `docs/architect/planning.mdx` + `docs/metrics/metric-scope.mdx`

## Remaining (optional)

- [ ] `PlanDisplay.tsx` — scope column on metrics
- [ ] `ArchitectWelcome.tsx` — four-path welcome chips
- [ ] Phase 3 (#2033) — generate `tool-catalog.md` from `mcp_tools.yaml`
- [ ] "Chat with docs" tool for Telemachus
