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

The per-span targets and `turn` also take `where`, the conditions the span must meet. The short form maps attribute keys to values, such as `{"rhesis.reported.metadata.channel": "email"}`, and a list of values means any of them. It is stored as a list of conditions (see [Span targets](#span-targets)). Use it to judge only a slice, for example only email conversations.

Each thing a target picks is judged as its own trace: the span and everything under it. A code metric that reads `trace` can take every target, and on `agent` it sees only that agent's calls.

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

## Span targets

`{"on": "span", "where": [...]}` judges each span that meets all of its conditions. Each condition is `{"field", "op", "value"}`.

- `field` is `kind` (`tool.invoke`, `retrieval`, `llm.invoke`, `agent.invoke`, `guardrail`, `endpoint.invoke`), `name` (tool, agent or model name, else the span name), `span_name`, `duration_ms`, `status` (`ok` or `error`), or any span attribute key. Write `attributes.status` for an attribute named like a special field.
- `op` is `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not_in`, `contains`, `matches`, `exists` or `not_exists`. `in` and `not_in` take a list; `exists` and `not_exists` take no value. There is no "or" across conditions; use `in`.
- A span without the field passes only `!=`, `not_in` and `not_exists`. So "`app.customer_tier` is not `gold`" keeps spans with no tier.
- `matches` accepts only patterns that mean the same in Python and Postgres and can't take exponential time. It refuses `\d`, `\w` and `\s` (write `[0-9]`, `[A-Za-z0-9_]`, `[ \t\n\r\f\v]`), `\b`, `\A`, `\Z`, named groups, lookbehind, inline flags such as `(?i)` (write `[Rr]efund`), possessive quantifiers, `{,n}` (write `{0,n}`), repeat counts over 255, POSIX classes such as `[[:alpha:]]`, and a repeated group that repeats inside, such as `(a+)+` or `([a-z]+\.)*com`. The refusal names the construct and the portable form where there is one.
- Conditions read the span's own attributes, not its parent's or the turn's.

`within`, `read`, `aggregate` and `min_share` work as on the presets. A span target needs at least one condition (use `run` for the whole trace) and takes no `name`; write a `name` condition instead.

### When a preset is enough

Each per-span preset is a short form of a span target. `{"on": "tool_call", "name": "issue_refund", "within": "billing_agent"}` matches exactly what `{"on": "span", "where": [kind == tool.invoke, name == issue_refund], "within": "billing_agent"}` does. Use the preset whenever the spans are all of one kind. A preset also takes `where`, on attributes, `status` or `duration_ms`, so a tool call with extra conditions is still a preset. Write `"span"` only when the spans cross kinds or no kind fits.

### Workflow

1. **`list_trace_attributes`** for the project (and the `kind`, if you know it). Take keys and values from it; never guess a key. Skip keys marked `unique`, such as ids.
2. **Draft** the target from those keys.
3. **`preview_target`** with the draft. Tell the user how many of the traces it matched, how many units the metric would run on, and what one or two samples look like. If it matches nothing, or far more than expected, fix the key, value or operator and preview again. If it still finds nothing, say what the endpoint must report for it to match (for example "`tool.invoke` spans must carry `ai.tool.name`") before saving it.
4. **`create_metric`** (or `update_metric`) with the same target in `config.target`.
5. **Read `warnings`** in the response. A warning names a `where` key no recent span carries and the nearest key that one does. The metric is saved anyway. Report it, and fix the key with `update_metric` if the suggestion is what was meant.

The response's `target_summary` is the target in words. Read it back to the user to confirm it says what they asked for. `list_spans` with `target` lists exactly the spans a target picks.

### What the metric reads

`read` sets what each unit hands the metric as `input` and `output`, when the kind's own (a tool call's arguments and result, a retrieval's query and documents) aren't what the criteria judge. Each side is an attribute key, `input`, `output`, `conversation.input`, `conversation.output`, or `event:<name>`, such as `event:ai.retrieval.query`. The conversation readers read the turn the unit belongs to. They take its root span's `rhesis.conversation.input` or `rhesis.conversation.output`, else that root span's own input or output. Use `{"input": "conversation.input"}` to judge a tool call against what the user asked in that turn. Leave a side out to keep the kind's own. `read` is refused on `conversation` and `run`.

### Example: refund policy

The requirement says that the billing agent refunds or cancels only within policy, in at least 90% of cases. Only calls that went through are judged; a failed call changed nothing.

```json
{"config": {"target": {
  "on": "span",
  "where": [
    {"field": "kind", "op": "==", "value": "tool.invoke"},
    {"field": "name", "op": "in", "value": ["issue_refund", "cancel_order"]},
    {"field": "status", "op": "==", "value": "ok"}
  ],
  "within": "billing_agent",
  "aggregate": "share",
  "min_share": 0.9
}}}
```

Its summary reads "each tool call named `issue_refund` or `cancel_order` inside `billing_agent`, where `status` is `ok`". A reported tool call has no status, so it is left out. Check with `list_trace_attributes` (`kind: "tool.invoke"`) and `preview_target` before saving.

---

## When a rule fits

A rule is a metric with no model: it reads a field of the trace, or one of the test's
expectations, and compares it with a fixed value. It costs no judge calls and gives the same
verdict every time. Plan a rule, not a judge, when the requirement is a limit or an exact check.
Reuse the seeded rules first: "Response Time", "No Failed Tool Calls", "Token Budget",
"Exact Match" and "Tool Call Trajectory".

| Requirement | Rule | Target |
|---|---|---|
| Answers within 5 seconds | `FieldRule` `{"field": "duration_ms", "op": "<=", "value": 5000}` | `turn` |
| No tool call fails | `FieldRule` `{"field": "error_count", "op": "==", "value": 0}` | `tool_call` |
| Never deletes an account | `FieldRule` `{"field": "span_count", "span_kind": "tool_call", "span_name": "delete_account", "op": "==", "value": 0}` | `run` |
| Stays under a token budget | `FieldRule` `{"field": "tokens.total", "op": "<=", "value": 20000}` | `run` or `conversation` |
| Returns valid JSON | `FieldRule` `{"field": "output", "op": "is_json"}` | `turn` |
| Leaks no email address | `FieldRule` `{"field": "output", "op": "matches", "value": "[A-Za-z0-9_.]+@[A-Za-z0-9_.]+", "negate": true}` | `turn` |
| Equals the expected answer | `ResponseRule` `{"match": "exact"}` | `turn` |
| Calls the expected tools in order | `ToolCallTrajectory` `{"match": "in_order"}` | `run` |

Send `class_name` (the rule), `metric_type: "rule"`, `backend_type: "rhesis"`, `score_type:
"numeric"` with `min_score` 0, `max_score` 1, `threshold` 1, and the settings in `config` next to
the target. `create_metric`'s description lists every field and operator. When the data a rule
reads is missing (a span with no timing, no token counts, no expected response), its result is not
applicable, never a pass: check what the endpoint reports before promising a rule will judge it.
Keep judges for questions of meaning, such as whether an answer is grounded or helpful.

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
