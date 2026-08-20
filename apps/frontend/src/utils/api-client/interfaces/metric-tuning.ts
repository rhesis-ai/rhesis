import { UUID } from 'crypto';

/**
 * What the metric said about a case in the latest run.
 *
 * `error` set means the call failed, which is deliberately not the same thing
 * as the metric being wrong.
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

/** The review that currently stands for a case. */
export interface MetricTuningReview {
  decision: 'accepted' | 'rejected';
  /** Required on a rejection, always null on an accept. */
  comment: string | null;
  /** The raw metric verdict this review was judging. */
  verdict: string | null;
  reviewed_at: string | null;
}

export type MetricTuningOutcome =
  | 'accepted'
  | 'rejected'
  | 'errored'
  | 'unreviewed';

/**
 * A metric tuning case: one input plus the answer the metric has to judge.
 *
 * The case records no expected verdict — nothing is compared for equality.
 * After a run, a reviewer reads what the metric said and either accepts it or
 * rejects it with a comment, which is what `review` and `outcome` carry.
 */
export interface MetricTuningCase {
  id: UUID;
  /** The input given to the system under test. */
  input: string;
  /** The answer the metric has to judge. */
  output: string;
  /** What the system under test should have answered, when the metric needs one. */
  reference_answer: string | null;
  /** The latest run's result, or null if the metric has not been run over it. */
  result: MetricTuningCaseResult | null;
  outcome: MetricTuningOutcome;
  /** The standing review, or null when the case is unreviewed/errored. */
  review: MetricTuningReview | null;
  /** Why an unreviewed case is unreviewed; null otherwise. */
  unreviewed_reason: 'never_judged' | 'invalidated' | null;
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
  reference_answer?: string | null;
}

/** Partial update — only the fields present are applied. */
export interface MetricTuningCaseUpdate {
  input?: string;
  output?: string;
  reference_answer?: string | null;
}

/** A reviewer's judgement of what the metric said. */
export interface MetricTuningReviewCreate {
  decision: 'accepted' | 'rejected';
  /** Required on a rejection — the API rejects a blank one. */
  comment?: string | null;
}

export interface MetricTuningCaseDeleteResponse {
  deleted: boolean;
  case_id: string;
}
