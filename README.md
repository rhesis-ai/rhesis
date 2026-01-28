# Rhesis: Open-Source LLM & Agentic Testing ![Rhesis AI_Logo_RGB_Favicon](https://github.com/user-attachments/assets/ff43ca6a-ffde-4aff-9ff9-eec3897d0d02)

<p align="center">
  <a href="https://github.com/rhesis-ai/rhesis/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT%20%2B%20Commercial-blue" alt="License">
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

**Generate test inputs for LLM & agentic applications using AI, then evaluate outputs to catch issues before production.**

<!-- VISUAL: hero-image.png
     Platform overview showing the Rhesis dashboard or visual workflow diagram.
     Show the end-to-end flow: requirements -> test generation -> execution -> results.
     Dimensions: 1200x600px -->
<p align="center">
  <img src="https://cdn.prod.website-files.com/68c3e3b148a4fd9bcf76eb6a/69039cdfccde6a7b02eac36f_Release%200.4.1.gif"
       loading="lazy"
       width="1080"
       alt="Rhesis Platform Overview">
</p>

---

## What is Rhesis?

Rhesis is an open-source platform for testing and evaluating LLM & agentic applications:

- **AI Test Generation**: Describe requirements in plain language, get hundreds of test scenarios
- **Single & Multi-Turn Testing**: Test both Q&A and complex conversations (Penelope agent)
- **LLM-as-Judge Evaluation**: Automated scoring with 50+ pre-built metrics and reasoning explanations
- **Traces & Observability**: Monitor your LLM applications with OpenTelemetry-based tracing
- **Team Collaboration**: UI for non-technical users, SDK for engineers, CI/CD integration

---

## Why Rhesis?

**Built for teams, not just engineers**: UI for non-technical stakeholders to define requirements and review results. SDK for engineers to work from their IDE and integrate into CI/CD. Comments, tasks, and review workflows so legal, compliance, and domain experts can collaborate without writing code.

### Rhesis vs...

| Alternative | Rhesis Difference |
|-------------|-------------------|
| **Manual testing** | Generates hundreds of test cases automatically instead of writing them by hand |
| **Traditional test frameworks** | Built for non-deterministic LLM behavior, not deterministic code |
| **LLM observability tools** | Focuses on **pre-production** validation, not just production monitoring |
| **Red-teaming services** | Continuous and self-service, not a one-time audit |

---

## Reliability Testing & Adversarial Testing

<!-- VISUAL: testing-types.png
     Split diagram showing two testing approaches side by side:
     Left = Reliability Testing (checkmarks, validation icons, "works correctly")
     Right = Adversarial Testing (shield icon, red-team, "find vulnerabilities")
     Dimensions: 1000x400px -->

### Reliability Testing

Ensure your LLM application works correctly under normal conditions:

- Validates expected behavior against requirements
- Tests edge cases and boundary conditions
- Measures consistency and accuracy across runs

### Adversarial Testing (Red-Teaming)

Proactively find vulnerabilities before bad actors do:

- Jailbreak attempts and prompt injection
- PII leakage and data extraction
- Harmful content generation
- Role violation and instruction bypassing

---

## Define & Generate

<!-- VISUAL: define-generate-flow.png
     Flow diagram showing the test generation workflow:
     Requirements (text icon) -> Context Sources (MCP + file upload icons) -> AI Generation (sparkle) -> Test Cases (list)
     Show both single-turn and multi-turn test outputs
     Dimensions: 1000x300px -->

### Define What Your App Should (and Shouldn't) Do

- Write requirements in plain language
- Connect knowledge sources via **file upload** and **MCP** (Notion, GitHub, Jira, Confluence) for best context
- Define positive behaviors (what it should do) and restrictions (what it must not do)

### AI-Powered Test Generation

- Generate hundreds of test scenarios from requirements
- **Single-turn tests** for Q&A validation
- **Multi-turn tests** for conversation flows (Penelope agent simulates realistic user interactions)
- **Adversarial test cases** for red-teaming

---

## Evaluate & Collaborate

<!-- VISUAL: evaluate-collaborate.png
     Dashboard mockup showing:
     - Test results grid with pass/fail indicators
     - Metric scores with reasoning
     - Comments and task assignment UI
     - Team collaboration features
     Dimensions: 1000x500px -->

### Manage Tests at Scale

- Organize hundreds of test cases into test sets
- Track test runs with detailed results and trends
- Compare performance across versions

### 50+ Pre-Built Metrics

| Framework | Metrics |
|-----------|---------|
| **RAGAS** | Context relevance, faithfulness, answer accuracy |
| **DeepEval** | Bias, toxicity, PII leakage, role violation, turn relevancy, knowledge retention |
| **Garak** | Jailbreak detection, prompt injection, XSS, malware generation, data leakage |
| **Custom** | NumericJudge and CategoricalJudge for domain-specific evaluation |

### LLM-as-Judge Evaluation

- Automated scoring with reasoning explanations
- **Bring Your Own Model** (BYOM): Use any LLM provider for evaluation

### Built for Teams

- UI for non-technical stakeholders (legal, compliance, domain experts)
- SDK/API for engineers and CI/CD integration
- Comments, tasks, and review workflows

---

## What Can You Test?

<!-- VISUAL: use-cases-grid.png
     2x2 grid with icons and brief descriptions:
     - Conversational AI (chat bubble icon)
     - RAG Applications (document + search icon)
     - NL-to-SQL / NL-to-Code (database + code icon)
     - Agentic Systems (robot/workflow icon)
     Dimensions: 800x400px -->

### Conversational AI

Chatbots, virtual assistants, customer support bots

- Multi-turn conversation testing with Penelope
- Role adherence and knowledge retention

### RAG Applications

Retrieval-augmented generation systems

- Context relevance and faithfulness
- Hallucination detection

### NL-to-SQL / NL-to-Code

Natural language to structured query systems

- Query accuracy and syntax validation
- Edge case handling

### Agentic Systems

Multi-step reasoning and tool-using agents

- Tool selection accuracy
- Goal achievement tracking
- Multi-agent coordination

---

## SDK: Code-First Testing

Test your Python functions directly with the `@endpoint` decorator:

```python
from rhesis.sdk.decorators import endpoint

@endpoint(name="my-chatbot")
def chat(message: str) -> str:
    # Your LLM logic here
    return response
```

- **Zero configuration**: Decorate your function, run tests from the platform
- **Parameter binding**: Inject dependencies (DB, config, auth) automatically
- **Auto-reconnection**: Reliable connection to Rhesis platform
- **Environment management**: Switch between dev/staging/production

---

## Traces & Observability

<!-- VISUAL: traces-observability.png
     Trace waterfall/span view showing:
     - LLM calls with latency and token counts
     - Nested spans (retrieval, embedding, generation)
     - Link to test results
     Dimensions: 1000x400px -->

Monitor your LLM applications in development and production:

- OpenTelemetry-based tracing integration
- Track LLM calls, latency, and token usage
- Link traces to test results for debugging
- SDK decorators: `@observe` for automatic instrumentation

```python
from rhesis.sdk.decorators import observe

@observe.llm(model="gpt-4")
def generate_response(prompt: str) -> str:
    # Your LLM call here
    return response
```

---

## Deploy Rhesis

<!-- VISUAL: deployment-options.png
     Three icons representing deployment options:
     - Cloud (cloud icon) - "Fastest"
     - Docker (container icon) - "Local"
     - Kubernetes (helm icon) - "Production"
     Dimensions: 600x150px -->

### Option 1: Rhesis Cloud (Fastest)

Managed deployment, free tier available, no setup required.

👉 **[app.rhesis.ai](https://app.rhesis.ai)**

### Option 2: Self-Host with Docker

Get the full platform running locally in under 5 minutes:

```bash
# Clone the repository
git clone https://github.com/rhesis-ai/rhesis.git
cd rhesis

# Start all services with one command
./rh start
```

**Access the platform:**
- Frontend: `http://localhost:3000` (auto-login enabled)
- Backend API: `http://localhost:8080/docs`

**Managing services:**
```bash
./rh logs          # View logs from all services
./rh stop          # Stop all services
./rh restart       # Restart all services
./rh delete        # Delete everything (fresh start)
```

### Option 3: Production Self-Hosting

For Kubernetes and production deployments, see the [Self-hosting Documentation](https://docs.rhesis.ai/getting-started/self-hosting).

---

## Bring Your Own Model

Use any LLM provider for test generation and evaluation:

| Provider | Type | Documentation |
|----------|------|---------------|
| OpenAI | Cloud | [Docs](https://docs.rhesis.ai/sdk/models) |
| Anthropic | Cloud | [Docs](https://docs.rhesis.ai/sdk/models) |
| Google Gemini | Cloud | [Docs](https://docs.rhesis.ai/sdk/models) |
| Mistral | Cloud | [Docs](https://docs.rhesis.ai/sdk/models) |
| Cohere | Cloud | [Docs](https://docs.rhesis.ai/sdk/models) |
| Groq | Cloud | [Docs](https://docs.rhesis.ai/sdk/models) |
| Together AI | Cloud | [Docs](https://docs.rhesis.ai/sdk/models) |
| Ollama | Local | [Docs](https://docs.rhesis.ai/sdk/models) |
| LiteLLM | Unified | [Docs](https://docs.rhesis.ai/sdk/models) |
| vLLM (Custom) | Self-hosted | [Docs](https://docs.rhesis.ai/sdk/models) |

---

## Open Source

MIT licensed with no plans to relicense core features. Commercial features (if we build them) will live in `ee/` folders.

We built this because existing LLM testing tools didn't meet our needs. If you have the same problem, contributions are welcome.

---

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Ways to contribute:**
- Fix bugs or add features
- Contribute test sets for common failure modes
- Improve documentation
- Help others in Discord or GitHub discussions

---

## License

**Community Edition**: MIT License - see [LICENSE](LICENSE) file for details. Free forever.

**Enterprise Edition**: Enterprise features in `ee/` folders are planned for 2026 and not yet available. Contact hello@rhesis.ai for early access information.

---

## Support

- [Documentation](https://docs.rhesis.ai)
- [Discord](https://discord.rhesis.ai)
- [GitHub Issues](https://github.com/rhesis-ai/rhesis/issues)

---

## Security & Privacy

We take data security and privacy seriously. For further details, please refer to our [Privacy Policy](https://rhesis.ai/privacy-policy).

### Telemetry

Rhesis automatically collects basic usage statistics from both cloud platform users and self-hosted instances.

This information enables us to:

1. Understand how Rhesis is used and enhance the most relevant features.
2. Monitor overall usage for internal purposes and external reporting.

No collected data is shared with third parties, nor does it include any sensitive information. For a detailed description of the data collected and the associated privacy safeguards, please see the [Self-hosting Documentation](https://docs.rhesis.ai/getting-started/self-hosting).

**Opt-out:**

For self-hosted deployments, telemetry can be disabled by setting the environment variable `OTEL_RHESIS_TELEMETRY_ENABLED=false`.

For cloud deployments, telemetry is always enabled as part of the Terms & Conditions agreement.

---

**Made with ❤️ in Potsdam, Germany**

Learn more at [rhesis.ai](https://rhesis.ai)
