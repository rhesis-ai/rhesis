# Rhesis Documentation Navigation Overhaul — Work Packages

> Generated: 2026-03-20
> Based on a deep comparison of [docs.rhesis.ai](https://docs.rhesis.ai/) vs. [deepeval.com/docs](https://deepeval.com/docs/getting-started)

---

## Table of Contents

- [WP-1: Introduce Global Top Navigation Bar](#wp-1-introduce-global-top-navigation-bar)
- [WP-2: Restructure the Docs Sidebar Into Intent-Based Groups](#wp-2-restructure-the-docs-sidebar-into-intent-based-groups)
- [WP-3: Transform "Development" into a Top-Level "Contribute" Section](#wp-3-transform-development-into-a-top-level-contribute-section)
- [WP-4: Move SDK to Its Own Top-Nav Sidebar Context](#wp-4-move-sdk-to-its-own-top-nav-sidebar-context)
- [WP-5: Promote Guides to Top-Nav Standalone Context](#wp-5-promote-guides-to-top-nav-standalone-context)
- [WP-6: Implement Non-Clickable Section Headers in the Docs Sidebar](#wp-6-implement-non-clickable-section-headers-in-the-docs-sidebar)
- [WP-7: Create a Use-Case Decision Tree on the Getting Started Page](#wp-7-create-a-use-case-decision-tree-on-the-getting-started-page)
- [WP-8: Add Breadcrumbs Across All Pages](#wp-8-add-breadcrumbs-across-all-pages)
- [WP-9: Add Visual Section Icons to the Docs Sidebar](#wp-9-add-visual-section-icons-to-the-docs-sidebar)
- [WP-10: Clarify Platform vs. SDK on Relevant Pages](#wp-10-clarify-platform-vs-sdk-on-relevant-pages)
- [Priority & Dependency Map](#priority--dependency-map)

---

## WP-1: Introduce Global Top Navigation Bar

### Current State

The top navbar contains only: Rhesis logo (links to `/`), search bar, GitHub icon, Discord icon, and a mobile hamburger menu button. All content routing happens exclusively through the sidebar.

### Target State

Add a horizontal top navigation bar with distinct content-type destinations. This gives users immediate orientation and separates structurally different content categories — mirroring the pattern used by DeepEval (Docs | Guides | Tutorials | Integrations | Blog | Changelog | Cloud Docs).

### Proposed Top Nav Items

| Item | Target | Type |
|------|--------|------|
| **Docs** | `/getting-started` | Internal — loads Docs sidebar |
| **Guides** | `/guides` | Internal — loads Guides sidebar |
| **SDK** | `/sdk/installation` | Internal — loads SDK sidebar |
| **Glossary** | `/glossary` | Internal — single page, no sidebar |
| **SDK Reference** | `https://rhesis-sdk.readthedocs.io/en/latest/` | External — opens new tab |
| **Changelog** | `/development/changelog` | Internal — single page, no sidebar |
| **Contribute** | `/contribute` | Internal — loads Contribute sidebar |

Retain existing: Search bar, GitHub icon, Discord icon, dark mode toggle.

### Acceptance Criteria

1. Top nav renders on all documentation pages, sticky on scroll, responsive on mobile (collapses to hamburger menu).
2. The currently active top-level section is visually highlighted (e.g., underline or bold) so users always know which section they're in.
3. "SDK Reference" link opens in a new tab and is marked with an external-link icon.
4. Items promoted to the topbar (Guides, SDK, Glossary, Changelog, Contributing/Acknowledgments) are removed from the Docs sidebar to avoid duplication.
5. Switching between top-nav destinations loads a different sidebar context (Docs sidebar ≠ SDK sidebar ≠ Guides sidebar ≠ Contribute sidebar). Glossary and Changelog load without a sidebar (full-width content).
6. On mobile/tablet, all top nav items are accessible via the hamburger menu.
7. Search works globally across all top-nav contexts.

---

## WP-2: Restructure the Docs Sidebar Into Intent-Based Groups

### Current State

The Docs sidebar has 16 top-level entries mixing onboarding, product features, internal development docs, reference material, and meta pages. Key sections like "Guides" appear near the bottom after 120+ items. The monolithic "Platform" section alone has ~25 pages with confusing non-clickable separators ("Requirements," "Testing," "Results," "Development"). Conversation Simulation, Adversarial Testing, and Multi-modal Testing each occupy their own top-level slot, diluting the sidebar.

### Target State

The Docs sidebar (under the "Docs" topnav item) is reorganized into intent-based groups. The "Platform" section is dissolved entirely. Six new non-clickable section headers (see WP-6) organize the content: **Expectations**, **Define**, **Execute**, **Insights**, **Collaborate**, and **Setup**. SDK, Guides, Glossary, Changelog, and Contribute content lives under separate top-nav destinations.

### New Docs Sidebar Structure

```
Getting Started
  ├── Overview                          (/getting-started)
  ├── Setup Environment                 (/getting-started/setup-environment)
  ├── Connect Application               (/getting-started/connecting-application)
  └── Run Evaluations                   (/getting-started/run-evaluations)

Core Concepts                            (/concepts) — single page, no children

Product Tour                             (/product-tour) — single page, no children

───── Expectations ─────                 ← non-clickable section header (WP-6)
  Projects                               (/platform/projects)
  Knowledge                              (/platform/knowledge)
  Behaviors                              (/platform/behaviors)
  Metrics                                (/platform/metrics)

───── Define ─────                       ← non-clickable section header (WP-6)
  Test Generation                        (/platform/tests-generation)
  Tests                                  (/platform/tests)
  Test Sets                              ← collapsible
    ├── Overview                         (/platform/test-sets)
    ├── Import from File                 (/platform/test-sets/import-from-file)
    └── Import from Garak               (/platform/test-sets/import-from-garak)
  Playground                             (/platform/playground)

───── Execute ─────                      ← non-clickable section header (WP-6)
  Test Execution                         (/platform/test-execution)
  Test Runs                              (/platform/test-runs)
  Conversation Simulation                ← collapsible
    ├── Overview                         (/conversation-simulation)
    ├── Getting Started                  (/conversation-simulation/getting-started)
    ├── Examples & Use Cases             (/conversation-simulation/examples)
    ├── Configuration                    (/conversation-simulation/configuration)
    ├── Execution Trace                  (/conversation-simulation/execution-trace)
    └── Extending                        (/conversation-simulation/extending)
  Adversarial Testing                    ← collapsible
    ├── Overview                         (/adversarial-testing)
    ├── Polyphemus                       (/adversarial-testing/polyphemus)
    ├── Requesting Access                (/adversarial-testing/requesting-access)
    └── Using Polyphemus with SDK        (/adversarial-testing/sdk-usage)
  Multi-modal Testing                    ← collapsible
    └── Overview                         (/multimodal-testing)

───── Insights ─────                     ← non-clickable section header (WP-6)
  Results Overview                       (/platform/results-overview)
  Tracing                                ← collapsible
    ├── Overview                         (/tracing)
    ├── Getting Started                  (/tracing/setup)
    ├── Decorators                       (/tracing/decorators)
    ├── Custom Spans                     (/tracing/custom-spans)
    ├── Semantic Conventions             (/tracing/semantic-conventions)
    ├── Auto-Instrumentation             (/tracing/auto-instrumentation)
    ├── Multi-Agent Tracing              (/tracing/multi-agent)
    └── Conversation Tracing             (/tracing/conversation-tracing)

───── Collaborate ─────                  ← non-clickable section header (WP-6)
  Organizations & Team                   (/platform/organizations)
  Test Reviews                           (/platform/test-reviews)
  Tasks                                  (/platform/tasks)

───── Setup ─────                        ← non-clickable section header (WP-6)
  Endpoints                              ← collapsible
    ├── Overview                         (/platform/endpoints)
    ├── Managing Endpoints               (/platform/endpoints/management)
    ├── Auto-Configure                   (/platform/endpoints/auto-configure)
    ├── Single-Turn Endpoints            (/platform/endpoints/single-turn)
    ├── Multi-Turn Conversations         (/platform/endpoints/multi-turn-conversations)
    ├── SDK Endpoints                    (/platform/endpoints/sdk-endpoints)
    ├── Mapping Examples                 (/platform/endpoints/mapping-examples)
    └── Default Insurance Chatbot        (/platform/endpoints/default-chatbot)
  Models                                 (/platform/models)
  MCP                                    (/platform/mcp)
  API Tokens                             (/platform/api-tokens)

Deployment
  ├── Overview                           (/deployment)
  ├── Running Locally                    (/deployment/running-locally)
  └── Self-Hosting                       (/deployment/self-hosting)

Frameworks                               (/frameworks) — single page, no children

──── (visual separator) ────

Acknowledgments                          (/acknowledgments)
```

### Complete Page Migration Audit

Every current page accounted for:

| Current Location | New Location | Notes |
|---|---|---|
| Home `/` | Home `/` | Unchanged |
| Getting Started (4 pages) | Getting Started | Unchanged |
| Product Tour | Product Tour | Unchanged |
| Core Concepts | Core Concepts | Unchanged |
| Platform → Overview | Removed | Replaced by section headers; redirect to Getting Started or first child |
| Platform → Organizations & Team | Collaborate → Organizations & Team | |
| Platform → Projects | Expectations → Projects | |
| Platform → Knowledge | Expectations → Knowledge | |
| Platform → Behaviors | Expectations → Behaviors | |
| Platform → Metrics | Expectations → Metrics | |
| Platform → Generation | Define → Test Generation | |
| Platform → Playground | Define → Playground | |
| Platform → Tests | Define → Tests | |
| Platform → Test Sets (3 pages) | Define → Test Sets | |
| Platform → Test Execution | Execute → Test Execution | |
| Platform → Results Overview | Insights → Results Overview | |
| Platform → Test Runs | Execute → Test Runs | |
| Platform → Test Reviews | Collaborate → Test Reviews | |
| Platform → Tasks | Collaborate → Tasks | |
| Platform → Endpoints (8 pages) | Setup → Endpoints | |
| Platform → Models | Setup → Models | |
| Platform → MCP | Setup → MCP | |
| Platform → API Tokens | Setup → API Tokens | |
| SDK (entire section, 15+ pages) | Moved to SDK topnav (WP-4) | |
| Tracing (8 pages) | Insights → Tracing | |
| Conversation Simulation (6 pages) | Execute → Conversation Simulation | |
| Adversarial Testing (4 pages) | Execute → Adversarial Testing | |
| Multi-modal Testing (1 page) | Execute → Multi-modal Testing | |
| Frameworks | Frameworks | Unchanged |
| Development (50+ pages) | Moved to Contribute topnav (WP-3) | |
| Guides (5 pages) | Moved to Guides topnav (WP-5) | |
| Glossary | Moved to Glossary topnav (WP-1) | |
| Contributing | Moved to Contribute topnav (WP-3) | |
| Acknowledgments | Bottom of Docs sidebar | |
| SDK Reference (external) | Moved to topnav (WP-1) | |
| Changelog | Moved to Changelog topnav (WP-1) | |

### Acceptance Criteria

1. The "Platform" section no longer exists as a sidebar group — all its pages are distributed across the six new intent-based groups.
2. Each of the six groups (Expectations, Define, Execute, Insights, Collaborate, Setup) appears as a non-clickable section header (see WP-6) with its child pages listed beneath it.
3. No non-clickable plain-text separators from the old Platform section remain ("Requirements," "Testing," "Results," "Development").
4. Maximum nesting depth is 3 levels (e.g., Execute → Adversarial Testing → Polyphemus).
5. All sections with children are collapsed by default except the one containing the current page.
6. SDK, Guides, Glossary, Changelog, Contributing, and Development pages do NOT appear in the Docs sidebar.
7. Every existing URL either continues to work at its current path or has a 301 redirect to the new path.
8. Total visible top-level items when all collapsible sections are collapsed is ≤ 15 (including section headers).

---

## WP-3: Transform "Development" into a Top-Level "Contribute" Section

### Current State

"Development" is a sidebar section containing 50+ pages of internal architecture documentation:
- **Backend:** 22 pages (Soft Deletion, Cascade Operations, Database Field Encryption, Encryption Troubleshooting, OData Query Guide, etc.)
- **Frontend:** 10 pages
- **Worker:** 12 pages (Multi-Worker RPC, Chord Management, Chord Monitoring Quick Reference, GKE Troubleshooting, etc.)
- **Tracing System:** 4 pages
- **Polyphemus:** 1 page
- **Connector:** 1 page

Plus Contributing guidelines, Telemetry, and Environment Variables. This content is primarily for open-source contributors and core engineers, not product users, yet it sits at the same level as user-facing docs.

### Target State

"Contribute" appears as a top-level item in the global nav (per WP-1). It loads its own dedicated sidebar context, entirely decoupled from user-facing docs. Overly granular pages are consolidated.

### Proposed Contribute Sidebar

```
Contribute (top nav → /contribute)

  Overview                               (why contribute, CLA, community norms)
  Development Setup
  Coding Standards
  Managing Documentation

  ──── Architecture ────                 (non-clickable section header)
  Frontend
    ├── Overview
    ├── Getting Started
    ├── Architecture
    ├── Routing
    ├── Component Library
    ├── State Management
    ├── API Integration
    ├── Endpoint Configuration
    ├── Authentication
    └── Testing
  Backend
    ├── Overview
    ├── Getting Started
    ├── Architecture
    ├── API Structure
    ├── Database Models
    ├── Data Lifecycle               (merge: Soft Deletion + Cascade Operations)
    ├── User Configuration           (merge: User Settings + Email Notifications)
    ├── Authentication
    ├── Multi-tenancy
    ├── Background Tasks
    ├── Test Run & Result Statuses   (merge: Test Result Stats + Test Result Status + Test Run Status)
    ├── Test Reviews
    ├── OData Query Guide
    ├── Environment Configuration
    ├── Security                     (merge: Security Features + Security Improvements)
    ├── Database Encryption          (merge: Database Field Encryption + Encryption Troubleshooting)
    ├── Development Workflow
    └── Deployment
  Worker
    ├── Overview
    ├── Architecture                 (absorb: Multi-Worker RPC + Background Tasks)
    ├── Test Execution
    ├── Test Types
    ├── Execution Modes
    ├── Chord Management             (merge: Chord Management + Chord Monitoring Quick Ref)
    └── Troubleshooting              (merge: Troubleshooting + GKE Troubleshooting)
  Tracing System
    ├── Overview
    ├── Architecture
    ├── Trace Lifecycle
    └── Data Structures
  Polyphemus → Overview
  Connector → Overview

  ──── Reference ────                    (non-clickable section header)
  Environment Variables
  Telemetry
```

### Page Consolidation Summary

| Merge Target | Pages Merged | Reduction |
|---|---|---|
| Backend: Data Lifecycle | Soft Deletion + Cascade Operations | 2 → 1 |
| Backend: User Configuration | User Settings + Email Notifications | 2 → 1 |
| Backend: Test Run & Result Statuses | Test Result Statistics + Test Result Status + Test Run Status | 3 → 1 |
| Backend: Security | Security Features + Security Improvements | 2 → 1 |
| Backend: Database Encryption | Database Field Encryption + Encryption Troubleshooting | 2 → 1 |
| Worker: Architecture | Architecture + Multi-Worker RPC + Background Tasks | 3 → 1 |
| Worker: Chord Management | Chord Management + Chord Monitoring Quick Reference | 2 → 1 |
| Worker: Troubleshooting | Troubleshooting + GKE Troubleshooting | 2 → 1 |
| **Total** | **18 pages** | **→ 8 pages (10 removed)** |

### Acceptance Criteria

1. "Contribute" appears in the global top nav and loads its own sidebar.
2. The Contribute sidebar does not contain any user-facing docs (Platform, Tracing, etc.).
3. The Docs sidebar does not contain any Development or Contributing pages.
4. Backend section is consolidated from 22 pages to ≤ 16 through merges as specified.
5. Worker section is consolidated from 12 pages to ≤ 7.
6. All existing `/development/*` URLs still work or 301-redirect to `/contribute/*` equivalents.
7. The Contribute overview page explains how to get involved, links to the repo, and provides a first-time contributor quick-start path.
8. No single Contribute sub-section exceeds 12 child pages.
9. The standalone `/contributing` page redirects to `/contribute`.

---

## WP-4: Move SDK to Its Own Top-Nav Sidebar Context

### Current State

SDK is a section inside the Docs sidebar with 15+ pages across sub-groups (Entities, Metrics, Connector).

### Target State

SDK becomes its own top-nav destination (per WP-1) with a dedicated sidebar, giving Python developers a focused reference context.

### SDK Sidebar (Standalone)

```
SDK (top nav → /sdk/installation)

  Installation & Setup            (/sdk/installation)
  Rhesis Client                   (/sdk/client)
  Entities                        ← collapsible
    ├── Overview                  (/sdk/entities)
    ├── Projects                  (/sdk/entities/projects)
    ├── Models                    (/sdk/entities/models)
    ├── Test Sets & Tests         (/sdk/entities/test-sets)
    ├── Test Attributes           (/sdk/entities/test-attributes)
    ├── Test Runs & Results       (/sdk/entities/test-runs)
    ├── Files                     (/sdk/entities/files)
    ├── Status                    (/sdk/entities/status)
    └── Endpoints                 (/sdk/entities/endpoints)
  Test Execution                  (/sdk/execution)
  Models                          (/sdk/models)
  Synthesizers                    (/sdk/synthesizers)
  Metrics                         ← collapsible
    ├── Overview                  (/sdk/metrics)
    ├── Single-Turn               (/sdk/metrics/single-turn)
    └── Conversational            (/sdk/metrics/conversational)
  Connector                       ← collapsible
    ├── Overview                  (/sdk/connector)
    ├── Input/Output Mapping      (/sdk/connector/mapping)
    ├── Advanced Mapping          (/sdk/connector/serializers)
    ├── Parameter Binding         (/sdk/connector/binding)
    └── Examples                  (/sdk/connector/examples)
```

### Acceptance Criteria

1. Clicking "SDK" in the top nav loads the SDK sidebar and navigates to `/sdk/installation`.
2. The SDK sidebar contains only SDK-related pages — no Platform, Tracing, or other content.
3. The Docs sidebar does not list any `/sdk/*` pages.
4. All existing `/sdk/*` URLs continue to work without redirects.
5. SDK sidebar has a maximum of 3 nesting levels and ≤ 8 top-level entries when collapsed.
6. Each SDK page includes a breadcrumb: `SDK > [Sub-section] > [Page]`.

---

## WP-5: Promote Guides to Top-Nav Standalone Context

### Current State

Guides is a sidebar section near the bottom of the Docs sidebar (position 14 of 16) with 5 entries, positioned after the massive Development section.

### Target State

Guides becomes a top-nav destination with its own sidebar context.

### Guides Sidebar

```
Guides (top nav → /guides)

  Overview                                        (/guides)
  Quick Start: Testing in 10 Minutes              (/guides/quick-start-guide)
  Building Custom Metrics with the Rhesis SDK     (/guides/custom-metrics)
  Integrating Rhesis SDK into CI/CD               (/guides/ci-cd-integration)
  Testing User Journeys of AI Agents              (/guides/testing-user-journeys)
```

### Acceptance Criteria

1. "Guides" appears in the global top nav and loads its own sidebar context.
2. The Guides sidebar lists only guide pages.
3. Guides are removed from the Docs sidebar.
4. All existing `/guides/*` URLs work without redirects.
5. The Guides overview page lists all guides with a one-sentence description each.
6. Each guide page includes breadcrumbs: `Guides > [Guide Name]`.

---

## WP-6: Implement Non-Clickable Section Headers in the Docs Sidebar

### Current State

The Platform section uses plain-text non-clickable list items as separators ("Requirements," "Testing," "Results," "Development"). These render identically to regular nav items but have no link, creating a broken affordance. The rest of the sidebar has no visual grouping mechanism beyond collapsible sections.

### Target State

Implement styled, non-clickable section headers in the Docs sidebar to visually group the six intent-based categories: **Expectations**, **Define**, **Execute**, **Insights**, **Collaborate**, and **Setup**. These follow the pattern used by DeepEval, where section headers like "Getting Started," "LLM Evals," "Eval Metrics" etc. are bold labels with an icon and a collapsible chevron that organize child items but are not themselves links to any page.

### Design Specification

Each section header should:

- **Be bold text**, visually heavier than regular sidebar links (e.g., font-weight 600–700).
- **Include a small icon** to the left (per WP-9) for quick visual scanning.
- **Include a chevron toggle** (▸/▾) on the right to collapse/expand the child items beneath it.
- **NOT be a link** — clicking the header text or chevron only toggles expand/collapse; it does not navigate to any page.
- **Have extra vertical spacing** above (e.g., 16–24px padding-top) to create clear visual separation between groups.
- **Not show a pointer cursor or hover underline** — must be visually distinct from clickable links.
- **Not be announced as links** by screen readers — use appropriate ARIA roles (e.g., `role="heading"` or a `<button>` with `aria-expanded`).

### Section Headers to Implement

| Header | Icon suggestion | Child items |
|--------|----------------|-------------|
| Expectations | 🎯 target / clipboard-check | Projects, Knowledge, Behaviors, Metrics |
| Define | ✏️ pencil / edit | Test Generation, Tests, Test Sets, Playground |
| Execute | ▶️ play-circle / terminal | Test Execution, Test Runs, Conversation Simulation, Adversarial Testing, Multi-modal Testing |
| Insights | 📊 bar-chart / eye | Results Overview, Tracing |
| Collaborate | 👥 users / message-circle | Organizations & Team, Test Reviews, Tasks |
| Setup | ⚙️ settings / wrench | Endpoints, Models, MCP, API Tokens |

### Reference: DeepEval Pattern

DeepEval uses this exact pattern for its sidebar sections ("Getting Started," "LLM Evals," "Eval Metrics," "Prompt Optimization," "Synthetic Data Generation," "Red-Teaming," "Benchmarks," "Others"). Each is:
- Bold text with an emoji/icon prefix
- Collapsible via chevron
- Not a link to any page
- Separated by vertical whitespace from the section above

### Acceptance Criteria

1. All six section headers (Expectations, Define, Execute, Insights, Collaborate, Setup) render in the Docs sidebar as non-clickable, bold labels with expand/collapse chevrons.
2. Section headers are visually distinct from clickable links: no pointer cursor, no hover underline, bolder font weight, extra top padding.
3. Clicking a section header toggles its children — it does NOT navigate to any URL.
4. All old non-clickable separators from the Platform section ("Requirements," "Testing," "Results," "Development") are removed.
5. Screen readers do not announce section headers as links. They are either `<button>` elements with `aria-expanded` or elements with `role="heading"`.
6. Each section header has a small icon to the left (consistent with WP-9).
7. Vertical spacing above each section header is ≥ 12px, creating clear visual separation between groups.
8. Sections are collapsible and default to collapsed state (except the section containing the current page).

---

## WP-7: Create a Use-Case Decision Tree on the Getting Started Page

### Current State

The Getting Started overview page has three link-out cards (Setup Environment, Connect Application, Run Evaluations) plus a video embed. There is no segmentation by use case and no inline code sample.

### Target State

Embed a quick-start code block and a use-case chooser on the Getting Started overview page.

### Additions

1. **Inline quick-install block** — a code snippet showing `pip install rhesis-sdk` and a 5–10 line working example (e.g., create a test set and run an evaluation) directly on the page, before the existing three-step cards.

2. **"What are you building?" cards** — after the three steps, a section with cards for primary use cases:
   - **Testing AI Agents** → agent testing guide + relevant pages
   - **Testing RAG Pipelines** → relevant metrics, test generation
   - **Adversarial & Safety Testing** → Adversarial Testing section
   - **CI/CD Integration** → CI/CD guide
   - **Conversation Testing** → Conversation Simulation section

Each card should have a 1-sentence description and a list of 2–3 things the user will accomplish.

### Acceptance Criteria

1. The Getting Started overview page contains a visible, copy-paste-ready `pip install rhesis-sdk` command and a working code example of ≤ 15 lines.
2. The code example runs successfully when pasted into a fresh Python environment with the SDK installed.
3. A "What are you building?" section appears on the page with at least 4 use-case cards.
4. Each use-case card links to at least 2 relevant documentation pages.
5. The inline code block appears above the fold or within one scroll on a 1080p display.
6. The existing three-step flow (Setup, Connect, Run) is preserved below the quick-start.

---

## WP-8: Add Breadcrumbs Across All Pages

### Current State

The homepage shows a single "Home" breadcrumb. Inner page breadcrumb behavior is inconsistent.

### Target State

Every documentation page displays a full breadcrumb trail reflecting the new hierarchy.

### Format

`[Context] > [Section Header] > [Sub-group] > [Page Title]`

### Examples

- `Docs > Execute > Adversarial Testing > Polyphemus`
- `SDK > Connector > Parameter Binding`
- `Contribute > Backend > Architecture`
- `Docs > Expectations > Behaviors`
- `Guides > Quick Start: Testing in 10 Minutes`

### Acceptance Criteria

1. Every page (including the homepage) displays a breadcrumb trail.
2. Breadcrumbs match the sidebar hierarchy exactly (same labels, same nesting).
3. Every segment except the current page is a clickable link.
4. The current page segment is displayed but not clickable (styled as plain text or muted).
5. Breadcrumbs render consistently on mobile and desktop.
6. Breadcrumbs reflect the top-nav context (Docs, SDK, Guides, Contribute).
7. Non-clickable section headers (Expectations, Define, etc.) appear in breadcrumbs as non-linked text, since they have no target page.

---

## WP-9: Add Visual Section Icons to the Docs Sidebar

### Current State

All sidebar sections are plain text with chevron expand/collapse arrows. No visual differentiation between sections.

### Target State

Add small icons to each top-level sidebar item and to each non-clickable section header (per WP-6) to provide visual landmarks. Follow the DeepEval pattern where each section header has an emoji or icon prefix.

### Proposed Icon Assignments

| Sidebar Item | Icon |
|---|---|
| Getting Started | 🚀 rocket / play |
| Core Concepts | 💡 lightbulb / book |
| Product Tour | 🧭 compass / video |
| **Expectations** (section header) | 🎯 target / clipboard-check |
| **Define** (section header) | ✏️ pencil / edit |
| **Execute** (section header) | ▶️ play-circle / terminal |
| **Insights** (section header) | 📊 bar-chart / eye |
| **Collaborate** (section header) | 👥 users / message-circle |
| **Setup** (section header) | ⚙️ settings / wrench |
| Deployment | ☁️ cloud / server |
| Frameworks | 🧩 puzzle-piece |

### Acceptance Criteria

1. Every top-level sidebar item and every non-clickable section header has an icon to the left of the label.
2. Icons are consistent in size (e.g., 16×16px) and style (all from the same icon set or all emoji).
3. Icons do not break text alignment — labels remain left-aligned and uniform.
4. Icons are purely decorative and not announced by screen readers (`aria-hidden="true"`).
5. Icons render correctly in both light and dark mode.

---

## WP-10: Clarify Platform vs. SDK on Relevant Pages

### Current State

The Docs and SDK sections both cover similar concepts (test sets, endpoints, models, test execution) for different audiences (web UI users vs. Python developers). No guidance helps users understand which section is relevant to them.

### Target State

Add cross-reference notices on relevant pages to help users self-select.

### Acceptance Criteria

1. At least the first page under each of the six Docs section headers includes a note like: "Prefer programmatic access? See the [SDK section](/sdk/installation)" where relevant.
2. The SDK Installation page includes a reciprocal note: "Prefer the web interface? See the [Platform documentation](/getting-started)" with links to relevant Docs groups.
3. Pages under Define link to SDK Entities for programmatic test set creation.
4. Pages under Setup link to SDK Connector for programmatic endpoint configuration.
5. Disambiguation notes are placed within the first screen of content on each page.
6. Language is user-facing, not internal jargon, and helps a new user self-select within 10 seconds.

---

## Priority & Dependency Map

| Work Package | Priority | Depends on | Effort | Summary |
|---|---|---|---|---|
| **WP-1**: Global Top Navigation | P0 | — | Medium | Add Docs, Guides, SDK, Glossary, SDK Ref, Changelog, Contribute to topnav |
| **WP-2**: Docs Sidebar Restructure | P0 | WP-1 | Large | Dissolve Platform into 6 intent groups; remove SDK/Guides/Glossary/Dev from sidebar |
| **WP-3**: Development → Contribute | P0 | WP-1 | Large | Dedicated Contribute topnav + sidebar; consolidate 50+ pages |
| **WP-4**: SDK Standalone Context | P0 | WP-1 | Small | Move SDK to its own topnav sidebar |
| **WP-5**: Guides Standalone Context | P0 | WP-1 | Small | Move Guides to its own topnav sidebar |
| **WP-6**: Non-Clickable Section Headers | P0 | WP-2 | Medium | Implement 6 styled section headers (Expectations, Define, Execute, Insights, Collaborate, Setup) |
| **WP-7**: Use-Case Decision Tree | P1 | WP-2 | Medium | Inline code + use-case cards on Getting Started |
| **WP-8**: Breadcrumbs | P1 | WP-2 + WP-3 + WP-4 | Medium | Full breadcrumb trails on all pages |
| **WP-9**: Section Icons | P2 | WP-6 | Small | Visual icons on sidebar headers and top-level items |
| **WP-10**: Platform vs. SDK Disambiguation | P2 | WP-2 + WP-4 | Small | Cross-reference notes on overview pages |

### Execution Order

```
Phase 1 (Foundation):      WP-1
Phase 2 (Structure):       WP-2 + WP-3 + WP-4 + WP-5 + WP-6  (parallelizable after WP-1)
Phase 3 (Content & UX):    WP-7 + WP-8
Phase 4 (Polish):          WP-9 + WP-10
```

WP-1 is the foundation — it establishes the multi-context navigation architecture. WP-2 through WP-6 can then be worked in parallel since they each affect a separate concern. WP-7 and WP-8 require the new structure to be in place before content can be written. WP-9 and WP-10 are polish items.
