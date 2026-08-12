import { UUID } from 'crypto';

/**
 * A metric tuning case: one labelled example of what a metric should say.
 *
 * `input`, `output` and `expected_output` are the case payload — what the metric
 * is shown. `expected` is what it should say about them, and is never shown to
 * it.
 *
 * `expected` is a plain string because the owning metric's `score_type` decides
 * how to read it — 'pass'/'fail' for binary, '1.0' for numeric, a category name
 * for categorical. The backend validates it against the metric on write, and
 * re-checks it on read to set `is_stale`.
 */
export interface MetricTuningCase {
  id: UUID;
  /** The input given to the system under test. */
  input: string;
  /** The answer the metric has to judge. */
  output: string;
  /** What the system under test should have answered, when the metric needs one. */
  expected_output: string | null;
  /** The verdict a human expects. Null on an unlabelled case, which scoring skips. */
  expected: string | null;
  /** Why that verdict is right. */
  rationale: string | null;
  /**
   * True when `expected` no longer fits the metric's current score type —
   * which happens when the score type is changed after the case was written.
   */
  is_stale: boolean;
  created_at: string;
  updated_at: string;
}

export interface MetricTuningCaseCreate {
  input: string;
  output: string;
  expected_output?: string | null;
  /** Omit to capture the case now and judge it later. */
  expected?: string | null;
  rationale?: string | null;
}

/**
 * Partial update — only the fields present are applied.
 *
 * `expected` reads absence and blankness differently: omitting it leaves the
 * stored verdict alone, while sending a blank one returns the case to unlabelled.
 */
export interface MetricTuningCaseUpdate {
  input?: string;
  output?: string;
  expected_output?: string | null;
  expected?: string | null;
  rationale?: string | null;
}

export interface MetricTuningCaseDeleteResponse {
  deleted: boolean;
  case_id: string;
}
