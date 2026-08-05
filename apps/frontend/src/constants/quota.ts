/**
 * Canonical metered-resource identifiers. Mirrors the backend
 * `QuotaResource` enum in
 * `apps/backend/src/rhesis/backend/app/quota/__init__.py`. Keep in sync
 * when adding new metered resources.
 *
 * Uses a `const` object plus derived union type (idiomatic modern TS) so
 * values survive to runtime and typos in call sites surface as compile
 * errors, same pattern as `FeatureName`.
 */
export const QuotaResource = {
  TEST_EXECUTIONS: 'test_executions',
  TRACING_SPANS: 'tracing_spans',
  TEST_GENERATION: 'test_generation',
  MODEL_TOKENS: 'model_tokens',
  SEATS: 'seats',
  PROJECTS: 'projects',
  ENDPOINTS: 'endpoints',
} as const;

export type QuotaResource = (typeof QuotaResource)[keyof typeof QuotaResource];

/**
 * Human-readable labels for the usage dashboard.
 *
 * TEST_EXECUTIONS displays as "Test Runs" -- the platform's own term for
 * the thing being metered -- even though the resource key itself doesn't
 * change (it's the wire value, not UI copy).
 */
export const QUOTA_RESOURCE_LABELS: Record<QuotaResource, string> = {
  [QuotaResource.TEST_EXECUTIONS]: 'Test Runs',
  [QuotaResource.TRACING_SPANS]: 'Tracing Spans',
  [QuotaResource.TEST_GENERATION]: 'Test Generation',
  [QuotaResource.MODEL_TOKENS]: 'Model Tokens',
  [QuotaResource.SEATS]: 'Seats',
  [QuotaResource.PROJECTS]: 'Projects',
  [QuotaResource.ENDPOINTS]: 'Endpoints',
};

/**
 * Canonical display order for the usage dashboard. Which group (flow vs.
 * stock) each resource belongs to comes from `UsageResourceItem.kind` on
 * the API response, not a second hardcoded list here -- that list existed
 * once and had already drifted from the backend's own split by the time it
 * was caught in review.
 */
export const QUOTA_RESOURCE_ORDER: readonly QuotaResource[] = [
  QuotaResource.TEST_EXECUTIONS,
  QuotaResource.TRACING_SPANS,
  QuotaResource.TEST_GENERATION,
  QuotaResource.MODEL_TOKENS,
  QuotaResource.SEATS,
  QuotaResource.PROJECTS,
  QuotaResource.ENDPOINTS,
];
