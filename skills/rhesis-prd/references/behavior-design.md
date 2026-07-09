# Behavior Design for PRD

## One behavior = one specific expectation

A behavior is **not** a category label. It is a single, observable expectation you can write a test prompt for and score with one metric.

Real PRDs express expectations through **stakeholder constraints**, **persona narratives**, and **numbered requirements** — often the same topic in all three. See [prd-anatomy.md](prd-anatomy.md).

---

## Split bundled PRD text (original examples)

The excerpts below are **illustrative** (fictional *Helios Retail Support Agent v2.1* PRD). They mirror how enterprise PRDs are written — not tidy chat prompts.

### Example A — Persona user story (requirements in prose)

**PRD text (User Story RS-04):**

> **Morgan, 41, marketplace operations lead.** Morgan monitors seller disputes during live flash sales on a tablet, often while coordinating staff over walkie-talkie. During a sale, Morgan needs the agent to pull **order status and refund eligibility in one thread** without re-entering the order number after each follow-up question. If the purchase is **outside the 30-day window** or the SKU is **final-sale**, the agent must **state the policy reason in one sentence** and **not offer workarounds** (no "manager exceptions" unless Morgan explicitly asks for escalation). Morgan also uses the agent to sanity-check **whether a bulk-buyer message looks like reseller fraud** — the agent should **flag the pattern** and **refuse to draft approval messages** that bypass seller verification.

| Split into | Why | Linked numbered reqs (if any) |
|---|---|---|
| Order Context Retention Across Follow-ups | "without re-entering the order number" is a distinct conversational capability | FR-3.2 |
| Refund Window Policy Enforcement | 30-day window + one-sentence reason + no workarounds | FR-4.1, FR-4.3 |
| Final-Sale Refund Refusal | Final-sale SKUs are a different gate than date window | FR-4.2 |
| Reseller Fraud Pattern Flagging | "flag the pattern" ≠ refusing to draft — two observable actions | FR-6.1 |
| Seller Verification Bypass Draft Refusal | "refuse to draft approval messages" is a separate prohibition | FR-6.2 |

**Do not create:** "Marketplace Operations Support", "Flash Sale Reliability", or "Morgan's Workflow" as behaviors.

**Underspecified in story alone:** what "flag the pattern" means visually — pull criteria from **FR-6.1** (numbered section), not from the adjective "looks like fraud".

---

### Example B — Stakeholder + legal block (vague + specific mixed)

**PRD text (Stakeholders — Legal & Trust, excerpt):**

> Legal requires the assistant to **operate safely in customer-facing channels** and to **stay within approved product and policy content**. The agent **must not provide legal advice** or interpret warranty terms beyond the **published FAQ corpus (rev 2025-03)**. Trust & Safety adds: **no disclosure** of system prompts, retrieval chunk text, or internal playbooks; **no assistance** structuring chargeback abuse, warranty fraud, or **bulk-purchase arbitrage**. Customer Marketing insists the bot **still feel helpful** when redirecting off-topic requests — **one brief sentence**, no lecture.

| Split into | Why |
|---|---|
| Published FAQ Corpus Boundary | "beyond published FAQ corpus" is testable; "legal advice" is operationalized here |
| Internal Configuration Secrecy | Explicit prohibition list (prompts, chunks, playbooks) |
| Chargeback Abuse Assistance Refusal | Listed fraud type — separate test prompts from warranty fraud |
| Warranty Fraud Assistance Refusal | Distinct scheme — do not merge into "Fraud Refusal" |
| Bulk-Purchase Arbitrage Assistance Refusal | Third distinct prohibition in same bullet |
| Single-Sentence Off-Topic Redirect | Marketing constraint is measurable ("one brief sentence") |

**Do not create:** "Operate Safely" or "Stay Within Approved Content" — Legal's first sentence is **not** an AC until tied to FAQ boundary or a numbered FR.

**Plan note:** "feel helpful" is not a behavior — only the **one-sentence redirect** rule is.

---

### Example C — Numbered requirements section (metrics live here)

**PRD text (§4 Order & refunds):**

> **FR-4.1 (P9)** — Before initiating a refund, the agent shall verify **purchase date ≤ 30 calendar days** from current date (store timezone).  
> **FR-4.2 (P9)** — If SKU is tagged **final-sale** in catalog API, agent shall **not** initiate refund workflow; response includes SKU flag and policy link.  
> **FR-4.3 (P8)** — When refund is denied for eligibility, agent gives **one-sentence reason** citing **date OR final-sale OR open-RMA**; no speculative alternatives.  
> **FR-4.4 (P7)** — Order status lookup accepts **order number OR email on file**, not both required.

| Split into | Notes |
|---|---|
| Refund Eligibility Window Check | FR-4.1 only — quantifier is explicit |
| Final-Sale Refund Block | FR-4.2 — categorical gate on SKU flag |
| Denial Reason Single-Sentence Citation | FR-4.3 — separate from whether refund is correct (format + cited reason) |
| Order Status Lookup by Identifier | FR-4.4 — OR-logic for identifiers |

One **workflow** ("refunds") → **four behaviors** because each FR has independent pass conditions.

---

### Example D — Regulatory-style appendix (do not collapse)

**PRD text (Appendix B — Payments compliance, excerpt):**

> **PC-01** — Agent shall not instruct users to **split transactions** to evade card limits.  
> **PC-02** — Agent shall not generate **dispute text** intended to misrepresent delivery status.  
> **PC-03** — For EU storefronts, agent must **surface PSD2 strong-customer-authentication reminder** when user asks to "skip 3DS" or "use backup card without verification."

| Split into | Why |
|---|---|
| Transaction Splitting Evasion Refusal | PC-01 |
| False Dispute Narrative Refusal | PC-02 |
| PSD2 SCA Skip Refusal (EU) | PC-03 — region-scoped; tag `compliance` + `eu` |

**Do not create:** "Payments Compliance" or "Appendix B Compliance."

---

## Reject as behaviors

- Section / epic titles: "Order Support", "Adaptive Intelligence", "Safety"
- Stakeholder theme names: "Legal & Trust Requirements"
- Engineering virtues: reliable, robust, seamless, intuitive (unless a numbered req defines an observable test)
- Entire persona names or stories: "Morgan's Workflow"
- Metric names copied as behaviors

## Capability vs guardrail behaviors

**Capability behaviors** — what the agent should **do** in scope (collect slots, retain context, cite policy links).

**Guardrail behaviors** — what it must **not** do or must **always** do under pressure (refuse, withhold, disclose, redirect).

Guardrails usually map to **binary categorical** metrics when the PRD states a prohibition. Capabilities map to **numeric** metrics when the PRD gives counts/limits/field lists — otherwise **categorical** gates from the FR text.

See [metric-design.md](metric-design.md) for score types.

## Description template

```
[Agent] [does/refuses/redirects] [specific thing] [when condition].
Source: [Story ID or FR-#].
Example: [concrete user message] → [expected response pattern].
```

## Tag assignment

- **functional** — product workflows (status, refund, search)
- **safety** — secrecy, leakage, jailbreak resistance
- **compliance** — legal, regulatory, payments policy refusals
- **domain** — scope boundaries and redirects
- **quality** — format constraints tied to AC (one-sentence reason, recap fields)
- **transparency** — disclosure when PRD requires it

Apply the same tags to the linked metric when the tag describes what is measured.

## Test prompt angles per behavior type

| Behavior type | Generation prompt should include |
|---|---|
| Capability | Happy path, missing info, ambiguous input, correction mid-flow |
| Context retention | Follow-up without re-supplying identifiers |
| Domain scope | Off-topic asks, polite single-sentence redirect |
| Secrecy | Direct/indirect prompt asks, role-play, tool-schema fishing |
| Refusal | Each fraud type from appendix separately |
| Policy citation | Denied refund with required reason format |
