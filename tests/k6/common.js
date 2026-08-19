import http from 'k6/http';
import { check, group, sleep } from 'k6';

// Targets: unauthenticated, side-effect-free endpoints only.
// api.rhesis.ai/health and /home are not decorated with @limiter.limit(...)
// in apps/backend/src/rhesis/backend/app/main.py, so they're safe to load
// without tripping the global slowapi rate limiter (100/hour, 1000/day per IP).
export const API_BASE = __ENV.API_BASE || 'https://api.rhesis.ai';
export const FRONTEND_BASE = __ENV.FRONTEND_BASE || 'https://app.rhesis.ai';

// Obtain by logging in yourself and passing the result as -e AUTH_TOKEN=...
// (see tests/k6/README.md). Never embed a password in these scripts.
export const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
// Some authenticated routes are project-scoped and need this header alongside the token.
export const PROJECT_ID = __ENV.PROJECT_ID || '';

// The session token lasts ~15 minutes — shorter than every scenario but
// spike.js. REFRESH_TOKEN (also from /auth/exchange-code) lets each VU mint
// a fresh session token mid-run without the password ever touching this
// script. Optional: without it, AUTH_TOKEN is just used as-is for the run.
const REFRESH_INTERVAL_MS = 10 * 60 * 1000; // 5m margin inside the 15m expiry

let liveToken = AUTH_TOKEN;
let liveRefreshToken = __ENV.REFRESH_TOKEN || '';
let tokenMintedAt = -Infinity; // force an immediate refresh on first use

function refreshTokenIfDue() {
  if (!liveRefreshToken || Date.now() - tokenMintedAt < REFRESH_INTERVAL_MS) return;

  const res = http.post(`${API_BASE}/auth/refresh`, JSON.stringify({ refresh_token: liveRefreshToken }), {
    headers: { 'Content-Type': 'application/json' },
    tags: { name: 'auth_refresh' },
  });
  const accessToken = res.status === 200 ? res.json('access_token') : null;
  // Only advance tokenMintedAt on success — on failure, leave it stale so the
  // very next iteration retries instead of running on an expired token for
  // the rest of the 10-minute window.
  if (!accessToken) return;

  liveToken = accessToken;
  const rotatedRefreshToken = res.json('refresh_token');
  if (rotatedRefreshToken) liveRefreshToken = rotatedRefreshToken;
  tokenMintedAt = Date.now();
}

function authHeaders() {
  return {
    headers: liveToken
      ? { Authorization: `Bearer ${liveToken}`, ...(PROJECT_ID ? { 'X-Project-Id': PROJECT_ID } : {}) }
      : {},
  };
}

// Safety circuit-breaker shared by every scenario: if error rate or p95
// latency blows past these for delayAbortEval, k6 stops the run itself
// instead of continuing to hammer production.
export function safetyThresholds(p95Ms, failRate) {
  return {
    http_req_failed: [
      { threshold: `rate<${failRate}`, abortOnFail: true, delayAbortEval: '15s' },
    ],
    http_req_duration: [
      { threshold: `p(95)<${p95Ms}`, abortOnFail: true, delayAbortEval: '15s' },
    ],
  };
}

export function hitAll() {
  group('backend_health', () => {
    const res = http.get(`${API_BASE}/health`, { tags: { name: 'backend_health' } });
    check(res, { 'health status 200': (r) => r.status === 200 });
  });

  group('backend_home', () => {
    const res = http.get(`${API_BASE}/home`, { tags: { name: 'backend_home' } });
    check(res, { 'home status 200': (r) => r.status === 200 });
  });

  group('frontend_landing', () => {
    const res = http.get(`${FRONTEND_BASE}/`, { tags: { name: 'frontend_landing' } });
    check(res, { 'frontend status 200': (r) => r.status === 200 });
  });

  sleep(1);
}

const AUTH_ENDPOINTS = [
  { name: 'auth_test_runs', path: '/test_runs/?skip=0&limit=50&sort_by=created_at&sort_order=desc' },
  { name: 'auth_test_sets', path: '/test_sets/?skip=0&limit=50' },
  { name: 'auth_annotations', path: '/annotations/?skip=0&limit=50' },
  { name: 'auth_projects', path: '/projects/?skip=0&limit=10' },
  { name: 'auth_behaviors', path: '/behaviors/?skip=0&limit=20&sort_by=created_at&sort_order=desc' },
  { name: 'auth_test_sets_stats', path: '/test_sets/stats' },
  { name: 'auth_categories', path: '/categories/?skip=0&limit=10&sort_by=created_at&sort_order=desc' },
  { name: 'auth_test_results', path: '/test_results/?skip=0&limit=50' },
];

// Every distinct `name` tag used across hitAll() and hitAuthenticated(),
// kept in sync with those two functions. Used to break out per-endpoint
// latency in the summary (see perEndpointThresholds/buildSummary below).
export const ENDPOINT_TAGS = [
  'backend_health',
  'backend_home',
  'frontend_landing',
  ...AUTH_ENDPOINTS.map((e) => e.name),
];

// Highest-traffic authenticated GET endpoints (see tests/k6/README.md for
// how this list was derived). Skipped entirely when AUTH_TOKEN is unset, so
// the same scripts still work anonymously against just the public routes.
export function hitAuthenticated() {
  if (!AUTH_TOKEN) return;

  refreshTokenIfDue();

  for (const { name, path } of AUTH_ENDPOINTS) {
    group(name, () => {
      const res = http.get(`${API_BASE}${path}`, { ...authHeaders(), tags: { name } });
      check(res, { [`${name} status 200`]: (r) => r.status === 200 });
    });
  }

  sleep(1);
}

export function summaryPath(name) {
  return `results/${name}.json`;
}

// k6 only tracks a per-tag submetric (e.g. `http_req_duration{name:foo}`) if
// something references that tag combination — a threshold is the standard
// way to force it. `max>=0` is always true, so this never fails a test; it
// exists purely to make k6 compute per-endpoint stats we can read back in
// handleSummary.
export function perEndpointThresholds() {
  const thresholds = {};
  for (const tag of ENDPOINT_TAGS) {
    thresholds[`http_req_duration{name:${tag}}`] = ['max>=0'];
  }
  return thresholds;
}

function fmt(ms) {
  return ms === undefined ? '-'.padStart(8) : ms.toFixed(1).padStart(8);
}

// Per-endpoint latency breakdown, slowest (by p95) first — this is what
// pinpoints which specific route is behind an aggregate outlier like a
// 12s max in the combined http_req_duration.
export function endpointBreakdown(data) {
  const rows = [];
  for (const tag of ENDPOINT_TAGS) {
    const m = data.metrics[`http_req_duration{name:${tag}}`];
    if (!m) continue;
    const v = m.values;
    rows.push({ endpoint: tag, avg: v.avg, med: v.med, p90: v['p(90)'], p95: v['p(95)'], max: v.max });
  }
  rows.sort((a, b) => b.p95 - a.p95);
  return rows;
}

function formatBreakdown(rows) {
  const header = 'endpoint'.padEnd(28) + ['avg', 'med', 'p90', 'p95', 'max'].map((h) => h.padStart(8)).join('');
  const lines = rows.map(
    (r) =>
      r.endpoint.padEnd(28) + [r.avg, r.med, r.p90, r.p95, r.max].map(fmt).join('')
  );
  return [header, ...lines].join('\n');
}

// Shared handleSummary for every scenario script: writes the full k6 summary
// (plus the per-endpoint breakdown) to tests/k6/results/<name>.json, and
// prints a slowest-first latency table + error rate to stdout.
export function buildSummary(data, name) {
  const rows = endpointBreakdown(data);
  const text =
    `\n--- per-endpoint http_req_duration (ms), slowest p95 first ---\n${formatBreakdown(rows)}\n\n` +
    `error_rate: ${data.metrics.http_req_failed?.values?.rate}\n`;

  return {
    [summaryPath(name)]: JSON.stringify({ ...data, endpoint_breakdown: rows }, null, 2),
    stdout: text,
  };
}
