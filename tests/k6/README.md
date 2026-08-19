# k6 load tests

Targets against `api.rhesis.ai` and `app.rhesis.ai`:

- **Public** (always run, no auth needed): `GET /health`, `GET /home`,
  `GET /` on the frontend. `/health` and `/home` aren't decorated with
  `@limiter.limit(...)` in `main.py`, so they sit outside the global slowapi
  rate limiter (100/hour, 1000/day per IP).
- **Authenticated** (runs only if `AUTH_TOKEN` is set): the highest-traffic
  read-only routes — `GET /test_runs/`, `/test_sets/`, `/annotations/`,
  `/projects/`, `/behaviors/`, `/test_sets/stats`, `/categories/`,
  `/test_results/`. All GET-only; nothing that creates, mutates, or deletes
  data. `/annotations/`, `/behaviors/`, and `/categories/` are project-scoped
  and need `PROJECT_ID` set alongside `AUTH_TOKEN` (see below) — without it
  they 404/422.

Every scenario carries a safety circuit-breaker (`safetyThresholds` in
`common.js`): if the error rate or p95 latency crosses the configured limit
for 15s, k6 aborts the run automatically instead of continuing to hammer a
degraded target.

## Getting a token (do this yourself — don't share your password)

Login no longer returns the token directly — `/auth/login/email` returns a
single-use `auth_code` (expires in 60s) that must be immediately exchanged
for the real token via `/auth/exchange-code`. Run both steps together, from
your own terminal. Your password stays on your machine; only the resulting
token gets used by the script:

```bash
CODE=$(curl -s -X POST https://api.rhesis.ai/auth/login/email \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}' \
  | jq -r '.auth_code')

curl -s -X POST https://api.rhesis.ai/auth/exchange-code \
  -H "Content-Type: application/json" \
  -d "{\"code\":\"$CODE\"}"
```

That last response has both `session_token` and `refresh_token`. (No `jq`?
Copy them out of the raw JSON by hand — but do it fast, the `auth_code`
expires in 60 seconds and can only be used once.)

**The session token itself is short-lived — in practice about 15 minutes**,
not the 7 days older docs claimed (it's the framework's default
`JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15`, left unset in prod config). It'll
expire mid-run for every scenario except `spike.js` (~3m), so also grab
`refresh_token` and pass it as `REFRESH_TOKEN` — the scripts use it to mint
a fresh session token every 10 minutes via `/auth/refresh`, no password
needed.

## Run

```bash
brew install k6          # or see https://k6.io/docs/get-started/installation
cd tests/k6

export AUTH_TOKEN="<paste the session_token here>"       # omit to test public routes only
export REFRESH_TOKEN="<paste the refresh_token here>"    # keeps AUTH_TOKEN alive past 15m
export PROJECT_ID="<your project id>"                    # needed for annotations/behaviors/categories

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
