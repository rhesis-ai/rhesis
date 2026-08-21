# Discovery phase

When the user names an endpoint or wants to test an AI application:

1. Resolve endpoint: `list_endpoints` with `$select=name,id,url,description`. If missing, `create_endpoint` — it lands in the current project automatically, so omit `project_id`.
2. `check_endpoint` — report failures before proceeding.

If the project has **no** endpoint at all, lead your reply with that before any test design: nothing can run against the project until one is connected, so there are no responses to score. Show both routes — register the application's HTTP API, or wrap a Python function with the SDK's `@endpoint` decorator ([connecting an application](https://docs.rhesis.ai/docs/getting-started/connecting-application)) — and offer to create it now. Say it once; if the user would rather design tests first, continue.
3. If mode not chosen: offer **Quick** vs **Comprehensive** (default Quick if vague).
4. `explore_endpoint` with strategy from `exploration-strategies.md` — async; poll `get_job_status` every 5–10s until `SUCCESS`.

## Compiled observations

Synthesize — never dump raw tool output. Cover: domain/purpose, capabilities, restrictions, response patterns, areas for testing.

Ask 2–3 **specific** follow-up questions from findings — not generic ("what does your bot do?").

Good: "It refused all zoning questions outside Bracketfeld — should adjacent cities be in scope?"

## After discovery

Proceed to `phases/planning.md` unless the user only wanted exploration.
