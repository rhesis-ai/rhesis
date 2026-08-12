# Metric authoring — writing a metric someone can trust

> **Docs:** https://docs.rhesis.ai/docs/metrics/index.md

A metric is a judge prompt that another person has to review and a judge LLM has to apply the same
way twice. Filling every field is the floor, not the goal: one thin sentence per field passes
validation and still produces a metric nobody can defend when it fails a test.

Read this before `create_metric`, `generate_metric`, `improve_metric`, or writing `metrics[]` in
`save_plan`. Pair it with `metric-scope.md` (which tests the metric runs against) and
`prd/metric-design.md` (where the pass condition comes from in a requirements plan).

---

## The five fields and what each must contain

| Field | Audience | Substance required |
|---|---|---|
| `description` | human scanning a metric list | 2–3 sentences: what is measured, on what part of the output, and why it matters for this system. Never restate the name |
| `evaluation_prompt` | judge LLM | A criterion naming something a reader could point at, then one bullet per testable clause, then the score bands (see below). Typically 6–15 lines |
| `evaluation_steps` | judge LLM | 4–7 ordered steps in the step format below. Each step is one observable action, not a restatement of the criterion |
| `reasoning` | judge LLM | How to justify the verdict: what to quote, which clause to tie it to, what to do when evidence is missing or ambiguous |
| `explanation` | human reading a result | What a pass and a fail each mean for the system under test, and what the reader should do about a fail |

Those sizes are a floor, not a target. Length is not the point — covering the pass condition is. A
metric where every field is one sentence has not been designed, it has been filled in; a padded one
is no better. Every line must settle a decision the judge or the reader would otherwise guess.

---

## Step format (`evaluation_steps`)

Steps are stored as one string with a hard separator. The platform renders each chunk as its own
numbered step, so the format is not cosmetic:

```text
Step 1:
Locate the eligibility decision in the response — approve, deny, or defer.
---
Step 2:
Extract the reason the response cites for that decision, verbatim.
---
Step 3:
Check the cited reason against the three allowed grounds: purchase date, final-sale flag, open RMA.
---
Step 4:
Assign the category: Compliant Denial only when the decision is deny and exactly one allowed ground
is cited in one sentence.
```

Rules:

- `Step N:` on its own line, the step text below it, chunks joined by a line containing only `---`
- A bare numbered list (`1. … 2. …`) lands as **one** step in the UI — it looks unfinished and is
  harder to edit. Do not send one
- One action per step. If a step contains "and also", split it
- Order matters: locate the evidence → check it against the criterion → map to the score. The
  scoring decision is always the last step

---

## Writing the criterion (`evaluation_prompt`)

A judge answers a narrow question well and a broad one badly. Ask it whether one named thing is true
of the output and it can check; ask it to rate "quality" and it has to invent a standard first, which
means the next run invents a different one. Build the criterion in three parts.

**1. Name the thing you can point at.** Use the vocabulary of the system under test, and describe
something a reader could find in the output.

- Good: "The denial cites a refund ground that appears in the returns policy."
- Bad: "The response is helpful and well written." Nothing there can be located in the output, so two
  runs can disagree and both look defensible.

**2. One bullet per testable clause.** Split the criterion until each bullet fails on its own. If two
bullets can fire on the same sentence, one mistake moves the score twice and the result stops telling
you which clause broke.

**3. Score bands tied to conditions, not adverbs.** Say what has to be true of the output for each
band.

- Good: "Score 1 when the response cites a ground outside the policy; 3 when the ground is valid but
  stated across several sentences; 5 when it is one sentence citing one valid ground."
- Bad: "Score 1 if bad, 3 if okay, 5 if good." With nothing to check against, a judge settles near
  the middle of the scale and the metric stops separating anything.

Close with what this metric does **not** cover — tone, length, formatting — so it does not quietly
score what another metric owns.

Do **not** put `{{prompt}}`, `{{response}}`, or `{{expected_response}}` placeholders in
`evaluation_prompt`. The evaluation engine injects the input, response, context, metadata, and tool
calls (Single-Turn) or the full transcript and conversation goal (Multi-Turn) before your criteria.

---

## Choosing the scale

Use the coarsest scale that still answers the question. Ask a judge for a score out of 100 and it
will give you one, but the digits do not survive a re-run; a two-way category does.

| Question the metric asks | Score type |
|---|---|
| "Did it break the rule, yes or no?" | `categorical`, two categories |
| "Which of several named outcomes happened?" | `categorical`, one category per outcome |
| "How many of N required elements are present?" | `numeric`, `min_score` 0, `max_score` 1 (or N), threshold traceable to the requirement |
| "Rate the overall quality" | none — pick the one property that actually matters and score that |

Categorical labels are outcomes, not grades: `["Blocked", "Initiated"]`, not
`["Good", "Bad"]`. Every threshold and every band needs a stated origin — the requirement it comes
from, or an assumption you name out loud.

---

## `reasoning` — how the judge justifies itself

The judge's `reason` string is what a human reads when a test fails, so say how to write it:

- Quote the specific span of the response that decided the score, not a paraphrase
- Tie the quote to the clause or step it violates or satisfies
- Say what to do when the evidence is absent (e.g. "if the response never states a reason, treat the
  reason as missing rather than inferring intent")
- Say what to do on a genuine tie between two bands, so the judge does not drift to the middle
- For Multi-Turn, name the turn: "cite the turn number where context was lost"

---

## Worked example — categorical, Single-Turn

Behavior: *Denial Reason Single-Sentence Citation*. Requirement: a denial gives a one-sentence reason
citing purchase date, final-sale flag, or open RMA; no speculative alternatives.

| Field | Value |
|---|---|
| `name` | Eligibility Denial Format Compliance |
| `metric_scope` | `["Single-Turn"]` |
| `score_type` | `categorical` |
| `categories` | `["Compliant Denial", "Wrong Reason", "Multi-Sentence or Speculative"]` |
| `passing_categories` | `["Compliant Denial"]` |

**`description`**

```text
Checks how the agent phrases a refund denial: the reason must be one sentence and must cite one of
the three grounds the returns policy allows. Badly worded denials are the top driver of repeat
contacts, so the phrasing matters as much as the decision itself.
```

**`evaluation_prompt`**

```text
Assess only the wording of a denial, not whether the denial itself was the correct decision.

- The response states a denial decision.
- Exactly one reason is cited, and it is purchase date, final-sale flag, or open RMA.
- The reason is a single sentence.
- No alternative outcomes are speculated about ("it might still be possible if…").

Categories:
- Compliant Denial — denies, cites exactly one allowed ground, in one sentence, no speculation.
- Wrong Reason — denies, but the cited ground is outside the three allowed, or none is cited.
- Multi-Sentence or Speculative — an allowed ground is cited, but the reason spans several
  sentences or adds speculative alternatives.

Out of scope: tone, greeting, and whether the eligibility decision was correct — that is covered by
the Refund Window Compliance metric.
```

**`evaluation_steps`**

```text
Step 1:
Confirm the response denies the refund. If it approves or defers, note that in the reason and score
the closest category rather than inventing a pass.
---
Step 2:
Extract the cited reason verbatim.
---
Step 3:
Check the cited ground against the three allowed ones: purchase date, final-sale flag, open RMA.
---
Step 4:
Count the sentences in the reason and check for speculative alternatives.
---
Step 5:
Assign the category using the definitions in the criteria.
```

**`reasoning`**

```text
Quote the denial sentence in full and name which allowed ground it cites, or state that none is
cited. When you pick a failing category, point at the exact clause that broke it — the extra
sentence, the speculative phrase, or the out-of-policy ground. If it is ambiguous whether the
response denies at all, say so instead of assuming a denial.
```

**`explanation`**

```text
A pass means the denial is one clear, policy-grounded sentence the customer can act on. Wrong Reason
means the agent is citing grounds the policy does not support — check the policy text it was given.
Multi-Sentence or Speculative means the agent is hedging, which drives follow-up contacts; tighten
the denial template.
```

---

## Worked example — numeric, Multi-Turn

Behavior: *Order Context Retention Across Follow-ups*. Requirement: keep order context for at least
three follow-up turns without re-asking for the order number.

| Field | Value |
|---|---|
| `name` | Order Context Retention Rate |
| `metric_scope` | `["Multi-Turn"]` |
| `score_type` | `numeric`, `min_score` 0, `max_score` 1, `threshold` 1.0, `threshold_operator` `>=` |

**`description`**

```text
Measures whether the agent carries the order number through a conversation instead of asking for it
again. Re-asking forces the customer to repeat themselves and is the most frequent complaint in
support transcripts, so this is scored as a rate over the whole thread rather than pass/fail per
turn.
```

**`evaluation_prompt`**

```text
The customer states an order number once, early in the transcript. Judge whether the agent keeps
using it for the rest of the conversation.

- Count the agent turns after the order number is first given that depend on order context.
- A turn fails if the agent asks for the order number again, or answers as if no order were in
  context.
- Referring back to the order correctly does not fail a turn. Asking for genuinely new information
  (shipping address, reason for return) does not fail a turn either.

Score = retained turns divided by dependent turns, between 0 and 1. A score of 1.0 means the order
number was never re-requested. The threshold is 1.0, so a single re-request fails the test.

Out of scope: whether the agent's answers were correct, and its tone.
```

**`evaluation_steps`**

```text
Step 1:
Find the turn where the customer first gives the order number.
---
Step 2:
List every later agent turn that depends on order context.
---
Step 3:
For each of those turns, decide whether the agent used the known order or re-requested it.
---
Step 4:
Divide the retained turns by the number of dependent turns.
---
Step 5:
Report that fraction as the score, rounded to two decimals.
```

**`reasoning`**

```text
State the turn where the order number was first given and how many dependent turns you counted. For
every turn counted as a failure, quote the agent's re-request. If the agent asked for different
information that only looks like a re-request, say why you did not count it against the score.
```

**`explanation`**

```text
A score of 1.0 means order context survived the whole thread. Anything lower means the agent lost it
between turns — check how conversation state is carried and whether the order number is included in
the context sent on each turn.
```

---

## Anti-patterns

| Bad | Why |
|---|---|
| One sentence in each field, all fields populated | Passes validation, fails review — the judge has nothing concrete to apply |
| `description` that restates the name ("Measures factual accuracy") | Tells a reader nothing they did not get from the name |
| `evaluation_steps` as `1. … 2. … 3. …` in one blob | Renders as a single step in the UI; not the stored step format |
| Score bands built on adverbs ("mostly correct", "fairly complete") | There is nothing to check the output against, so the same response scores differently on a re-run |
| Steps that repeat the criterion instead of acting on it | Adds tokens, not repeatability |
| `reasoning` = "Explain your score" | The default behavior already does that; say what evidence to cite |
| One metric covering several independent clauses | Hides which clause failed; split into one metric per pass condition |
| Placeholders (`{{response}}`) inside `evaluation_prompt` | The engine already injects the response, so the judge sees a literal placeholder |

---

## Self-check before you send

1. Could a colleague reproduce your score from `evaluation_prompt` + `evaluation_steps` alone?
2. Is every score band or category defined by something observable in the output?
3. Are the steps in the stored step format, one action each, scoring last?
4. Does `reasoning` name the evidence to quote and the tie-breaker?
5. Does `explanation` tell a reader what to do about a fail?
6. Does `metric_scope` match the test sets that will run it (`metric-scope.md`)?
