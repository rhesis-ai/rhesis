import { UUID } from 'crypto';
import type { ScoreType, ThresholdOperator } from './metric';

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

/** What a reviewer said about the verdict a metric gave. */
export type TuningDecision = 'accepted' | 'rejected';

/** The annotation that currently stands for a case. */
export interface MetricTuningAnnotation {
  id: UUID;
  decision: TuningDecision;
  /** Required on a rejection, always null on an accept. */
  comment: string | null;
  /** The raw metric verdict this judgement was made against. */
  verdict: string | null;
  annotated_at: string | null;
}

export type MetricTuningOutcome =
  | 'accepted'
  | 'rejected'
  | 'errored'
  | 'unannotated';

/**
 * A metric tuning case: one input plus the answer the metric has to judge.
 *
 * The case records no expected verdict — nothing is compared for equality.
 * After a run, a reviewer reads what the metric said and either accepts it or
 * rejects it with a comment, which is what `annotation` and `outcome` carry.
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
  /** The standing judgement, or null when the case is unannotated/errored. */
  annotation: MetricTuningAnnotation | null;
  /** Why an unannotated case is unannotated; null otherwise. */
  unannotated_reason: 'never_judged' | 'invalidated' | null;
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
 * How much of what the metric said the reviewer accepted — the one number to
 * watch while editing an evaluation prompt.
 *
 * `ratio` is null when nothing has been judged, never 1 — a set nobody has
 * looked at has no agreement rather than a perfect one. Unannotated and errored
 * cases are counted out of it and reported beside it instead.
 */
export interface MetricTuningAgreement {
  /** accepted / (accepted + rejected), or null when nothing has been judged. */
  ratio: number | null;
  /** The denominator. Never show the ratio without it. */
  judged: number;
  accepted: number;
  rejected: number;
  /** Left out of the ratio, never counted as accepted. */
  unannotated: number;
  /** The metric call failed — left out too, and reported apart. */
  errored: number;
  /**
   * Test results where someone overruled this metric on a real run. Outside the
   * ratio on purpose: that measures the curated tuning set, and a metric with no
   * tuning cases at all can still have a count here.
   */
  disagreements_in_runs: number;
}

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
  /**
   * Recomputed from the stored annotations on every read, so a judgement
   * recorded between runs moves it without a run.
   */
  agreement: MetricTuningAgreement;
  /**
   * True when the metric has changed in a verdict-affecting way since this run
   * started — so its agreement belongs to the earlier metric, not the one on
   * screen. Renaming a metric does not set this; editing its evaluation prompt
   * does.
   */
  predates_metric: boolean;
}

/**
 * The metric fields a model may rewrite from a reviewer's rejections.
 *
 * `score_type` and `categories` always come back as the metric already has
 * them — an improvement that moved either would invalidate every annotation on
 * the metric.
 */
export interface ImprovedMetricFields {
  name: string;
  description: string;
  evaluation_prompt: string;
  evaluation_steps: string;
  reasoning: string;
  explanation: string;
  score_type: ScoreType;
  min_score: number | null;
  max_score: number | null;
  threshold: number | null;
  threshold_operator: ThresholdOperator | null;
  categories: string[] | null;
  passing_categories: string[] | null;
}

/**
 * A proposed rewrite of a metric, read off the rejections its reviewers wrote.
 *
 * Producing one saves nothing. The reviewer sees the current fields beside these
 * and applies them with an ordinary metric update, or closes the dialog.
 */
export interface MetricTuningImprovement {
  improvement: ImprovedMetricFields;
  /** Fields whose proposed value differs from the metric's current one. */
  changed: (keyof ImprovedMetricFields)[];
  /** How many rejections it was written from, across all three sources. */
  rejections_used: number;
  /** Tuning cases someone curated for judging this metric. */
  tuning_rejections_used: number;
  /** People overruling this metric on a real test result. */
  run_rejections_used: number;
  /**
   * How many of those exist. Higher than `run_rejections_used` when the cap
   * bit, so the difference is shown rather than silently dropped.
   */
  run_rejections_found: number;
  /** Explorer tests labelled against what this metric said about them. */
  explorer_rejections_used: number;
  explorer_rejections_found: number;
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
export interface MetricTuningAnnotationCreate {
  decision: TuningDecision;
  /** Required on a rejection — the API rejects a blank one. */
  comment?: string | null;
}

export interface MetricTuningCaseDeleteResponse {
  deleted: boolean;
  case_id: string;
}
