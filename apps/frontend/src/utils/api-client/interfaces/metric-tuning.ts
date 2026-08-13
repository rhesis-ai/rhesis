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
/**
 * What the metric said about a case in the latest run.
 *
 * Read `verdict` beside the case's `expected` — the human's answer, which the
 * metric never sees. `error` set means the call failed, which is deliberately
 * not the same thing as the metric being wrong.
 */
export interface MetricTuningCaseResult {
  /** The metric's own verdict, as a string, whatever its score type. */
  verdict: string | null;
  /** The metric's explanation, where it produces one. */
  reasoning: string | null;
  /** Why the metric call failed for this case, when it did. */
  error: string | null;
  evaluated_at: string | null;
}

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
  /** The latest run's result, or null if the metric has not been run over it. */
  result: MetricTuningCaseResult | null;
  created_at: string;
  updated_at: string;
}

/**
 * Where a metric's latest tuning run got to.
 *
 * `never_run` rather than an absent object, so the tab renders one shape either
 * way.
 */
export type TuningRunStatus = 'never_run' | 'running' | 'completed' | 'failed';

/**
 * A metric's latest tuning run. Only the latest is kept — a new run overwrites
 * the previous one.
 */
export interface MetricTuningRun {
  status: TuningRunStatus;
  started_at: string | null;
  completed_at: string | null;
  /** How many cases the run covers, and how many it has finished so far. */
  total_cases: number;
  completed_cases: number;
  /** Cases whose metric call failed. Counted apart from the verdicts. */
  errored_cases: number;
  /** Why the run as a whole failed. One case failing does not fail a run. */
  error: string | null;
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
