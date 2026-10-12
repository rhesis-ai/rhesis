# Audit log

Read this when the user asks who changed, created or deleted something, what changed since a date,
what a person, an API token or the Architect did, or who changed access.

## When the tools are missing

The audit log tools (`list_audit_events`, `get_audit_event`, `list_audit_actions`) are listed only
when the organization's plan includes the audit log and the user's role or API token may read it.
If they are not in your tool list, tell the user the audit log is not available on this plan or for
this role, and stop. Do not rebuild history from other data such as `created_at` or `updated_at`.

## What an entry holds

One entry is one action, named `resource.verb_past`: `endpoint.updated`, `metric.deleted`,
`test_set.created`. `list_audit_actions` has every name, so look a name up there instead of
guessing one. A change of someone's role, for example, is `member.updated` with `role_id` in its
changes.

| Field | Meaning |
|---|---|
| `occurred_at` | When it happened |
| `actor_label` | Who did it, by name and email at the time, so it still reads after they leave |
| `actor_type` | `user`, `api_token`, `api_client`, `system` or `anonymous` |
| `actor_credential_hint` | Which API token, when one was used |
| `channel` | Where it came from (`web`, `sdk`, `mcp`, `architect`, `api` or `job`) |
| `resource_id`, `resource_label` | What it was done to, and its name at the time |
| `outcome` | `success`, `failure` or `denied` |
| `changes` | One item per field: `field`, `kind`, `before`, `after` |
| `trace_id` | Entries with the same value came from the same request |

A field of kind `secret` (API keys, auth tokens) or `content` (prompts, responses, comments) shows
that it changed but never carries its values. A job that created many rows writes one entry whose
`changes` is `{count, ids}`.

The log holds only what happened while the organization had it. An empty result for an older
period does not prove nothing changed then.

## Finding the right entries

Resolve names first, as everywhere else. Find the id with `list_metrics`, `list_endpoints` or
`list_test_sets` and a `tolower()` filter, then filter the log on `resource_id`. Batch several ids with `or`. A deleted
resource no longer lists, so match its name in the log instead:
`contains(tolower(resource_label), 'refusal')`.

There is no tool that looks people up. Match the name or email the entry recorded:
`contains(tolower(actor_label), 'alice')`.

| Question | `filter` |
|---|---|
| Who changed metric X? | `resource_id eq '<metric id>'` |
| What changed since Monday? | `occurred_at ge 2026-10-05T00:00:00Z` |
| What changed on our endpoints? | `startswith(action,'endpoint.')` |
| What did Alice do? | `contains(tolower(actor_label), 'alice')` |
| What did API tokens do? | `actor_type eq 'api_token'` |
| Who changed access? | `startswith(action,'member.') or startswith(action,'project_member.') or startswith(action,'role.') or startswith(action,'token.') or startswith(action,'api_clients.')` |
| What did the Architect change? | `channel eq 'architect'` |
| What else did that request do? | `trace_id eq '<trace_id>'` |
| Who failed to sign in? | `action eq 'session.signed_in' and outcome eq 'failure'` |
| What was someone refused? | `outcome eq 'denied'` |
| Who exported test sets? | `action eq 'test_set.exported'` |

Combine conditions with `and`. Results come newest first, one page at a time. When
`_pagination.has_more` is true, narrow the filter or call again with `skip`.

## Answering

- One line per change: time, who, the action and the resource's name, then each field as
  `before → after`.
- Report only the entries the tool returned. Never describe a change that is not in the response.
  No entries is the answer, so say that nothing in the audit log matched.
- For a `secret` or `content` field, say it changed and that the value is not recorded. Do not look
  for the value anywhere else.
- Do not guess why someone made a change. The log says what happened, not why.
