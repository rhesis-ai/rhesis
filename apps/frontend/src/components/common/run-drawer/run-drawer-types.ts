import type { UUID } from 'crypto';

export const METRIC_MODE = {
  TEST_SET: 'use_test_set',
  REQUIREMENT: 'use_requirement',
  CUSTOM: 'define_custom',
} as const;
export type MetricMode = (typeof METRIC_MODE)[keyof typeof METRIC_MODE];

export const SCORING_TARGET = { FRESH: 'fresh', REUSE: 'reuse' } as const;
export type ScoringTarget =
  (typeof SCORING_TARGET)[keyof typeof SCORING_TARGET];

export const EXECUTION_MODE = {
  PARALLEL: 'Parallel',
  SEQUENTIAL: 'Sequential',
} as const;
export type ExecutionMode =
  (typeof EXECUTION_MODE)[keyof typeof EXECUTION_MODE];

/** When the run starts: now, once at a set time, or on a repeating schedule. */
export const RUN_WHEN = { NOW: 'now', ONCE: 'once', REPEAT: 'repeat' } as const;
export type RunWhen = (typeof RUN_WHEN)[keyof typeof RUN_WHEN];

export const RUN_WHEN_LABEL: Record<RunWhen, string> = {
  [RUN_WHEN.NOW]: 'Now',
  [RUN_WHEN.ONCE]: 'Once, later',
  [RUN_WHEN.REPEAT]: 'Repeat',
};

/** What a new run covers: one picked test set, or every set carrying a tag. */
export const RUN_TARGET = { SET: 'set', TAG: 'tag' } as const;
export type RunTarget = (typeof RUN_TARGET)[keyof typeof RUN_TARGET];

export interface SelectedMetric {
  id: UUID;
  name: string;
  scope?: string[];
}
