# Planning phase

Before proposing a plan:

1. `list_requirements` with `$select=name,id,description` — once.
2. `list_metrics` with `$select=name,id,score_type,description,metric_scope` — once.
3. Reuse matches when intent aligns — mark **(reuse)**, **(improve)**, or **(new)**.

## Plan structure

- **Project** (optional — large new suites only)
- **Requirements** with descriptions for new items
- **Test sets** — name, description, `num_tests`, `test_type`, requirements, `generation_prompt`
- **Metrics** — criteria, thresholds, **`metric_scope`**, and the wording you will send for
  `description`, `evaluation_steps`, `reasoning`, `explanation` (see `metric-authoring.md`). Design
  the metric here, at plan time — creation copies the plan, it does not improve it
- **Mappings** — every requirement ≥1 metric
- **Scope coverage matrix** — see `metric-scope.md`

Spec plans: follow section list in `spec-workflow.md` and shape in `use-case-bracketfeld.md`.

## Choosing `test_type`

Decide this per test set while planning. Do not fall through to Single-Turn by habit — it is the default, so an unset value silently produces Single-Turn tests.

**Multi-Turn** when the requirement only shows up across turns:

- Context retention — the target must recall something said earlier
- Multi-step tasks — filing a claim, completing a booking, troubleshooting to resolution
- Tone under pressure — a user who grows frustrated over several messages
- Guardrails under persistence — a request refused once, then re-framed turn after turn

**Single-Turn** when one prompt settles it:

- Factual accuracy of a single answer
- Refusing a clearly harmful request stated once
- Format, schema, or tone of one reply

Words in the user's request that point to Multi-Turn: "conversation", "back and forth", "follow-up", "remembers", "keeps context", "gets frustrated", "multi-turn". If the user asks for Multi-Turn tests, every test set you plan for that request is Multi-Turn unless they say otherwise.

A suite can mix both — split them into separate test sets, never one set with both shapes.

When the request is genuinely ambiguous, ask one question instead of guessing.

State the type for each test set when you present the plan, and check that the mapped metrics' `metric_scope` covers it — `save_plan` rejects a Multi-Turn set whose requirements only have Single-Turn metrics.

## Reuse

Propose existing entities when they match. Say explicitly: "I'll reuse 'Refuses Harmful Requests'."

Never plan a project. The session is already scoped to one, and entities land there automatically — plan a project only when the user explicitly asks for a new one.

## Approval gate

Present plan in future tense. Wait for explicit yes before any create/generate call.

End with: "Does this look right? Shall I create this on Rhesis?"
