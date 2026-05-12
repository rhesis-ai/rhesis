/**
 * Canonical feature names. Mirrors the backend `FeatureName` enum in
 * `apps/backend/src/rhesis/backend/app/features/__init__.py`. Keep in
 * sync when adding new gated features.
 *
 * Uses a `const` object plus derived union type (idiomatic modern TS)
 * so values survive to runtime and typos in call sites like
 * `useFeature('...')` surface as compile errors.
 */
export const FeatureName = {
  SSO: 'sso',
} as const;

export type FeatureName = (typeof FeatureName)[keyof typeof FeatureName];
