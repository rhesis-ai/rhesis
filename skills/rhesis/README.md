# Rhesis Agent Skill

Design, run, and analyze AI test suites on the [Rhesis](https://rhesis.ai) platform — from within Claude Code, Cursor, Codex, or [any compatible AI interface](https://github.com/vercel-labs/skills#supported-agents).

This skill teaches your agent how to explore an AI endpoint's capabilities, design a test suite, create behaviors and metrics, generate tests, execute them, and analyze the results. All platform operations run through the Rhesis MCP server.

> **Note:** This is different from Rhesis's inbound MCP connector (where the platform consumes tools like Notion or GitHub). Here, an external AI agent calls *into* Rhesis to drive the testing platform.

---

## Prerequisites

- A Rhesis account at [app.rhesis.ai](https://app.rhesis.ai) (or a self-hosted backend)
- An API token — generate one at [app.rhesis.ai/tokens](https://app.rhesis.ai/tokens)

---

## Install the skill (any agent)

The fastest way to install across Claude Code, Cursor, Codex, Gemini CLI, and 40+ other AI interfaces:

```bash
npx skills add rhesis-ai/rhesis
```

The CLI detects which agents you have installed and asks where to place the skill. Use `-g` for a global install (available in all projects) or omit it for project-level.

```bash
# Global install — available everywhere
npx skills add rhesis-ai/rhesis -g

# Install to specific agents only
npx skills add rhesis-ai/rhesis -a cursor -a claude-code -g

# See where it would be installed without installing
npx skills add rhesis-ai/rhesis --list
```

> `npx skills` installs the skill instructions. The MCP server (which the skill uses to talk to Rhesis) is configured separately — see the sections below for your agent.

---

## Connect the MCP server

The skill needs the Rhesis MCP server connected to call platform tools. Set this up once per agent.

### Claude Code

```bash
export RHESIS_API_KEY=rhs_your_token_here
# Optional — defaults to https://api.rhesis.ai/mcp
export RHESIS_MCP_URL=http://localhost:8080/mcp
```

The skill is bundled as a Claude Code plugin that includes the MCP config. To install via plugin (MCP + skill together):

```
/plugin marketplace add rhesis-ai/rhesis
/plugin install rhesis@rhesis-ai
```

Then set `RHESIS_API_KEY` as above.

### Cursor

**One click** — click the badge to install the MCP server config automatically:

[![Install in Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](cursor://anysphere.cursor-deeplink/mcp/install?name=rhesis&config=eyJ1cmwiOiJodHRwczovL2FwaS5yaGVzaXMuYWkvbWNwIiwiaGVhZGVycyI6eyJBdXRob3JpemF0aW9uIjoiQmVhcmVyIFlPVVJfUkhFU0lTX0FQSV9LRVkifX0K)

After clicking, edit `.cursor/mcp.json` to replace `YOUR_RHESIS_API_KEY` with your actual token. Restart Cursor.

**Or paste manually** into `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "rhesis": {
      "url": "https://api.rhesis.ai/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_RHESIS_API_KEY"
      }
    }
  }
}
```

### Other agents (Codex, Gemini CLI, OpenCode, etc.)

Add the Rhesis MCP server to your agent's MCP config file. The connection details are:

- **URL:** `https://api.rhesis.ai/mcp` (or `http://localhost:8080/mcp` for self-hosted)
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
2. **Plan** — proposes a test suite with behaviors, test sets, and metrics
3. **Review** — waits for your approval before creating anything
4. **Create** — builds the entities on the platform
5. **Execute** — runs the tests when you're ready
6. **Analyze** — presents pass/fail summary, failure patterns, and links

You can also use it for direct operations without the full workflow:

```
"List my existing test sets"
"Improve the Safety Compliance metric — make the threshold stricter"
"Compare my last two test runs for the chatbot"
"Link the Accuracy metric to the Provides Accurate Information behavior"
```

---

## What's in this directory

| File | Purpose |
|------|---------|
| `SKILL.md` | Skill instructions — loaded by all compatible agents |
| `.claude-plugin/plugin.json` | Claude Code plugin manifest |
| `.mcp.json` | MCP server config bundled with the Claude Code plugin |
| `references/tool-catalog.md` | All 27 MCP tools with parameters and common mistakes |
| `references/odata-patterns.md` | `$filter`, `$select`, navigation properties, batched lookups |
| `references/exploration-strategies.md` | Domain probing, capability mapping, boundary discovery |
| `references/result-analysis.md` | Single-run summaries, run comparison, failure patterns |

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
- Test connectivity: `curl -H "Authorization: Bearer $RHESIS_API_KEY" https://api.rhesis.ai/mcp`
- In Cursor, restart the IDE after editing `.cursor/mcp.json`

**Skill not activating:**
- Run `npx skills list` to verify the skill is installed and shows the correct path
- In Cursor, verify `~/.cursor/skills/rhesis/SKILL.md` exists
- In Claude Code, try `/rhesis` explicitly; if the filesystem skill loading bug affects your version, use the plugin install path instead

**Tool-name collisions:**
- If you have other MCP servers with generic tool names (e.g., `list_test_runs`), they may conflict. In Claude Code, Rhesis tools are prefixed by server name; in Cursor, check `.cursor/mcp.json` for conflicts.
