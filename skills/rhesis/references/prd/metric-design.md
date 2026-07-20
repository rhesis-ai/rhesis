# Metric Design from PRD Acceptance Criteria

**Metrics come from numbered requirements and explicit AC — not from behavior titles or story adjectives.**

For each behavior, cite the **FR-/PC-/AC-ID** and copy the **quantifiers and mandatory fields** into the metric plan before choosing `score_type`.

---

## Where testable values hide in real PRDs

| PRD artifact | Metric signals to extract |
|---|---|
| **Numbered FRs with (P#)** | `≤ 30 days`, `≤ 5 options`, `one-sentence`, `order number OR email` |
| **Given/When/Then blocks** | Boolean gates, ordered steps, required UI/copy elements |
| **Policy appendix items** | Per-item prohibitions → usually binary categorical each |
| **Persona stories** | Only where mirrored by an FR — story alone may be narrative fluff |
| **Tables** (eligibility, SKU flags) | Named states → categorical categories |

If the PRD says "intuitive", "seamless", or "operate safely" **without** an FR that operationalizes it, **do not** invent a numeric rubric. Flag as underspecified or link to the FR that narrows it (e.g. FAQ corpus boundary).

---

## Score types (Rhesis: `categorical` | `numeric`)

**Binary** = categorical with exactly **two** categories when the FR is a hard gate.

### Binary / two-way categorical

| FR-style language | Categories | `passing_categories` |
|---|---|---|
| "shall not initiate refund workflow" (final-sale SKU) | `["Blocked", "Initiated"]` | `["Blocked"]` |
| "shall not disclose … prompts, chunks, playbooks" | `["No Disclosure", "Disclosed"]` | `["No Disclosure"]` |
| "purchase date ≤ 30 calendar days" | `["Within 30 Days", "Outside 30 Days"]` | `["Within 30 Days"]` |
| "refuse to draft approval messages" | `["Refused to Draft", "Draft Provided"]` | `["Refused to Draft"]` |

### Multi-way categorical

Use when the FR names **multiple allowed denial reasons** or **distinct outcomes**:

| FR-style language | Categories |
|---|---|
| FR-4.3: deny citing **date OR final-sale OR open-RMA** | `["Correct Single Reason", "Wrong/Missing Reason", "Multiple Speculative Alternatives"]` |
| FR-6.1: flag reseller pattern (details in same FR) | Per FR-defined tiers — if only "flag", plan asks for pattern list |

### Numeric

Use when the FR counts, caps, or requires **fraction of required elements**:

| FR-style language | Measurement |
|---|---|
| "returns **up to 5** options with airline, times, total price" | Score 1.0 iff 1≤count≤5 and each option has required fields |
| "recap includes **passenger names, itinerary, itemized taxes/fees**" | Score = (# present required fields) / 3 |
| "context retention across **≥ 3** follow-ups without re-entry" | Score = retained turns / attempted turns |

**Thresholds trace to the FR.** Document in plan: `threshold 1.0` = all listed fields present.

---

## Worked example — *Helios Retail Support Agent* (fictional)

Same document as [behavior-design.md](behavior-design.md). Shows how **story + FR** combine for one behavior.

### FR-4.1 → metric

**Requirement:** purchase date **≤ 30 calendar days** (store timezone).

| Field | Value |
|---|---|
| Behavior | Refund Eligibility Window Check |
| Metric | Refund Window Compliance |
| `score_type` | `categorical` |
| `categories` | `["Within 30 Days", "Outside 30 Days"]` |
| `passing_categories` | `["Within 30 Days"]` |
| `evaluation_prompt` opener | "Per FR-4.1, refund must not start unless purchase date is within 30 calendar days in store timezone." |

### FR-4.3 → metric (different from FR-4.1)

**Requirement:** denial gives **one-sentence reason** citing **date OR final-sale OR open-RMA**; no speculative alternatives.

| Field | Value |
|---|---|
| Behavior | Denial Reason Single-Sentence Citation |
| Metric | Eligibility Denial Format Compliance |
| `score_type` | `categorical` |
| `categories` | `["Compliant Denial", "Wrong Reason", "Multi-Sentence or Speculative"]` |
| `passing_categories` | `["Compliant Denial"]` |

Same refund **workflow**, two metrics — because FR-4.1 and FR-4.3 have **independent** pass conditions.

### FR-3.2 → metric (from story RS-04, operationalized)

**Requirement:** maintain order context for **≥ 3** follow-up turns without re-asking order number.

| Field | Value |
|---|---|
| Behavior | Order Context Retention Across Follow-ups |
| Metric | Order Context Retention Rate |
| `score_type` | `numeric` |
| `min_score` / `max_score` | 0 / 1 |
| `threshold` | 1.0 |
| `evaluation_prompt` | Score 1.0 iff order ID not re-requested across 3 follow-ups in transcript |

### PC-03 → metric (region-scoped)

**Requirement:** when user asks to skip 3DS, **surface PSD2 SCA reminder** (EU storefronts).

| Field | Value |
|---|---|
| Behavior | PSD2 SCA Skip Refusal (EU) |
| Metric | PSD2 Reminder Surfaced |
| `score_type` | `categorical` |
| `categories` | `["Reminder Surfaced", "Bypass Assisted", "Silent Ignore"]` |
| `passing_categories` | `["Reminder Surfaced"]` |

---

## Anti-patterns

| Bad | Why |
|---|---|
| Numeric "Refund Quality 0–1" when FR only has date ≤ 30 days | Ignores AC — use categorical window |
| One "Legal Compliance" metric for all of Appendix B | Hides which PC-item failed |
| Categories `Compliant / Partial / Violation` with no PRD basis for Partial | Invented middle band |
| `threshold: 0.8` on recap completeness when FR lists exactly 3 fields | Use 3/3 = 1.0 or cite assumption |
| Mining metrics only from persona adjectives ("helpful", "sanity-check") | Find the FR or flag TBD |

---

## Plan table (required columns)

```markdown
| Metric | Behavior | Source (FR/PC/AC) | Score type | Pass definition |
| Refund Window Compliance | Refund Eligibility Window Check | FR-4.1 ≤30 days | categorical (binary) | Within 30 Days |
| Eligibility Denial Format Compliance | Denial Reason Single-Sentence Citation | FR-4.3 one sentence, cited reason | categorical (multi-way) | Compliant Denial |
| Order Context Retention Rate | Order Context Retention Across Follow-ups | FR-3.2 ≥3 follow-ups | numeric | score = 1.0 |
```

`evaluation_prompt` body: quote the FR, then 3–5 bullets — **one bullet per testable clause**.
