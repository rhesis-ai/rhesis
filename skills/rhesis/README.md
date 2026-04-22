# Rhesis Agent Skill

Design, run, and analyze AI test suites on the [Rhesis](https://rhesis.ai) platform — from within Claude Code, Cursor, or any compatible AI interface.

This skill teaches your agent how to explore an AI endpoint's capabilities, design a test suite, create behaviors and metrics, generate tests, execute them, and analyze the results. All platform operations run through the Rhesis MCP server.

> **Note:** This is different from Rhesis's inbound MCP connector (where the platform consumes tools like Notion or GitHub). Here, an external AI agent calls *into* Rhesis to drive the testing platform.

---

## Prerequisites

- A Rhesis account at [app.rhesis.ai](https://app.rhesis.ai) (or a self-hosted backend)
- An API token — generate one at [app.rhesis.ai/tokens](https://app.rhesis.ai/tokens)

---

## Install in Claude Code

Claude Code uses a plugin system that bundles the skill and MCP server configuration together. Install in two steps:

```
/plugin marketplace add rhesis-ai/rhesis
/plugin install rhesis@rhesis-ai
```

Then set your API token:

```bash
export RHESIS_API_KEY=rhs_your_token_here
```

The plugin reads `RHESIS_API_KEY` automatically. On next session start, the `rhesis` MCP server is connected and the skill is active.

**Self-hosted backend:**

```bash
export RHESIS_MCP_URL=http://localhost:8080/mcp
export RHESIS_API_KEY=your_local_token
```

**Testing locally before publishing:**

```bash
claude --plugin-dir ./skills/rhesis
```

---

## Install in Cursor

### Step 1: Connect the MCP server (one click)

[![Install in Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](cursor://anysphere.cursor-deeplink/mcp/install?name=rhesis&config=eyJ1cmwiOiJodHRwczovL2FwaS5yaGVzaXMuYWkvbWNwIiwiaGVhZGVycyI6eyJBdXRob3JpemF0aW9uIjoiQmVhcmVyIFlPVVJfUkhFU0lTX0FQSV9LRVkifX0K)

After clicking, Cursor opens and installs the MCP server. Then edit `.cursor/mcp.json` to replace `YOUR_RHESIS_API_KEY` with your actual token.

**Or add manually** — paste this into `.cursor/mcp.json` (project-level) or `~/.cursor/mcp.json` (global):

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

Restart Cursor after editing the config.

**Self-hosted backend:** Replace `https://api.rhesis.ai/mcp` with `http://localhost:8080/mcp`.

### Step 2: Install the skill

Clone the repo and symlink the skill directory into Cursor's skills location:

```bash
# Clone (sparse — only the skills directory)
git clone --filter=blob:none --sparse https://github.com/rhesis-ai/rhesis.git rhesis-skills
cd rhesis-skills && git sparse-checkout set skills/rhesis

# Symlink for user-level (all projects)
ln -s "$(pwd)/skills/rhesis" ~/.cursor/skills/rhesis

# Or copy if you prefer no git dependency
cp -r skills/rhesis ~/.cursor/skills/rhesis
```

Cursor loads the skill automatically on next session. To verify, type `/rhesis` or ask about testing an AI endpoint.

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
| `SKILL.md` | Skill instructions (loaded by Cursor; Claude Code fallback) |
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

Use the native Architect when you want maximum structural control. Use this skill when you want to work within Claude Code or Cursor without switching to the Rhesis web UI.

---

## Troubleshooting

**MCP server not connecting:**
- Verify `RHESIS_API_KEY` is set and the token hasn't expired — regenerate at [app.rhesis.ai/tokens](https://app.rhesis.ai/tokens)
- Check that the MCP URL is reachable: `curl -H "Authorization: Bearer $RHESIS_API_KEY" https://api.rhesis.ai/mcp`
- In Cursor, restart the IDE after editing `.cursor/mcp.json`

**Skill not activating (Cursor):**
- Verify `~/.cursor/skills/rhesis/SKILL.md` exists
- Try explicitly invoking: `/rhesis` in the chat

**Claude Code filesystem skill loading issues:**
- There is a known bug with `~/.claude/skills/` discovery. Use the plugin install path (`/plugin install rhesis@rhesis-ai`) — this uses a supported installation mechanism.

**Tool-name collisions:**
- If you have other MCP servers with generic tool names (e.g., `list_test_runs`), they may conflict with Rhesis tools. Rhesis tools will be prefixed by the server name in Claude Code; in Cursor, check `.cursor/mcp.json` for any name conflicts.
