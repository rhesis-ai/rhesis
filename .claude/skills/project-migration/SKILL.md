---
name: project-migration
description: Copy a Rhesis project (endpoints, requirements, metrics, tests, test sets and their links) from one Rhesis instance to another with ./rh project-migrate. Use when asked to migrate, copy or move a project between instances, e.g. from cloud to a self-hosted deployment.
---

# Project migration (`./rh project-migrate`)

The backend has no export or import feature, so the tool replays the REST API. It reads the
source once into a snapshot. Then it plans against the target, applies, and verifies. Every
step is safe to run again.

Use the tool, not the Rhesis MCP server. MCP talks to one instance at a time, can't pace
requests, and can't resume after a failure.

## What gets copied

- **Endpoints.** The full config: URL, headers, request and response mappings.
- **Requirements.** Parents are created before their children, and impact is kept.
- **Custom metrics.** These are the project-scoped ones, plus any metric created at org
  level that a requirement or test set links to. That one is copied into the project.
- **Topics and categories** used by the tests.
- **Every test in the project,** including tests that belong to no set, multi-turn tests, and
  older tests with no project that sit in one of its sets. Each test keeps its prompt,
  `test_parameters`, `test_metadata` and `test_configuration`.
- **Test sets.** A test that sits in several sets stays one test.
- **Links.** Requirement→metric, test set→test and test set→metric.

**Not copied:**
- **Endpoint secrets** (`auth_token`, `client_secret`). The API never returns them, so they
  must be pasted into the target UI afterwards.
- **Built-in metrics.** Each instance seeds its own. Links to them are matched on the target by
  name and `class_name`.
- **History and ownership.** Test runs, results, traces, annotations, tags, files, project
  members, owners and assignees. Every record ends up owned by the target key's user.
- **A metric's judge model** (`model_id`). Copied metrics use the target org's default model.

## Runbook

Keys come from the environment only. Never write them to a file, a command that gets saved, or
a commit. If the user pasted keys into chat, tell them to rotate the keys afterwards.

```bash
export RHESIS_SRC_API_KEY=...   # key on the source instance
export RHESIS_DST_API_KEY=...   # key on the target instance
```

1. **Preflight.** The target project must already exist, so ask the user to create it in the
   target UI. The API can't delete a project, so don't create a throwaway one there for testing.
   Get both project IDs (`GET /projects/`).
2. **Snapshot.** Read the counts it prints back to the user, and pass on any `note:` lines (for
   example, a requirement that was deleted on the source but is still used by tests; it gets
   recreated).
   ```bash
   ./rh project-migrate snapshot --src-url https://api.rhesis.ai --src-project <src-id>
   ```
3. **Plan.** It's a dry run with zero writes. Show the table to the user and **get a yes before
   any write**, especially on a customer's instance.
   ```bash
   ./rh project-migrate plan --snapshot <file> --dst-url <target-api-url> --dst-project <dst-id>
   ```
4. **Trial.** Run `apply ... --limit 5` and have the user check the result in the target UI.
   `--limit` must be 1 or more.
5. **Apply.** Run it in the background. At the default 2 writes per second, 500 tests take about
   10 minutes.
6. **Verify.** It must end with `VERIFY OK`. A second `plan` must show everything as
   `unchanged`/`linked`.
7. **After.**
   - The user pastes endpoint secrets into the target UI. `apply` lists the endpoints that need one.
   - Run one small test set on both instances and compare. This proves the target can reach the
     endpoint and that its default judge model scores the copied metrics.

## Files

Snapshots and state go to `playground/project-migrate/` by default. That folder is gitignored and
shared with every worktree. Change it with `--work-dir`.
- `snapshots/<host>-<project>/<timestamp>.json`
- `state/<host>-<project>.json`

Snapshots contain the customer's test data. They must never be committed, attached to a PR, or
quoted in public text.

## How it stays safe

- **Paced.** One request at a time. By default 5 reads and 2 writes per second per host, set
  with `--read-rps` and `--write-rps`.
- **Backoff.**
  - A 429 honors `Retry-After`.
  - On a read or `PUT`, a 5xx or network error backs off exponentially. After 6 failed tries
    the run stops, with state saved.
  - On a `POST`, a 5xx counts as an unclear outcome (see below).
  - Any other 4xx stops right away and prints the request.
- **Write-ahead state.** Each create is saved as `pending` before the POST and `done` after it.
  Changes are appended to `<state>.journal` and folded into the state file at the start and end
  of each run. A lock file stops two `apply` runs from overlapping.
- **No blind POST retries.** If a POST's outcome is unclear (timeout, broken connection, 5xx),
  the tool looks the record up first, and adopts it if it's there. So a laptop going to sleep
  mid-run is harmless: run `apply` again.
- **Matching without state.**
  - Named entities match by name in the target project.
  - Tests match by a hash of prompt, expected response, requirement, topic, category,
    `test_parameters`, `test_metadata` and `test_configuration`.
- **Updates, not just skips.** A changed source record gets a `PUT` with only the changed
  fields. A key removed from a dict field (headers, mappings, metadata) counts as a change.
  Two cases are not propagated:
  - a field cleared to empty on the source, because empty values are never sent;
  - a removed link. Links are only ever added. Extra links on the target are reported and
    left alone.

## Problems you may hit

| Symptom | Cause / fix |
|---|---|
| `ABORTED: another apply holds ….lock` | Another `apply` is still running (check `ps`). Wait for it; don't delete the lock |
| `target has 2 Xs named '…'` | Duplicate names on the target. Rename or delete one in the UI, then re-run |
| `source has duplicate … names` | Names are the match key. Rename on the source and take a new snapshot |
| `HTTP 403` on every call | Wrong key for that instance, or a proxy blocking the client. The tool sends its own User-Agent because some proxies block Python's default one |
| `HTTP 400` on a list call | `limit` above 100. The tool pages at 100 |
| Counts differ in `verify` | Read the plan table above it: it lists what's still missing |

## Code

`scripts/project_migrate/` (standard library only) and tests in `tests/project_migrate/`. The
tests run against an in-memory fake Rhesis server, so no backend or Docker is needed:

```bash
uvx --with pytest pytest tests/project_migrate
```
