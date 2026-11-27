# Metric target ↔ test set alignment (platform rules)

**Start here for what each target judges:** [metric-targets.md](../metric-targets.md).

The PRD skill plans a **target on every metric** (`config.target.on`) and a **`test_type` on every test set**, so that every test set has metrics that run on it. The platform does **not** add metrics for you: a test with no metric that can judge it gets no scores.

## How the platform resolves metrics at run time

For each test, metrics come from (highest priority first):

1. Execution-time override on `test_configuration`
2. Metrics attached to the **test set**
3. Metrics linked to the test's **requirement**

Then it keeps the metrics that can judge the test:

| Test `test_type` | Runs | Left out |
|---|---|---|
| `Single-Turn` | Every target except `conversation` | `conversation` metrics |
| `Multi-Turn` | Every target. `turn` judges each turn on its own | Metrics with `ground_truth_required` (a conversation has no reference answer) |

A per-span target (`tool_call`, `retrieval`, ...) that matches nothing in a test's trace is reported as **not applicable** for that test, with the reason. A test whose metrics are all not applicable is Inconclusive.

## Test set `test_type` sets every generated test

`generate_test_set` → `test_type`:

- **`Single-Turn`**: each test has a **prompt** (+ optional `expected_response`)
- **`Multi-Turn`**: each test has **`test_configuration.goal`**; no prompt. Penelope drives the conversation.

**Implication:** requirements that only make sense across turns (context retention, multi-step refund thread) need:

1. A metric with a `conversation` target
2. A **Multi-Turn** test set whose `generation_prompt` targets those requirements

Single-turn guardrails (secrecy, one-shot refusal) need:

1. A metric with a `turn` target (the default)
2. A **Single-Turn** test set. The same metric also judges every turn of a Multi-Turn set.

## PRD → target decision table

| PRD signal | Target | Test set `test_type` |
|---|---|---|
| "Shall not disclose…" (one-shot probe) | `turn` | Single-Turn |
| "Retain context ≥ N follow-ups without re-asking ID" | `conversation` | Multi-Turn |
| "Refund only if ≤ 30 days" tested via one message | `turn` | Single-Turn |
| Same refund rule exercised **after** a status thread | `turn` (checks every reply) or `conversation` (checks the thread's outcome) | Multi-Turn |
| "Order number OR email" single lookup | `turn` | Single-Turn |
| Full thread (status + refund, no re-entry) | `conversation` for retention; separate metrics per FR | Multi-Turn |
| "Refunds go through `issue_refund` only" | `{"on": "tool_call", "name": "issue_refund"}` | Either |
| Off-topic one-sentence redirect | `turn` | Single-Turn |

When the same requirement needs **both** a one-shot probe and a whole-conversation check, link two metrics to it: one `turn`, one `conversation`.

## Plan requirements (mandatory columns)

### Metrics table

| Metric | Requirement | AC source | Target | Score type | Pass definition |

Fill the target on every row, even when it is the default `turn`, so the choice is visible to the user.

### Test sets table

| Test set | `test_type` | Requirements targeted | Metrics expected to run |

**Coverage check before user approval:**

For each **Single-Turn** test set row, every requirement listed must have **at least one** linked metric whose target is not `conversation`.

```
∀ Single-Turn test_set T, ∀ requirement B ∈ T.requirements:
  ∃ metric M linked to B such that M.target ≠ conversation
```

If not, add a `turn` metric for that requirement or move it to a Multi-Turn set. Do not proceed. Architect's `save_plan` refuses a plan that fails this check.

## Common failure modes

| Mistake | What happens |
|---|---|
| Single-Turn test set, every linked metric targets `conversation` | No metric runs; the tests get no scores |
| Context-retention FR judged only by a `turn` metric | Each reply is judged on its own; nothing checks retention across the thread |
| Reference-answer metric (`ground_truth_required`) on a Multi-Turn set | Left out of every Multi-Turn test |
| Per-span target on an endpoint that reports no such spans | Not applicable on every test |

## Creation order reminder

1. Create requirements
2. Create metrics **with `config.target` from the plan** (or omit it for `turn`)
3. `add_requirement_to_metric` for each mapping
4. Generate **Single-Turn** and **Multi-Turn** test sets separately when the PRD needs both
5. Tag entities
