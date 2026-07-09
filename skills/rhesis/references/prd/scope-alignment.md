# Metric scope ↔ test set alignment (platform rules)

The PRD skill must plan **`metric_scope` on every metric** and **`test_type` on every test set** so they match. The platform does **not** auto-fix mismatches — incompatible metrics are **silently dropped** at execution.

## How the platform resolves metrics at run time

For each test, metrics come from (highest priority first):

1. Execution-time override on `test_configuration`
2. Metrics attached to the **test set**
3. Metrics linked to the test's **behavior**

Then the executor filters by **test type**:

| Test `test_type` | Filter applied | Source |
|---|---|---|
| `Single-Turn` | Keep metrics where `"Single-Turn" ∈ metric_scope` | `prepare_metric_configs(..., SINGLE_TURN)` in `runners.py` |
| `Multi-Turn` | Keep metrics where `"Multi-Turn" ∈ metric_scope` | `prepare_metric_configs(..., MULTI_TURN)` in `evaluation.py` |

Additional guards:

- **`metric_scope` null or `[]`** → metric **excluded** (warning logged)
- **Multi-Turn-only metric on Single-Turn test** → excluded (`_is_multi_turn_only` in `evaluate_single_turn_metrics`)
- **Single-Turn-only metric on Multi-Turn test** → excluded by scope filter
- **No metrics left after filter** → evaluation returns `{}`; result status tends to **Error** (`determine_status_from_metrics`)

Preflight (`check_metric_functionality`) may **warn**: *"No metrics support Multi-Turn scope"* — but this does not block the run.

## Valid `metric_scope` values

`create_metric` → `metric_scope` is a **required list** of:

- `["Single-Turn"]` — one prompt, one response
- `["Multi-Turn"]` — full `conversation_summary` / transcript required
- `["Single-Turn", "Multi-Turn"]` — runs on **both** test types (use when the same AC is testable either way)

There is no separate "binary" scope — binary is a **categorical score type**, not a scope.

## Test set `test_type` sets every generated test

`generate_test_set` → `test_type`:

- **`Single-Turn`** — each test has a **prompt** (+ optional `expected_response`)
- **`Multi-Turn`** — each test has **`test_configuration.goal`**; no prompt. Penelope drives the conversation.

**Implication:** behaviors that only make sense across turns (context retention, multi-step refund thread) need:

1. Metric with `"Multi-Turn"` in `metric_scope`
2. A **Multi-Turn** test set whose `generation_prompt` targets those behaviors

Single-turn guardrails (secrecy, one-shot refusal) need:

1. Metric with `"Single-Turn"` in `metric_scope` (or dual-scope)
2. A **Single-Turn** test set

## PRD → scope decision table

| PRD signal | `metric_scope` | Test set `test_type` |
|---|---|---|
| "Shall not disclose…" (one-shot probe) | `["Single-Turn"]` | Single-Turn |
| "Retain context ≥ N follow-ups without re-asking ID" | `["Multi-Turn"]` | Multi-Turn |
| "Refund only if ≤ 30 days" tested via one message | `["Single-Turn"]` | Single-Turn |
| Same refund rule exercised **after** status thread in story | `["Multi-Turn"]` or dual-scope | Multi-Turn (preferred) |
| "Order number OR email" single lookup | `["Single-Turn"]` | Single-Turn |
| Full RS-04 thread (status + refund, no re-entry) | `["Multi-Turn"]` for retention; separate metrics per FR | Multi-Turn |
| Off-topic one-sentence redirect | `["Single-Turn"]` | Single-Turn |

When the same behavior needs **both** a one-shot adversarial probe and a conversational flow, either:

- Create **two metrics** (one per scope), or
- One dual-scope metric with an `evaluation_prompt` that works for both (harder — prefer split)

## Plan requirements (mandatory columns)

### Metrics table

| Metric | Behavior | AC source | `metric_scope` | Score type | Pass definition |

Every row must have an explicit `metric_scope` list — never leave blank (platform default may be Single-Turn only, but PRD skill must plan intentionally).

### Test sets table

| Test set | `test_type` | Behaviors targeted | Metrics expected to run |

**Coverage check before user approval:**

For each test set row, every behavior listed must have **at least one** linked metric whose `metric_scope` includes that test set's `test_type`.

```
∀ test_set T, ∀ behavior B ∈ T.behaviors:
  ∃ metric M linked to B such that T.test_type ∈ M.metric_scope
```

If not, split behaviors, split metrics, or add dual-scope metrics — do not proceed.

## Common failure modes

| Mistake | What happens |
|---|---|
| Multi-Turn test set, all metrics `["Single-Turn"]` only | Preflight warning; run produces no metric scores |
| Context-retention FR, metric scoped Single-Turn only | Metric never runs on the Multi-Turn set that tests retention |
| Forgot `metric_scope` on `create_metric` | Metric excluded on every run |
| One test set mixes retention + secrecy behaviors | Secrecy metrics won't run on Multi-Turn set unless dual-scope — **split test sets** by scope |
| Behavior linked to metric, but wrong test set type | Mapping exists but execution filter drops metric |

## Creation order reminder

1. Create behaviors
2. Create metrics **with `metric_scope` set from plan**
3. `add_behavior_to_metric` for each mapping
4. Generate **Single-Turn** and **Multi-Turn** test sets separately when the PRD needs both
5. Tag entities

Do not put all behaviors in one test set if their metrics require different scopes.
