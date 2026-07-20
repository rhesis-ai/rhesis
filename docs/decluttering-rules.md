# Docs Decluttering Rules

Derived from the patterns in recent docs cleanups (#2129 contributing guides, #2167 deployment
restructure, #2069 verified docs) and a review of the Langfuse docs (langfuse.com/docs) as a
positive example. Apply when trimming pages under `docs/content/`.

## Tone

1. **No empty sales style.** Delete hype and reassurance that carries no information: "That's
   it!", "the script will do it for you!", "improving the user experience". State what a command
   does, not how easy it is. Concrete, true promises are fine where they set expectations —
   "running in under 5 minutes" belongs in a getting-started/quick-start intro (once, not
   repeated in every heading). Exception: marketing-facing pages (Product Tour, Welcome, and to
   a degree Core Concepts) may keep promotional copy — decluttering there targets redundancy and
   wrong facts, not tone.
2. **No "simply", "easily", "just", "powerful", "seamless", "comprehensive".** If a step needs
   "simply" to sound simple, rewrite the step instead. Where a verifiable claim exists, replace
   the adjective with it rather than only deleting: "drop-in replacement for the OpenAI SDK"
   instead of "powerful integration", "minimal changes to your code" instead of "seamless".
3. **Warmth where it fits, facts everywhere else.** A brief thank-you at the top of a
   contributing guide is fine. Elsewhere, skip pleasantries and exclamation marks and start with
   the first useful fact. The first sentence of a page defines its subject: "Prompt management is
   a systematic approach to storing, versioning, and retrieving prompts" / "This guide walks you
   through ingesting your first trace" — no welcome paragraph, no framing before it.
4. **No decorative emojis** (✅ 🚀 📦 ℹ️). Use plain text, or "Note:" / "Warning:" / a `Callout`
   when emphasis is genuinely needed (already a CLAUDE.md rule). Applies to prose and headings
   only — emojis passed as component props (e.g. `NextStepCard` icons) are a deliberate design
   element and stay.

## Redundancy

5. **Say each fact once per page.** The old Running Locally page stated "auto-login, ports,
   generated keys" three times: in an overview bullet list, in code-block comments, and in an
   "Auto-Generated Configuration" section. Keep one canonical spot; delete the echoes.
   Exception: short audience-routing callouts ("**Prefer code?** Use the [Python SDK](…)") are
   acceptable even when the SDK is covered elsewhere on the page — they route a different reader
   at the point of decision, not restate a fact.
6. **Say each fact once across the site.** If another page owns the topic, link to it instead of
   restating (pattern: root/app `CONTRIBUTING.md` files were cut to a short command list plus a
   link to docs.rhesis.ai). Prefer the docs site as the canonical location. In particular, core
   entity definitions (project, endpoint, test set, test run, …) live in `concepts.mdx` and
   nowhere else — feature pages link there instead of re-explaining terms. Exception:
   landing/index pages are navigational surfaces — a repeated navigation block (e.g. the same
   `<Steps>` on Welcome and the Getting Started index) is acceptable.
7. **Delete "Overview" / "What You Get" sections that restate the page title or the section
   headings below them.** A reader who can see the table of contents gains nothing from them.
   Overview *pages* of a section, by contrast, are short hubs (~250 words): the problem the
   feature solves, how it addresses it, one screenshot, links to the subpages — never a
   restatement of subpage content.

## Obviousness

8. **Don't narrate a command's internals.** "The `./rh start` command automatically: checks
   Docker, generates an encryption key, creates `.env.docker.local`, runs migrations, creates the
   admin user…" — the user runs one command; document only what they must do beforehand, type, and
   will see afterwards. Internal steps belong in the script, not the docs. If hidden behavior
   genuinely matters to the reader (async processing, request flow), one mermaid sequence/class
   diagram with a one-line annotation on the concepts or architecture page beats paragraphs of
   narration.
9. **Don't explain standard tools.** No "ruff ensures consistent code style across the project" or
   what pytest/Docker/git fundamentally are. Show the command; the reader knows the tool or can
   read its docs.
10. **Don't list obvious prerequisites.** "Git installed", "Docker Desktop installed and running"
    for a Docker guide — cut, or compress to one line only when a version constraint matters
    (e.g. Python 3.10+). Non-obvious prerequisites are a one-line link, not a section: "If you're
    unfamiliar with core concepts, see [Concepts]."
11. **No file trees or tables describing self-describing files.** A `FileTree` entry like
    "`docker-compose.yml` — Docker Compose configuration" adds nothing. Keep such listings only
    when the description carries non-obvious information.
12. **Keep code-block comments to non-obvious facts.** `# 1. Clone the repository` above
    `git clone` is noise; a comment is fine when it states something the command doesn't
    (`# pulls prebuilt images from GHCR`).

## Scope

13. **Cut tangential/optional tooling mentions** unless the project depends on them (pattern:
    the optional pyenv paragraph was removed from development setup).
14. **One page, one job.** If a section grows into its own topic (env-vars reference inside the
    Docker guide), split it into its own page and link out, keeping only the core subset inline.
15. **Trim option menus to the recommended path.** Present the default way once; mention
    alternatives in a single line with a link, not as parallel fully-worked sections. When
    options must coexist, route the reader by situation instead of presenting them as equals:
    "just debugging → tracing; iterating on prompts → prompt management."
16. **Drop version annotations** like "(v0.6.9+)" from headings and prose. Docs describe the
    current product; version history belongs in the changelog.
17. **Getting-started pages document the user-facing surface only.** Service internals —
    deployment modes, storage-layout tables, backend config payloads, generic best-practices and
    troubleshooting boilerplate — get cut (pattern: Rosalind page trimmed ~600 → ~120 lines to
    what a new user needs: what it is, request/response, sessions, limits, one code example).
18. **"Next steps" are concrete actions, not page pointers.** End guides with the next thing the
    reader would *do* ("Group traces into sessions", "Add attributes to traces"), not card grids
    restating the navigation ("Explore the Product Tour →").

## Terminology

19. **Call it an "LLM application" (or "AI agent"), never "AI application" / "generative AI
    application".** "Generative AI" and "AI application" are too broad — image generation is
    generative AI too, but not what Rhesis tests. Default to **LLM application**; use **AI agent**
    only where the context is specifically about agents (reasoning, tool calls, multi-turn goal
    pursuit). Leave proper names untouched: Garak's expansion "Generative AI Red-teaming and
    Assessment Kit", the "Pydantic AI" framework, and example strings like `name="My AI App"`.
    Glossary term text lives in `content/glossary/glossary-terms.jsonl` — edit the source and
    regenerate with `node scripts/generate-glossary-pages.js`, not the generated `index.mdx` files.

## Documentation sections (`docs/content/`, 262 pages)

Inventory for the decluttering pass, mirroring the sidebar (`_meta.tsx` order and titles).
Check off pages/sections as they are done.

### Docs (87 pages)

- [x] Welcome (`docs/index.mdx`) — no changes needed; landing-page Steps duplication kept by design
- [x] Getting Started — Overview, Setup Environment, Connect Application, Run Evaluations,
      Projects, Default Chatbot (Rosalind)
- [x] Core Concepts (`docs/concepts.mdx`) — already lean; fixed two broken links, tidied whitespace
- [x] Product Tour (`docs/product-tour.mdx`) — no changes; promotional tone allowed by design
- [x] Architect — Overview, Workflow, Endpoint Exploration, Planning Test Suites,
      Running and Analyzing, Chat Features, Scenarios (already rule-compliant; two
      redundancy cuts and eight factual fixes)
- [x] Agent Skill — accurate mirror of the repo skill README; one promotional-word
      fix and one redundancy cut (Cursor skill-install prose duplicated the universal
      installer)
- [x] Organizations & Team — Overview, Roles, Single Sign-On, API Clients
      (Overview: fixed broken list/callout formatting, wrong image alt, and a
      false sidebar claim — denied items are hidden, not locked, and Metrics/Models
      are permission-gated. Roles: corrected Admin/Member capability descriptions.
      API Clients: fixed token-lifetime defaults and invalid_request/target/client
      error mapping. SSO: verified accurate, no changes.)
- [x] Deployment — Overview, Quick Start, Docker Compose, Environment Variables
      (Quick Start and Docker Compose: removed unused FileTree imports, tone pass,
      fixed backup commands and internal links; verified ports, ./rh commands,
      secrets, and env defaults against rh/docker-compose.yml/.env.example)

**Define**
- [ ] Knowledge
- [ ] Behaviors
- [ ] Metrics — Overview, DeepEval, Ragas, Trace Metrics, Code Metrics

**Generate**
- [ ] Playground
- [ ] Explorer — Overview, Workflow, Building and Evaluating, Scenarios, Test Generation
- [ ] Tests — Tests, Conversation Simulation (Overview, Getting Started, Examples & Use Cases,
      Configuration, Execution Trace, Extending), Adversarial Testing (Overview, Polyphemus,
      Requesting Access, SDK Usage), Multi-modal Testing
- [ ] Test Sets — Overview, Import from File, Import from Garak

**Improve**
- [ ] Insights (`results-overview`)
- [ ] Test Runs — Test Runs, Test Execution
- [ ] Experiments — Experiments, Parameter Schema, SDK Usage, Connector Injection
- [ ] Tasks — Tasks, Test Reviews

**Connect**
- [ ] Traces (`tracing`) — Overview, Getting Started, Decorators, Custom Spans,
      Semantic Conventions, Auto-Instrumentation, Microsoft Agent Framework,
      Multi-Agent Tracing, Conversation Tracing
- [ ] Endpoints — Overview, Creating Endpoints, Request Mapping, Response Mapping, Examples,
      Management, SDK Endpoints (+ hidden: auto-configure, multi-turn-conversations)
- [ ] Tools
- [ ] Models
- [ ] Integrations
- [ ] API Tokens
- [ ] Acknowledgments (+ hidden pages: test-results, test-sets-runs)

### Guides (5 pages)

- [ ] Overview
- [ ] Quick Start: Testing in 10 Minutes
- [ ] Building Custom Metrics with the Rhesis SDK
- [ ] Integrating Rhesis SDK into CI/CD
- [ ] Testing User Journeys of AI Agents

### SDK (27 pages)

- [ ] Installation & Setup
- [ ] Rhesis Client
- [ ] Agents
- [ ] Entities — Overview, Projects, Experiments, Models, Test Sets & Tests, Test Attributes,
      Test Runs & Results, Files, Status, Endpoints
- [ ] Parameters & Experiments
- [ ] Test Execution
- [ ] Statistics
- [ ] Models
- [ ] Synthesizers
- [ ] Metrics — Overview, Single-Turn, Conversational
- [ ] Connector — Overview, Input/Output Mapping, File Attachments, Advanced Mapping,
      Parameter Binding, Examples

### Contribute (66 pages)

- [ ] Overview
- [ ] Development Setup
- [ ] Coding Standards
- [ ] Managing Documentation

**Architecture**
- [ ] Frontend — Overview, Getting Started, Architecture, Routing, Component Library,
      State Management, Architect Chat UI, API Integration, Frontend Authentication, Testing
- [ ] Backend (26 pages, largest subsection) — Overview, Getting Started, Architecture,
      API Structure, Database Models, User Settings, Soft Deletion, Cascade Operations,
      Backend Authentication, Authorization (RBAC), Multi-tenancy, Background Tasks,
      Email Notifications, Test Reviews, Test Result Statistics, Test Result Status,
      Test Run Status, OData Query Guide, Architect Chat System, Environment Configuration,
      Security Features, Security Improvements, Database Field Encryption,
      Encryption Troubleshooting, Development Workflow, Deployment
- [ ] Worker — Overview, Architecture, Multi-Worker RPC, Background Tasks,
      Architect Background Tasks, Trace Ingestion Pipeline, Test Execution, Test Types,
      Execution Modes, Logging, Troubleshooting, GKE Troubleshooting
- [ ] SDK — Getting Started, Architect Agent, Integrations
- [ ] Tracing System — Overview, Architecture, Trace Lifecycle, Data Structures
- [ ] Polyphemus
- [ ] Connector (`contribute/connector.mdx`)

**Reference**
- [ ] Environment Variables (`contribute/environment-variables.mdx`)
- [ ] Telemetry

### Other

- [ ] Glossary — 74 single-page term entries, no sidebar (short by design; likely low priority)
- [ ] Changelog (`changelog.mdx`) — top offender in the promotional-word scan (27 hits), but
      release notes may warrant a different bar

## Mechanics when editing

- Preserve MDX rules: escape `{}` outside code blocks; keep `CodeBlock`/`Callout`/`Table` imports
  only if still used after trimming.
- After trimming, check internal links still resolve (pages that got merged/renamed).
- Verify the docs build (`docs/` is Nextra).
- Verify factual correctness while trimming: check every concrete claim the page keeps —
  commands, env vars, API routes and fields, defaults, rate limits, UI labels, code samples —
  against the code. A page that passed the decluttering pass counts as verified, so wrong claims
  must be fixed or cut, never carried over.
