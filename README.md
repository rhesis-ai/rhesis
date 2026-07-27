<p align="center">
  <img src="https://github.com/user-attachments/assets/ff43ca6a-ffde-4aff-9ff9-eec3897d0d02" alt="Rhesis AI Logo" height="80">
</p>

# Rhesis: Get the knowledge you need to improve your agents

<p align="center">
  <a href="https://github.com/rhesis-ai/rhesis/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT%20%2B%20Enterprise-blue" alt="License">
  </a>
  <a href="https://pypi.org/project/rhesis-sdk/">
    <img src="https://img.shields.io/pypi/v/rhesis-sdk" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/rhesis-sdk/">
    <img src="https://img.shields.io/pypi/pyversions/rhesis-sdk" alt="Python Versions">
  </a>
  <a href="https://codecov.io/gh/rhesis-ai/rhesis">
    <img src="https://codecov.io/gh/rhesis-ai/rhesis/graph/badge.svg?token=1XQV983JEJ" alt="codecov">
  </a>
  <a href="https://discord.rhesis.ai">
    <img src="https://img.shields.io/discord/1340989671601209408?color=7289da&label=Discord&logo=discord&logoColor=white" alt="Discord">
  </a>
  <a href="https://www.linkedin.com/company/rhesis-ai">
    <img src="https://img.shields.io/badge/LinkedIn-Rhesis_AI-blue?logo=linkedin" alt="LinkedIn">
  </a>
  <a href="https://huggingface.co/rhesis">
    <img src="https://img.shields.io/badge/🤗-Rhesis-yellow" alt="Hugging Face">
  </a>
  <a href="https://docs.rhesis.ai">
    <img src="https://img.shields.io/badge/docs-rhesis.ai-blue" alt="Documentation">
  </a>
</p>

<p align="center">
  <a href="https://rhesis.ai"><strong>Website</strong></a> ·
  <a href="https://docs.rhesis.ai"><strong>Docs</strong></a> ·
  <a href="https://discord.rhesis.ai"><strong>Discord</strong></a> ·
  <a href="https://github.com/rhesis-ai/rhesis/blob/main/CHANGELOG.md"><strong>Changelog</strong></a>
</p>

<h3 align="center">Collaborative platform for continuous AI improvement.<br>
<strong>Open source · SaaS or self-hosted · UI, SDK, and MCP</strong></h3>

<p align="center">
A shared workspace where domain experts annotate behavior and engineers get the feedback they need to improve the agent.
</p>

<p align="center">
  <a href="https://rhesis.ai/?video=open" target="_blank">
    <img src=".github/images/GH_Short_Demo.png"
         loading="lazy"
         width="1080"
         alt="Rhesis Platform Overview - Click to watch demo">
  </a>
</p>

---

## Why Rhesis?

Many tools start with tests or traces. Rhesis starts with the collaboration problem: getting domain-expert knowledge into agent development.

- **Capture expert judgment** — Reviews and expected behavior stay attached to the case and agent version, not buried in Slack
- **One definition of good** — Annotated sets the whole team shares and measures against
- **UI for experts, SDK & MCP for builders** — Same record, three interfaces
- **From review to CI** — Expand coverage with generation and simulation; run checks engineers already use

<p align="center">
  <img src=".github/images/GH_Collaboration_Hub.jpg"
       loading="lazy"
       width="1080"
       alt="Rhesis collaboration hub — domain knowledge in, agent progress out">
</p>

---

## Who it’s for

| Role | How they use Rhesis |
|------|---------------------|
| **Domain experts** | Review outputs, annotate cases, define what good means — UI, no code |
| **Product managers** | Structure expert feedback and see whether the agent improves against the PRD — UI / MCP |
| **AI engineers** | Pull annotated sets into SDK, CI, and MCP while you build |

---

## How it works

| Step | What you do |
|------|-------------|
| **Connect** | Start from the PRD and context your team already uses; link your LLM application |
| **Annotate** | Capture expected behavior and edge cases from domain experts in reusable test sets |
| **Evaluate** | Run annotated sets against agent changes; catch regressions before they ship |
| **Review** | Keep experts in the loop on hard, novel cases; automate routine checks over time |
| **Improve** | Measure progress against the same definition of good every cycle |

---

## Connect your app

Rhesis needs a way to invoke your LLM application under test.

### SDK connector (recommended for local and private apps)

Your app opens a persistent outbound WebSocket. Rhesis sends test inputs down that connection — no public URL required.

```python
from rhesis.sdk.decorators import endpoint

@endpoint(name="my-chatbot")
def chat(message: str) -> str:
    return response
```

See the [SDK README](sdk/README.md) for install, environments, and tracing.

### REST API

Language-agnostic access for CI/CD and custom integrations: manage test sets, trigger runs, fetch results. [OpenAPI spec](https://api.rhesis.ai/docs).

### MCP and skills

Use Rhesis from MCP-capable clients (Cursor, Claude Code, and others): design suites, pull sets, trigger runs, and keep expert context in the tools engineers already use.

```bash
npx skills add rhesis-ai/rhesis
```

Connect knowledge sources (Notion, GitHub, Jira, Confluence) so generation and review stay grounded. See the [skills README](skills/rhesis/README.md).

> Tracing (OpenTelemetry) and LLM providers for synthesis/judges are documented separately — see [Tracing](https://docs.rhesis.ai/tracing) and [Models](https://docs.rhesis.ai/sdk/models). They are not how you connect the app under test.

---

## Capabilities

Once knowledge is in the shared record, you can expand and harden coverage:

- **Test generation** from requirements and knowledge (files or MCP)
- **Conversation simulation** with Penelope; **adversarial probing** with Polyphemus and [garak](https://github.com/leondz/garak)
- **60+ metrics** — RAGAS, DeepEval, garak, and custom LLM-as-Judge evaluators
- **Traces** linked to test results via OpenTelemetry

| Use case | What you validate |
|----------|-------------------|
| **Conversational & support agents** | Role adherence, policy citation, escalation |
| **RAG / knowledge assistants** | Faithfulness, grounding, retrieval quality |
| **Tool-using & multi-agent systems** | Tool choice, goal completion, handoffs |
| **Regulated / high-stakes domains** | Expert-defined must / must-not behaviors |

Details: [docs.rhesis.ai](https://docs.rhesis.ai)

---

## Get started

### Cloud

[app.rhesis.ai](https://app.rhesis.ai) — managed service, connect your app.

### Local (Docker)

```bash
git clone https://github.com/rhesis-ai/rhesis.git && cd rhesis && ./rh start
```

`./rh start` pulls prebuilt images from GHCR. To build from the repo instead, use `./rh start --build` (and `./rh restart --build` after local Dockerfile changes).

**Access:** Frontend at `localhost:3000`, API at `localhost:8080/docs`

**Commands:** `./rh logs` · `./rh stop` · `./rh restart` · `./rh delete`

> This setup enables auto-login for local testing. For production self-hosting (including Kubernetes), see [Self-hosting docs](https://docs.rhesis.ai/deployment/self-hosting).

Once the platform is running, connect your app with the SDK:

```bash
pip install rhesis-sdk
```

See [sdk/README.md](sdk/README.md).

| Option | Best for |
|--------|----------|
| **[Rhesis Cloud](https://app.rhesis.ai)** | Managed deployment |
| **Local Docker (`./rh start`)** | Development and trying the platform |
| **Kubernetes** | Production self-hosting — [docs](https://docs.rhesis.ai/deployment/self-hosting) |

---

## In this repo

| Path | What it covers |
|------|----------------|
| [`sdk/`](sdk/README.md) | Python SDK — connector, synthesizers, metrics, tracing |
| [`skills/rhesis/`](skills/rhesis/README.md) | Agent skill + MCP workflows for Cursor, Claude Code, and others |
| [`apps/backend/`](apps/backend/README.md) | API and workers |
| [`apps/frontend/`](apps/frontend/README.md) | Web UI |
| [`docs/`](docs/README.md) | Documentation site source |

---

## Open source

[MIT licensed](LICENSE). No plans to relicense core features. Enterprise features live in `ee/` and remain separate.

We built Rhesis because expert knowledge kept getting stuck outside the agent loop. If you face the same challenge, contributions are welcome.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Ways to contribute:** Fix bugs or add features · Contribute test sets for common failure modes · Improve documentation · Help others in Discord or GitHub discussions

---

## Support

- **[Documentation](https://docs.rhesis.ai)** — Guides and API reference
- **[Discord](https://discord.rhesis.ai)** — Community support
- **[GitHub Issues](https://github.com/rhesis-ai/rhesis/issues)** — Bug reports and feature requests

---

## Security & privacy

We take data security seriously. See our [Privacy Policy](https://rhesis.ai/privacy-policy) for details.

**Telemetry:** Rhesis can collect basic, anonymized usage statistics to improve the product. No sensitive data is collected or shared with third parties.

- **Self-hosted:** Opt in by setting `OTEL_RHESIS_TELEMETRY_ENABLED=true` (off by default)
- **Cloud:** Telemetry enabled as part of Terms & Conditions

---

<p align="center">
  <strong>Made with <img src="https://github.com/user-attachments/assets/598c2d81-572c-46bd-b718-dee32cdc749c" height="16" alt="Rhesis logo"> in Potsdam, Germany 🇩🇪</strong>
</p>

<p align="center">
  <a href="https://rhesis.ai">Learn more at rhesis.ai</a>
</p>
