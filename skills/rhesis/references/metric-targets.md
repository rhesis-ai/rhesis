# Metric targets: what a metric judges and which tests it runs on

> **Docs:** https://docs.rhesis.ai/docs/metrics/targets.md

Every metric has a **target** in its `config`: `config.target = {"on": ...}`. It says what the metric judges in a test's trace, and so which tests the metric runs on. Every test set declares a **`test_type`** (`Single-Turn` or `Multi-Turn`).

See [Glossary](https://docs.rhesis.ai/glossary.md) (`glossary/metric-target.md`) for the term; `definitions.md` for confusions.

---

## Choices

| `on` | Label | Judges |
|---|---|---|
| `turn` | Each turn | The test's one response, or every turn of a conversation on its own |
| `conversation` | The conversation | The whole conversation, once |
| `run` | The whole run | The whole trace, once |
| `tool_call` | Each tool call | Each tool call: arguments as input, result as output |
| `retrieval` | Each retrieval | Each retrieval: query as input, documents as output |
| `model_call` | Each model call | Each call to a model: prompt as input, completion as output |
| `agent` | Each agent | Each agent run: task as input, final answer as output |
| `guardrail` | Each guardrail check | Each guardrail check: what it checked as input, its decision as output |

The per-span targets (`tool_call`, `retrieval`, `model_call`, `agent`, `guardrail`) also take `name` (only spans with that tool, agent or model name), `within` (only spans inside that agent), and `aggregate`: `"all"` (default, every span passes), `"any"`, or `"share"` with `min_share` (0 to 1).

---

## Which tests a metric runs on

- `conversation` runs only on **Multi-Turn** tests. It never runs on Single-Turn tests.
- Every other target runs on Single-Turn and Multi-Turn tests alike.
- On a Multi-Turn test, `turn` judges every turn on its own. The metric fails when a turn fails ("2 of 3 turns passed").
- A metric with `ground_truth_required` is left out of Multi-Turn tests, which have no reference answer, and can't take the `conversation` target.

**Rule:** every requirement on a **Single-Turn** test set needs at least one linked metric whose target is not `conversation`. Otherwise nothing judges those tests.

---

## When to keep the default `turn`

Most metrics. Each reply must hold up on its own: refusals, one-shot format rules, factual checks, adversarial probes, tone. A `turn` metric also runs on every turn of a Multi-Turn set, so one metric covers both test types.

---

## When to use `conversation`

Only the whole conversation shows whether the requirement holds: context retention, multi-step threads, "no further questions after X", the session goal reached. Pair it with a **Multi-Turn** test set whose `generation_prompt` describes the thread goal. If the same requirement is also on a Single-Turn set, link a second metric with a `turn` target.

---

## When a per-span target fits

The requirement is about one step inside the agent, not the reply:

- **Tool-call policy** ("refunds only through `issue_refund`, at most once per order"): `{"on": "tool_call", "name": "issue_refund"}`.
- **Retrieval quality** ("the documents found answer the question"): `{"on": "retrieval"}`.
- **Sub-agent output** ("the research agent cites its sources"): `{"on": "agent", "name": "researcher"}`.

A per-span target only matches what the endpoint reports. SDK endpoints report every span they trace. REST and WebSocket endpoints report tool calls and retrievals only when their response mapping maps `tool_calls` or `context`, or when the service sends its own traces. When nothing matches, the metric is reported as not applicable for that test. A metric with `ground_truth_required` can't take a per-span target.

---

## Sending it

`create_metric` takes it in `config`. It is optional: leave it out and the default (`turn` for custom judges) is stored and returned in the response's `config`.

```json
{"config": {"target": {"on": "conversation"}}}
```

`update_metric` changes it the same way. The whole `config` is replaced, so send any other settings the metric keeps there along with the target. A target the metric can't take is refused with the choices it can take.

`list_metrics` returns `config`, so read `config.target.on` when reusing a metric.

---

## Planning checklist

1. A target on every metric in the plan (default `turn`; copy `config.target.on` from `list_metrics` when reusing).
2. One `test_type` per test set.
3. Requirements listed on each test set.
4. Coverage: every requirement on a Single-Turn set has a linked metric whose target is not `conversation`.
5. Retention and other whole-conversation requirements go on a Multi-Turn set with a `conversation` metric.

---

## Plan tables (required before approval)

**Metrics:** Metric | Requirement | AC source | Target | Score type | Pass definition

**Test sets:** Test set | `test_type` | Requirements | Metrics expected to run

**Coverage matrix:** Test set | test_type | Requirement | Linked metric | Runs on this type?
