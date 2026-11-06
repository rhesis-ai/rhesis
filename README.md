<p align="center">
  <img src=".github/images/GH-collaborate.png"
       loading="lazy"
       width="1920"
       alt="Rhesis: Get the feedback you need to improve your agents">
</p>

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
  <a href="https://docs.rhesis.ai">
    <img src="https://img.shields.io/badge/docs-rhesis.ai-blue" alt="Documentation">
  </a>
</p>

<p align="center">
  <a href="#get-started"><strong>Quickstart</strong></a> ·
  <a href="https://youtu.be/sCfhabhk6ww"><strong>Connect your agent (video)</strong></a> ·
  <a href="https://rhesis.ai"><strong>Website</strong></a> ·
  <a href="https://docs.rhesis.ai"><strong>Docs</strong></a> ·
  <a href="https://discord.rhesis.ai"><strong>Discord</strong></a> ·
  <a href="https://github.com/rhesis-ai/rhesis/blob/main/CHANGELOG.md"><strong>Changelog</strong></a>
</p>

<h3 align="center">The open-source collaboration layer for teams building AI agents.<br>
<strong>Open source · SaaS or self-hosted · UI, SDK, and MCP</strong></h3>

<p align="center">
Connect the agent you are building, share the link with your team, and get structured feedback from the people who know the right answers.
</p>

---

## Why Rhesis?

Most tools start with tests or traces. Rhesis starts one step earlier: the people who know what the
agent should answer are not the people building it, and their feedback rarely arrives in a form you
can act on.

- **Feedback that stays attached.** Every review sits on the test case and the agent version that produced it, not in a Slack thread
- **One pass/fail bar.** The whole team reviews against the same tests, and you measure against them
- **UI for reviewers, SDK and MCP for builders.** Same data, three ways in
- **From feedback to CI.** Recurring feedback becomes tests and metrics that run on every change

<p align="center">
  <a href="https://rhesis.ai/?video=open" target="_blank">
    <img src=".github/images/GH-demo-video.jpg"
         loading="lazy"
         width="1920"
         alt="Watch: how engineers and domain experts test AI agents together">
  </a>
</p>

---

## How it works

<p align="center">
  <img src=".github/images/GH-how-it-works.png"
       loading="lazy"
       width="1920"
       alt="Rhesis workflow: requirements and conversations become tests, metrics and expert verdicts evaluate the agent, CI gates releases, traces feed back as new tests">
</p>

**1. Connect the agent you are building.** Via the SDK or a REST endpoint, no public URL needed
([how](#connect-your-agent), [video](https://youtu.be/sCfhabhk6ww)).

**2. Share the Rhesis link with your stakeholders.** Domain experts, product managers, and
reviewers open it in a browser. Nothing to install, no code.

**3. They put the agent to work.** In the playground they chat with the live agent and turn
interesting conversations into tests. They create and run test sets, simulate multi-turn
conversations, and leave structured feedback on what came back: pass/fail verdicts and comments,
down to the individual metric or conversation turn.

**4. Pull that feedback back into development.** Read it from the SDK or the REST API, or work
with it from Cursor, Claude Code, and other MCP clients through the Rhesis skill. Fix the agent,
run the same tests again.

**5. Agree on what the agent has to get right.** Each cycle, feedback that arrived as prose becomes
tests and metrics that check the same thing automatically. Reviews on a handful of cases end up as
evals that run on every change.

---

## Who it’s for

| Role | How they use Rhesis |
|------|---------------------|
| **AI engineers** | Connect the agent, pull feedback and reviewed test sets into the SDK, CI, and MCP while you build |
| **Domain experts** | Try the agent, review its answers, say what is wrong and what a correct answer looks like. UI, no code |
| **Product managers** | Turn scattered feedback into tests, and see whether the agent improves against the PRD. UI or MCP |

---

## Capabilities

Nobody can review every case by hand. Once the first feedback is in, you can grow coverage from it:

- **[Architect](https://docs.rhesis.ai/docs/architect)**: a chat agent that turns a PRD into requirements, metrics, and test sets, runs them, and charts the results
- **Test generation** from your requirements, a PRD, or an uploaded file
- **Conversation simulation** with Penelope; **adversarial probing** with Polyphemus and [garak](https://github.com/leondz/garak)
- **[Requirement coverage](https://docs.rhesis.ai/docs/requirements)**: see which requirements pass or fail, and in which conversations
- **[Production tracing](https://docs.rhesis.ai/docs/tracing)**: OpenTelemetry traces with latency, tokens, and cost. Auto-instrumentation for LangChain, LangGraph, Microsoft Agent Framework, Pydantic AI, Google ADK, and Haystack
- **[Experiments](https://docs.rhesis.ai/docs/experiments)**: compare model, prompt, or retrieval changes on the same test set, by quality and cost

Generated tests are only as good as the requirements behind them. Instead of retyping a spec into a
prompt, connect the tools your requirements already live in (Notion, GitHub, Jira, Confluence) and
Rhesis writes tests from the real thing. See [Tools](https://docs.rhesis.ai/docs/tools).

### From what your experts know to what runs in CI

| Who knows it | What they know | What Rhesis checks |
|---|---|---|
| **Legal** | "Bookings more than 24 h before departure are fully refundable." | The agent quotes the right refund terms for this booking's dates, across multi-turn conversations |
| **Support lead** | "Business accounts always escalate to a named contact." | Escalation is offered on the business tier, never on the consumer tier, and the contact is named |
| **Product** | "If the customer changes topic, the agent still finishes the cancellation." | Simulated users interrupt and rephrase; the agent keeps the booking reference and completes the task |
| **Marketing** | "We never promise delivery dates." | Adversarial prompts try to get a promise out of it; the brand-voice metric flags any that work |

None of these come from a metric library. Your team writes them once as requirements, and they run on every change.

Details: [docs.rhesis.ai](https://docs.rhesis.ai)

---

## Get started

### Cloud

[app.rhesis.ai](https://app.rhesis.ai): managed service, connect your agent and invite your team.

### Local (Docker)

```bash
git clone https://github.com/rhesis-ai/rhesis.git && cd rhesis && ./rh start
```

`./rh start` pulls prebuilt images from GHCR. To build from the repo instead, use `./rh start --build` (and `./rh restart --build` after local Dockerfile changes).

**Access:** Frontend at `localhost:3000`, API at `localhost:8080/docs`

**Commands:** `./rh logs` · `./rh stop` · `./rh restart` · `./rh delete`

> Local setup auto-logs you in. Not for production; see below.

Once the platform is running, connect your agent with the SDK:

```bash
pip install rhesis-sdk
```

See [sdk/README.md](sdk/README.md).

### Deployment options

| Option | Best for |
|--------|----------|
| **[Rhesis Cloud](https://app.rhesis.ai)** | Managed by us, nothing to run |
| **Local Docker (`./rh start`)** | Development and trying the platform |
| **[Docker Compose](https://docs.rhesis.ai/self-hosting/docker-compose)** | A single server |
| **[Kubernetes (Helm)](https://docs.rhesis.ai/self-hosting/kubernetes-helm)** | Production clusters, via ArgoCD and the [`charts/rhesis`](charts/rhesis) chart we run ourselves |
| **[GCP (Terraform)](https://docs.rhesis.ai/self-hosting/gcp-terraform)** | Provisioning a GKE cluster from scratch |

More: [self-hosting docs](https://docs.rhesis.ai/self-hosting).

---

## Connect your agent

Rhesis needs a way to invoke the agent under test. Two ways to do it: we recommend the SDK
connector, but if your agent already has a public REST endpoint, that is the fastest way to get
started.

### SDK connector (recommended)

Your process opens a persistent outbound WebSocket. Rhesis sends test inputs down that connection,
so the agent needs no public URL and can stay on your laptop or inside your VPC. You write a
function instead of describing a payload, and the same SDK carries tracing.

```python
from rhesis.sdk.decorators import endpoint

@endpoint(name="my-chatbot")
def chat(message: str) -> str:
    # Call your agent here
    return my_agent(message)
```

Run it, and the endpoint registers itself in Rhesis. See the [SDK README](sdk/README.md) for
install, environments, and tracing.

### Your agent's REST endpoint (fastest start if it is public)

Already serving HTTP on a reachable URL? Register it in the UI, no code and nothing to deploy. You
supply auth headers plus request and response mapping, or let Rhesis derive the configuration from
an OpenAPI spec or by exploring the endpoint. See
[Creating endpoints](https://docs.rhesis.ai/docs/endpoints/creating-endpoints).

Either way, the next step is the same: share the link, and let your team start using the agent
through the [playground](https://docs.rhesis.ai/docs/playground) and test runs.

---

## Work from your own tools

Feedback lands in Rhesis, but you do not have to leave your editor to act on it.

### MCP and skills

Use Rhesis from MCP-capable clients (Cursor, Claude Code, and others): build test sets, pull
results, trigger runs, and read the feedback in the tools you already work in. Install with the
[skills](https://github.com/vercel-labs/skills) CLI:

```bash
npx skills add rhesis-ai/rhesis
```

See the [skills README](skills/rhesis/README.md).

### SDK and REST API

Pull test runs, results, and the reviews attached to them from Python, or hit the API directly from
CI in any language: [OpenAPI spec](https://api.rhesis.ai/docs).

> The SDK also handles [tracing](https://docs.rhesis.ai/docs/tracing). LLMs for generation and judges: [Models](https://docs.rhesis.ai/sdk/models).

---

## In this repo

| Path | What it covers |
|------|----------------|
| [`sdk/`](sdk/README.md) | Python SDK: connector, synthesizers, metrics, tracing |
| [`skills/rhesis/`](skills/rhesis/README.md) | Agent skill + MCP workflows for Cursor, Claude Code, and others |
| [`apps/backend/`](apps/backend/README.md) | API and workers |
| [`apps/frontend/`](apps/frontend/README.md) | Web UI |
| [`docs/`](docs/README.md) | Documentation site source |
| [`charts/rhesis/`](charts/rhesis) | Helm chart for Kubernetes deployments |
| [`terraform/`](terraform) | Infrastructure as code for GCP |

---

## Open source

[MIT licensed](LICENSE). No plans to relicense core features. Enterprise features live in `ee/` and remain separate.

We built Rhesis because the feedback that mattered most kept getting stuck outside the development loop. If you face the same problem, contributions are welcome.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Ways to contribute:** Fix bugs or add features · Contribute test sets for common failure modes · Improve documentation · Help others in Discord or GitHub discussions

---

## Support

- **[Documentation](https://docs.rhesis.ai)**: Guides and API reference
- **[Discord](https://discord.rhesis.ai)**: Community support
- **[GitHub Issues](https://github.com/rhesis-ai/rhesis/issues)**: Bug reports and feature requests

---

## Security & privacy

We take data security seriously. See our [Privacy Policy](https://rhesis.ai/privacy-policy) for details.

**Telemetry:** Rhesis collects basic, anonymized usage statistics to improve the product. No sensitive data is collected or shared with third parties.

- **Self-hosted:** Opt out by setting `OTEL_RHESIS_TELEMETRY_ENABLED=false`
- **Cloud:** Telemetry enabled as part of Terms & Conditions

---

<p align="center">
  <strong>Made with <img src="https://github.com/user-attachments/assets/598c2d81-572c-46bd-b718-dee32cdc749c" height="16" alt="Rhesis logo"> in Potsdam, Germany 🇩🇪</strong>
</p>

<p align="center">
  <a href="https://rhesis.ai">Learn more at rhesis.ai</a>
</p>
