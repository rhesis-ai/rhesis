/**
 * Frontend outcome vocabulary mirror.
 *
 * Mirrors the two source-of-truth axes in the backend's
 * `apps/backend/src/rhesis/backend/app/outcomes.py`: `Execution` (did we
 * obtain a usable observation?) and `Verdict` (given it ran, did it meet its
 * criteria?). Both a test result and a trace carry this pair, already
 * accounting for any human review, so nothing on the client needs to
 * re-derive pass/fail from raw metrics.
 *
 * Not a classifier: `outcomeOf` is a lossless, mechanical fold with no
 * synonym lists and no fallback guessing. Keep it in sync when the backend
 * enum changes; do not add branches or heuristics here -- that logic belongs
 * server-side.
 */

export type Execution = 'not_run' | 'running' | 'ok' | 'error' | 'cancelled';
export type Verdict = 'pass' | 'fail' | 'inconclusive';

export type Outcome =
  'pass' | 'fail' | 'inconclusive' | 'error' | 'cancelled' | 'pending';

/** Anything carrying the backend's outcome pair: a test result or a trace. */
export interface HasOutcome {
  execution: Execution;
  verdict: Verdict | null;
}

/**
 * Project (execution, verdict) down to the one value a component renders.
 * Mirrors `outcomes.py`'s `outcome_of` exactly, including its invariant:
 * `verdict` only matters when `execution === 'ok'`.
 */
export function outcomeOf(
  execution: Execution,
  verdict: Verdict | null
): Outcome {
  if (execution === 'ok') {
    return verdict ?? 'pending';
  }
  if (execution === 'error') return 'error';
  if (execution === 'cancelled') return 'cancelled';
  return 'pending'; // not_run, running
}

/**
 * The display vocabulary for status chips. Four values, matching the
 * backend's `TestResultStatus` enum (constants.py) -- `Inconclusive` is a
 * real bucket, not a flavour of error: it means the metric ran and
 * legitimately has no pass/fail verdict to give (a score with no
 * threshold). The verdict grid already renders it distinctly as `scored`.
 */
export type TestResultStatus = 'Pass' | 'Fail' | 'Error' | 'Inconclusive';

const DISPLAY_STATUS: Record<Outcome, TestResultStatus> = {
  pass: 'Pass',
  fail: 'Fail',
  inconclusive: 'Inconclusive',
  error: 'Error',
  // A persisted row never actually reaches these -- nothing writes a
  // cancelled or still-pending result -- but the projection must be total.
  cancelled: 'Error',
  pending: 'Error',
};

/** The chip status for an entity carrying the backend outcome pair. */
export function displayStatusOf(entity: HasOutcome): TestResultStatus {
  return DISPLAY_STATUS[outcomeOf(entity.execution, entity.verdict)];
}

/** Past-tense label matching a display status. */
export const STATUS_LABEL: Record<TestResultStatus, string> = {
  Pass: 'Passed',
  Fail: 'Failed',
  Error: 'Error',
  Inconclusive: 'Inconclusive',
};

/**
 * "Every metric passed", for the one case the backend genuinely cannot
 * answer: a single **turn** within a multi-turn trace. A turn is finer than
 * anything the server stores an outcome for (a Trace row carries the
 * combined turn + conversation verdict, not a per-turn one), so this rule
 * has to live on the client.
 *
 * Use this ONLY for per-turn or per-metric-group summaries. For anything
 * that has an `execution`/`verdict` pair -- a test result, a trace -- use
 * `displayStatusOf` instead; re-deriving there is what this whole module
 * exists to prevent.
 *
 * Note this is deliberately weaker than the backend's `classify_metrics`:
 * it has no notion of a crashed metric or an inconclusive one, because a
 * turn summary has nowhere to render those. Empty means false, not "pass
 * by default".
 */
export function allMetricsPassed(
  metrics: Array<{ is_successful?: boolean | null }>
): boolean {
  return metrics.length > 0 && metrics.every(m => m.is_successful === true);
}

// ---------------------------------------------------------------------------
// Pass rate
// ---------------------------------------------------------------------------

/**
 * The one pass-rate formula, as a percentage (0-100), or null when there is
 * nothing to rate.
 *
 * Mirrors the backend's `pass_rate_of_executed`: the denominator is what
 * actually resolved to pass or fail. An errored, inconclusive, or unrun
 * subject is excluded rather than counted as a failure, so the rate answers
 * "of the things we could judge, how many passed" instead of silently
 * changing meaning with the number of unrun items.
 *
 * Returns null (not 0) for an empty denominator so callers must decide how
 * "no data" renders instead of showing a misleading 0%.
 */
export function passRate(passed: number, failed: number): number | null {
  const resolved = passed + failed;
  if (resolved <= 0) return null;
  return (passed / resolved) * 100;
}

// ---------------------------------------------------------------------------
// Pass-rate banding
// ---------------------------------------------------------------------------

export type ReviewBand = 'ok' | 'watch' | 'review';

export interface ReviewBandInfo {
  band: ReviewBand;
  label: string;
  colorKey: 'success' | 'warning' | 'error';
}

/**
 * The single pass-rate colour scale. Previously three scales disagreed
 * (100/70 here, 70/40 on the insights summary bar, 80 on the history tab),
 * two of them on the same page, so the same rate could be green in one
 * widget and red in the next.
 */
export function getReviewBand(passRateValue: number): ReviewBandInfo {
  if (passRateValue >= 100) {
    return { band: 'ok', label: 'OK', colorKey: 'success' };
  }
  if (passRateValue >= 70) {
    return { band: 'watch', label: 'Watch', colorKey: 'warning' };
  }
  return { band: 'review', label: 'Needs Review', colorKey: 'error' };
}
