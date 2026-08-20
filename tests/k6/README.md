# k6 load tests

Targets against `api.rhesis.ai` and `app.rhesis.ai`:

- **Public** (always run, no auth needed): `GET /health`, `GET /home`,
  `GET /` on the frontend. `/health` and `/home` aren't decorated with
  `@limiter.limit(...)` in `main.py`, so they sit outside the global slowapi
  rate limiter (100/hour, 1000/day per IP).
- **Authenticated** (runs only if `API_KEY` is set): the highest-traffic
  read-only routes — `GET /test_runs/`, `/test_sets/`, `/annotations/`,
  `/projects/`, `/behaviors/`, `/test_sets/stats`, `/categories/`,
  `/test_results/`. All GET-only; nothing that creates, mutates, or deletes
  data. `/annotations/`, `/behaviors/`, and `/categories/` are project-scoped
  and need `PROJECT_ID` set alongside `API_KEY` (see below) — without it
  they 404/422.

Every scenario carries a safety circuit-breaker (`safetyThresholds` in
`common.js`): if the error rate or p95 latency crosses the configured limit
for 15s, k6 aborts the run automatically instead of continuing to hammer a
degraded target.

## Getting an API key (do this yourself — don't share your password)

API keys authenticate the same way a session JWT does — `Authorization:
Bearer <token>` — but don't expire by default, so there's no refresh to
manage. `POST /tokens/` (which mints the key) itself requires a bearer
token, so the login → exchange-code steps below are a **one-time
bootstrap**: you need a JWT to mint your first key, but never again after
that — save the key and reuse it for every future run.

```bash
CODE=$(curl -s -X POST https://api.rhesis.ai/auth/login/email \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}' \
  | jq -r '.auth_code')

JWT=$(curl -s -X POST https://api.rhesis.ai/auth/exchange-code \
  -H "Content-Type: application/json" \
  -d "{\"code\":\"$CODE\"}" \
  | jq -r '.session_token')

curl -s -X POST https://api.rhesis.ai/tokens/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{"name": "k6-load-test-key"}' \
  | jq -r '.access_token'
```

(No `jq`? Copy the values out of the raw JSON by hand.) The printed key
starts with `rh-` and is only ever shown this once — save it somewhere.
Revoke it later with `DELETE /tokens/{id}` if you're done with it.

## Run

```bash
brew install k6          # or see https://k6.io/docs/get-started/installation
cd tests/k6

export API_KEY="<paste the rh-... key here>"   # omit to test public routes only
export PROJECT_ID="<your project id>"          # needed for annotations/behaviors/categories

k6 run load.js
k6 run stress.js
k6 run spike.js
k6 run soak.js      # ~64 minutes, run with `&` or nohup for long soaks
```

Override targets with `-e API_BASE=... -e FRONTEND_BASE=...` (e.g. to point
at staging instead of prod). JSON summaries land in `tests/k6/results/`
(run `k6` from inside `tests/k6/`, since that path is relative to cwd).

## Profiles (moderate aggressiveness)

| Test   | Profile                                              | Duration |
|--------|-------------------------------------------------------|----------|
| load   | ramp to 50 VUs, hold 10m, ramp down                   | ~18m     |
| stress | staged ramp 50→200 VUs, hold 5m, ramp down            | ~20m     |
| spike  | burst 5→300 VUs for 1m, back to 5 VU baseline         | ~3m      |
| soak   | 20 VUs held for 60m                                   | ~64m     |
