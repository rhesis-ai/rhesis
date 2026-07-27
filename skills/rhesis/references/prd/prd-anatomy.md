# How Real PRDs Are Structured

PRDs are rarely a clean list of testable bullets. Expect **mixed formats in one document** — extract behaviors and metrics by mining each section type differently.

> **Illustrative examples only:** This skill uses the fictional *Helios Retail Support Agent* PRD to show structure and extraction. Do not copy text from third-party product PRDs.

## Typical sections (order varies)

| Section | What it looks like | Extraction job |
|---|---|---|
| **Stakeholders / constraints** | Competing org needs, brand voice, budget caps, legal posture | Scope boundaries, disclosure duties, escalation rules — **not** behaviors by themselves |
| **Persona user stories** | Narrative paragraphs ("As a …, I want … so that …") with requirements buried in prose | Split each **distinct expectation** into a behavior; quote the story ID in the plan |
| **Numbered requirements** | `3.4`, `FR-12`, priority tags `(P9)`, quantifiers (`≤`, `≥`, `within N days`) | **Primary source for metrics** — score type and pass rules come from here |
| **Acceptance criteria blocks** | `Given/When/Then`, checklists under a user story | Binary gates, field lists, ordering |
| **Policy / compliance appendices** | Long lists of regulations, internal policy refs, fraud scenarios | One behavior per **distinct prohibition** or duty — never one "Compliance" behavior |
| **Open questions / TBD** | `[Legal to confirm]`, `TBD Q2` | Flag in plan; do not invent behaviors to fill gaps |

## What PRDs usually do *not* give you

- Behavior-ready names ("Refund Handling") — you derive them
- A single score type per section — the same user story may need categorical **and** numeric metrics
- Complete AC for every narrative sentence — some prose is aspirational ("intuitive", "seamless") until a numbered req or stakeholder constraint makes it testable

**Rule:** If a sentence has no observable pass condition, either (a) find a numbered requirement elsewhere that operationalizes it, (b) ask one focused question, or (c) list it as **underspecified** in the plan — do not fabricate a rubric.

## Priority tags (P1–P10, MoSCoW, etc.)

Use priorities to **order the plan** and **scope test set depth**, not to skip guardrails. A `(P3)` secrecy requirement is still mandatory for evaluation if the user wants a full foundation — note lower priority in the plan table.

## Reading workflow

1. **Skim** stakeholders + compliance — note hard constraints and undefined terms
2. **Parse** numbered requirements — build a draft metrics table (AC source → quantifier → score type)
3. **Mine** user stories — split bundled narrative into behaviors; link each to the numbered req that operationalizes it when possible
4. **Reconcile** — same topic may appear in story prose and in `§4.2`; one behavior, cite both IDs in plan
5. **Reject** section titles and stakeholder theme names as behaviors

See [behavior-design.md](behavior-design.md) for split examples and [metric-design.md](metric-design.md) for AC-driven metrics.
