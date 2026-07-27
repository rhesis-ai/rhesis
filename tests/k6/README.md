# k6 load tests

Targets against `api.rhesis.ai` and `app.rhesis.ai`:

- **Public** (always run, no auth needed): `GET /health`, `GET /home`,
  `GET /` on the frontend. `/health` and `/home` aren't decorated with
  `@limiter.limit(...)` in `main.py`, so they sit outside the global slowapi
  rate limiter (100/hour, 1000/day per IP).
- **Authenticated** (runs only if `AUTH_TOKEN` is set): the highest-traffic
  read-only routes — `GET /test_runs/`, `/test_sets/`, `/test_results/stats`,
  `/projects/`, `/test_runs/stats`, `/test_sets/stats`, `/behaviors/`,
  `/test_results/`. All GET-only; nothing that creates, mutates, or deletes
  data.

Every scenario carries a safety circuit-breaker (`safetyThresholds` in
`common.js`): if the error rate or p95 latency crosses the configured limit
for 15s, k6 aborts the run automatically instead of continuing to hammer a
degraded target.

## Getting a token (do this yourself — don't share your password)

Get a session token by logging in directly against the API, from your own
terminal. Your password stays on your machine; only the resulting token gets
used by the script:

```bash
curl -s -X POST https://api.rhesis.ai/auth/login/email \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}' \
  | jq -r '.session_token'
```

(No `jq`? Drop the pipe and copy the `session_token` value out of the raw
JSON response by hand.)

Copy the printed token — it's a JWT valid for 7 days
(`JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080`), so it'll outlast even the soak
run without needing a refresh.

## Run

```bash
brew install k6          # or see https://k6.io/docs/get-started/installation
cd tests/k6

export AUTH_TOKEN="<paste the session_token here>"   # omit to test public routes only

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
