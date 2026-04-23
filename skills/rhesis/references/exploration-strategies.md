# Exploration Strategies

The `explore_endpoint` tool uses Penelope, a multi-turn conversation agent, to probe an AI endpoint. Three built-in strategies provide structured exploration, plus a `comprehensive` mode that chains all three.

Pass the strategy name via the `strategy` parameter. When a strategy is provided, the tool generates `goal` and `instructions` automatically — you don't need to write them. You can still pass `previous_findings` from a prior run to chain strategies.

---

## `domain_probing`

**Purpose:** Discover the endpoint's purpose, core domain, terminology, and persona through structured decomposition and conversational probing. Typically run first.

**Max turns:** 5

**Dimensions probed:**
1. **Scope** — open with a broad question; let the endpoint introduce itself; identify main topic areas it volunteers vs. those you have to ask about
2. **Depth** — follow up on the most prominent topic; detailed answers signal deep coverage, vague answers signal shallow coverage
3. **Persona** — tone, formality, vocabulary, consistent voice; observe throughout the conversation rather than dedicating a turn
4. **Terminology** — domain-specific terms and jargon the endpoint uses consistently
5. **Adjacent domains** — topics one step outside the core domain; reveals where the boundary begins

**Structured findings returned:**
```json
{
  "domain": "travel booking",
  "purpose": "helps users find and book flights and hotels",
  "persona": "professional, friendly, uses industry jargon",
  "key_topics": ["flights", "hotels", "cancellations"],
  "terminology": ["PNR", "fare class", "open-jaw"],
  "depth_assessment": "deep on flights, shallow on hotels",
  "adjacent_domains": ["travel insurance", "visa requirements"]
}
```

**When to use:** First exploration of any endpoint. Gives enough context to start planning.

---

## `capability_mapping`

**Purpose:** Systematically map what the endpoint can do across five query types, with progressive difficulty escalation.

**Max turns:** 7

**Dimensions probed:**
1. **Factual** — straightforward domain-knowledge questions
2. **Procedural** — step-by-step walkthroughs or how-to instructions
3. **Analytical** — comparisons, trade-offs, or recommendations
4. **Multi-turn** — follow-ups that require remembering prior context
5. **Edge case** — unusual inputs, ambiguous requests, boundary scenarios

For each type: baseline probe → stress test (if baseline succeeds) → record the capability ceiling.

**Structured findings returned:**
```json
{
  "capabilities": ["factual", "procedural", "multi_turn"],
  "limitations": ["analytical queries return generic answers"],
  "capability_ceilings": {"factual": "handles 3-hop reasoning", "multi_turn": "retains 2 prior turns"},
  "interaction_patterns": "prefers structured questions over open-ended ones",
  "multi_turn_support": "basic context retention confirmed",
  "query_type_coverage": {"factual": "strong", "procedural": "moderate", "analytical": "weak"}
}
```

**When to use:** After domain probing, when you need to understand the full capability surface before designing test sets.

**Passes `previous_findings`:** Capability mapping uses prior domain findings to focus on the right topic area.

---

## `boundary_discovery`

**Purpose:** Discover refusal patterns, domain limits, and safety guardrails through structured boundary probing with consistency verification.

**Max turns:** 7

**Dimensions probed:**
1. **Domain edge** — topics adjacent to but outside the core domain
2. **Sensitivity** — potentially sensitive or controversial topics
3. **Capability limit** — requests that exceed the endpoint's competence
4. **Instruction conflict** — requests that conflict with the endpoint's guidelines
5. **Consistency** — rephrasing a previously refused topic to check whether enforcement is consistent (hard vs. soft boundary)

**Structured findings returned:**
```json
{
  "refusal_patterns": ["refuses all financial advice", "declines personal opinions"],
  "domain_boundaries": ["handles travel only, not adjacent services"],
  "safety_guardrails": ["blocks requests for personal data"],
  "boundary_consistency": "mostly consistent; one inconsistency found with indirect framing",
  "hard_boundaries": ["financial advice", "medical information"],
  "soft_boundaries": ["political questions (deflects but partially answers)"]
}
```

**When to use:** After capability mapping, to understand what the endpoint won't do and how reliably. Essential for designing safety-focused test sets.

**Passes `previous_findings`:** Boundary discovery uses domain and capability findings to target boundaries at the right level.

---

## `comprehensive`

**Purpose:** Run all three strategies in sequence, chaining findings from each into the next.

**Order:** domain_probing → capability_mapping → boundary_discovery (in parallel after domain probing).

**When to use:** When the user wants a complete picture of an unfamiliar endpoint and is willing to wait. Produces findings across all three areas.

**How to invoke:**
```
# 1. Launch — returns {task_id, message}
explore_endpoint(endpoint_id=<uuid>, strategy="comprehensive")

# 2. Poll until SUCCESS
get_job_status(task_id=<task_id>)
# → {status: "SUCCESS", result: {findings, strategy_findings, conversation, ...}}
```

No `goal` or `instructions` needed.

---

## Chaining strategies manually

You can also chain strategies one at a time, passing `previous_findings` from each to the next. This lets you decide after each run whether to continue:

```
# Step 1: Quick domain scan
task_1 = explore_endpoint(endpoint_id=<uuid>, strategy="domain_probing")
# → {task_id: "abc"}
result_1 = get_job_status(task_id="abc")   # poll until SUCCESS
findings_1 = result_1["result"]

# Step 2: Only if domain probing suggests it's worth deeper exploration
task_2 = explore_endpoint(
    endpoint_id=<uuid>,
    strategy="capability_mapping",
    previous_findings=findings_1
)
result_2 = get_job_status(task_id=task_2["task_id"])   # poll until SUCCESS
findings_2 = result_2["result"]

# Step 3: Only if you need to understand limits for safety testing
task_3 = explore_endpoint(
    endpoint_id=<uuid>,
    strategy="boundary_discovery",
    previous_findings={**findings_1, **findings_2}
)
result_3 = get_job_status(task_id=task_3["task_id"])   # poll until SUCCESS
```

Use `"comprehensive"` when you know you want all three. Use manual chaining when you want to inspect findings between steps and decide whether to continue.

---

## Novelty filtering

When `previous_findings` are provided, each strategy instructs Penelope to avoid re-probing areas already characterized. This prevents redundant turns and keeps the conversation focused on new information.

For example, if `previous_findings` contains `domain: "travel booking"` and `key_topics: ["flights", "hotels"]`, subsequent strategies skip confirming the domain and probe new dimensions instead.

---

## What to do with exploration failures

A failed or partial exploration is still useful data. An endpoint that refuses all your probes reveals its refusal pattern and domain restrictions. After each call:
- Assess whether you have enough information to design a meaningful test suite
- If yes, stop exploring and move to planning
- If not, try a different strategy or pass `previous_findings` for a follow-up run
- Never repeat the same strategy with the same goal — vary your approach
