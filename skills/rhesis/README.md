# Rhesis Agent Skill

Design, run, and analyze AI test suites on the [Rhesis](https://rhesis.ai) platform — from within Claude Code, Cursor, Codex, or [any compatible AI interface](https://github.com/vercel-labs/skills#supported-agents).

This skill teaches your agent how to explore an AI endpoint's capabilities, design a test suite, create requirements and metrics, generate tests, execute them, and analyze the results. All platform operations run through the Rhesis MCP server.

**Skill layout:** `SKILL.md` is a thin router. Deep guidance lives under `references/` — start with `workflow-index.md`. Spec plans should match the fictional golden example in `use-case-bracketfeld.md` (City of Bracketfeld PermitDesk — not a real product).

> **Note:** This is different from Rhesis's inbound MCP connector (where the platform consumes tools like Notion or GitHub). Here, an external AI agent calls *into* Rhesis to drive the testing platform.

---

## Prerequisites

- A Rhesis account at [app.rhesis.ai](https://app.rhesis.ai) (or a self-hosted backend)
- An API token — generate one at [app.rhesis.ai/tokens](https://app.rhesis.ai/tokens)

---

## Install in Claude Code

The plugin carries both the skill and the MCP server config, so it is the only install step. **Do
not also run `npx skills add`** — that installs the skill a second time from a different source,
and one copy silently shadows the other.

```
/plugin marketplace add rhesis-ai/skills
/plugin install rhesis@rhesis-ai
```

Then set your API token, either in your shell:

```bash
export RHESIS_API_KEY=rhs_your_token_here
```

or in the `env` block of `~/.claude/settings.json`, which applies to every session without
touching your shell profile:

```json
{
  "env": {
    "RHESIS_API_KEY": "rhs_your_token_here"
  }
}
```

Restart Claude Code and run `/mcp`. Under the built-in servers you should see `rhesis` connected,
with a tool count after it:

```
plugin:rhesis:rhesis · ✔ connected · 52 tools
```

That line is the only confirmation that matters. The skill on its own does nothing — every
operation it performs is a call to this server.

If instead you are asked to authenticate a connector named "Rhesis AI", the plugin's server is not
connected — see [Troubleshooting](#troubleshooting).

For a self-hosted backend, also set `RHESIS_MCP_URL=http://localhost:8080/mcp/`.

---

## Install in other agents

For Cursor, Codex, Gemini CLI, and 40+ other AI interfaces, the skill and the MCP server are two
separate steps.

**Step 1 — the skill.** The CLI detects which agents you have and asks where to place it. Use `-g`
for a global install, or omit it for project-level.

```bash
npx skills add rhesis-ai/skills -g

# Install to specific agents only
npx skills add rhesis-ai/skills -a cursor -a codex -g

# See where it would be installed without installing
npx skills add rhesis-ai/skills --list
```

**Step 2 — the MCP server.** `npx skills` installs the skill instructions only. Configure the
server for your agent using the sections below.

---

## Connect the MCP server

### Cursor

**One click** — click the badge to install the MCP server config automatically:

[![Install in Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](cursor://anysphere.cursor-deeplink/mcp/install?name=rhesis&config=eyJ1cmwiOiJodHRwczovL2FwaS5yaGVzaXMuYWkvbWNwLyIsImhlYWRlcnMiOnsiQXV0aG9yaXphdGlvbiI6IkJlYXJlciBZT1VSX1JIRVNJU19BUElfS0VZIn19)

After clicking, edit `.cursor/mcp.json` to replace `YOUR_RHESIS_API_KEY` with your actual token. Restart Cursor.

**Or paste manually** into `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "rhesis": {
      "url": "https://api.rhesis.ai/mcp/",
      "headers": {
        "Authorization": "Bearer YOUR_RHESIS_API_KEY"
      }
    }
  }
}
```

### Other agents (Codex, Gemini CLI, OpenCode, etc.)

Add the Rhesis MCP server to your agent's MCP config file. The connection details are:

- **URL:** `https://api.rhesis.ai/mcp/` (or `http://localhost:8080/mcp/` for self-hosted)
- **Auth header:** `Authorization: Bearer <your-api-token>`

Refer to your agent's documentation for the exact config file location and format.

---

## Usage

Once installed, start a conversation naturally:

```
"I want to test my travel chatbot. The endpoint is called 'travel-agent-v2'."
```

The skill guides the full workflow:

1. **Discover** — explores what your endpoint can do (Quick or Comprehensive mode)
2. **Plan** — proposes a test suite with requirements, test sets, and metrics
3. **Review** — waits for your approval before creating anything
4. **Create** — builds the entities on the platform
5. **Execute** — runs the tests when you're ready
6. **Analyze** — presents pass/fail summary, failure patterns, and links

You can also use it for direct operations without the full workflow:

```
"List my existing test sets"
"Improve the Safety Compliance metric — make the threshold stricter"
"Compare my last two test runs for the chatbot"
"Link the Accuracy metric to the Provides Accurate Information requirement"
```

---

## What's in this repository

| Path | Purpose |
|------|---------|
| `skills/rhesis/SKILL.md` | Skill instructions — loaded by all compatible agents |
| `skills/rhesis/.mcp.json` | MCP server config bundled with the Claude Code plugin |
| `skills/rhesis/references/workflow-index.md` | Router — read first, points at everything below |
| `skills/rhesis/references/tool-catalog.md` | Every MCP tool with parameters and common mistakes |
| `skills/rhesis/references/odata-patterns.md` | `$filter`, `$select`, navigation properties, batched lookups |
| `skills/rhesis/references/exploration-strategies.md` | Domain probing, capability mapping, boundary discovery |
| `skills/rhesis/references/result-analysis.md` | Single-run summaries, run comparison, failure patterns |
| `.claude-plugin/`, `.cursor-plugin/` | Generated plugin manifests — see `CONTRIBUTING.md` |

---

## Relationship to the native Architect

The Rhesis platform has a built-in Architect agent with a WebSocket chat UI. This skill is a complement, not a replacement:

| | Native Architect | This Skill |
|---|---|---|
| **Access** | Rhesis web UI | Your existing AI interface |
| **Plan tracking** | Structured plan with progress bar | Conversational, host agent's context |
| **Confirmation guard** | Accept/Change UI, auto-approve toggle | Host agent's native confirmation |
| **Write guard** | Plan-level, structural enforcement | Instructional guidance only |
| **Mode transitions** | Formal phases with WebSocket events | Informal, guided by skill instructions |

Use the native Architect when you want maximum structural control. Use this skill when you want to work within your existing AI environment without switching context.

---

## Troubleshooting

**MCP server not connecting:**
- Verify `RHESIS_API_KEY` is set and the token hasn't expired — regenerate at [app.rhesis.ai/tokens](https://app.rhesis.ai/tokens)
- Test connectivity: `curl -H "Authorization: Bearer $RHESIS_API_KEY" https://api.rhesis.ai/mcp/`
- In Cursor, restart the IDE after editing `.cursor/mcp.json`

**Claude Code asks you to authenticate a "Rhesis AI" connector:**
- The plugin's MCP server is not connected, so the skill is falling back to the claude.ai cloud connector, which uses OAuth rather than your API token. Don't authenticate it.
- Run `/mcp` and look for `plugin:rhesis:rhesis`. Missing entirely means the plugin isn't installed or enabled — check `claude plugin list`. Present but failed means `RHESIS_API_KEY` is unset or invalid.
- Environment variables are read at session start, so set the token and restart; a running session won't pick up a new one.
- Once the plugin's server is connected, that connector correctly stays under "unused connectors".

**`rhesis` appears twice in Claude Code, or skill edits have no effect:**
- The skill is installed from two sources, usually because `npx skills add` was run alongside the plugin. One shadows the other and they update through different channels.
- Remove the standalone copy with `rm ~/.claude/skills/rhesis` and keep the plugin. This leaves `~/.agents/skills/rhesis` in place, so Cursor and Codex keep working.

**Skill not activating (other agents):**
- Run `npx skills list` to verify the skill is installed and shows the correct path
- In Cursor, verify `~/.cursor/skills/rhesis/SKILL.md` exists
- Try invoking it explicitly by typing `/rhesis`

**Tool-name collisions:**
- If you have other MCP servers with generic tool names (e.g., `list_test_runs`), they may conflict. In Claude Code, Rhesis tools are prefixed by server name; in Cursor, check `.cursor/mcp.json` for conflicts.
