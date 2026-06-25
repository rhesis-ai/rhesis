/**
 * Canonical entity-type taxonomy for the platform.
 *
 * A single generic definition for the kinds of entities the app references (for
 * comments, tasks, tags, etc.) instead of per-feature copies. Feature modules
 * re-export this rather than redefining their own subset.
 *
 * Implemented as a `const` object + derived union (the `FeatureName`/`Capability`
 * pattern) rather than a TS `enum` so the names are usable as runtime values
 * (`EntityType.TASK`) while the type stays a string-literal union — i.e. raw
 * strings remain assignable, so existing call sites that pass `"Test"` etc. keep
 * compiling. Migrating those literals to `EntityType.*` can follow separately.
 */
export const EntityType = {
  TEST: 'Test',
  TEST_SET: 'TestSet',
  TEST_RUN: 'TestRun',
  TEST_RESULT: 'TestResult',
  PROMPT: 'Prompt',
  PROMPT_TEMPLATE: 'PromptTemplate',
  BEHAVIOR: 'Behavior',
  CATEGORY: 'Category',
  ENDPOINT: 'Endpoint',
  USE_CASE: 'UseCase',
  RESPONSE_PATTERN: 'ResponsePattern',
  PROJECT: 'Project',
  ORGANIZATION: 'Organization',
  METRIC: 'Metric',
  MODEL: 'Model',
  SOURCE: 'Source',
  TASK: 'Task',
  TRACE: 'Trace',
} as const;

export type EntityType = (typeof EntityType)[keyof typeof EntityType];
