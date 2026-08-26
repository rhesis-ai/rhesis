/**
 * Cell state as a pure function of time.
 *
 * The strip appears to fill left-to-right, but nothing here sweeps or eases
 * across a row. Columns are ordered by execution start, workers pull the
 * leftmost queued tests, and each cell simply reports what its test was doing
 * at time `t`. The advancing frontier -- and its raggedness, where a slow test
 * leaves an amber notch behind resolved neighbours -- falls out of that. Do
 * not add a fill animation: it would desynchronise from the data the moment
 * one test ran long.
 *
 * Everything is a pure function of (timing, verdict, t) with no mutable
 * animation state, which is what makes replay and mid-run joins free.
 */

import {
  CHAR_TO_STATE,
  type CellState,
  type GroupTestAggregate,
} from './verdict-model';
import type { VerdictRow } from '@/utils/api-client/interfaces/test-run';

/** One test's phase boundaries, in seconds since the run's timing origin. */
export interface TestTiming {
  startedAt: number | null;
  generatedAt: number | null;
  resolvedAt: number | null;
}

export type TestTimingMap = Map<string, TestTiming>;

/**
 * Longest window the per-metric reveal is spread over. The cascade exists to
 * show that judges return one after another, not to stall a resolved row.
 */
const MAX_STAGGER_SPAN = 1.7;

/**
 * Fraction of a test's total duration treated as its evaluation tail when the
 * generating -> evaluating boundary wasn't reported. Both execution paths
 * report it (sequential fires it from inside execute_test's call chain, not
 * its own loop -- see jobs/execution/sequential.py), so this is a defensive
 * fallback for a dropped timestamp (a Redis hiccup, a TTL lapse), not the
 * expected case for either path.
 */
const SEQUENTIAL_TAIL_RATIO = 0.3;

/** Jitter as a fraction of one metric's slot. Under 0.5 so reveals can't reorder. */
const SLOT_JITTER = 0.25;

const DS_PER_SECOND = 10;

/** Deterministic [0,1) from a test id and metric index, so replays match. */
function seededUnit(testId: string, metricIndex: number): number {
  let h = 2166136261 ^ metricIndex;
  for (let i = 0; i < testId.length; i++) {
    h ^= testId.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 100000) / 100000;
}

/** Where evaluation began: measured when known, else inferred from the tail. */
function evaluationStart(timing: TestTiming): number | null {
  if (timing.generatedAt !== null) return timing.generatedAt;
  if (timing.resolvedAt === null || timing.startedAt === null) return null;
  const duration = timing.resolvedAt - timing.startedAt;
  return timing.resolvedAt - duration * SEQUENTIAL_TAIL_RATIO;
}

/**
 * When generation stops and evaluation starts. Infinity while a test is still
 * generating -- no end is known yet, so the whole column stays amber.
 */
function generationEnd(timing: TestTiming): number {
  return evaluationStart(timing) ?? Infinity;
}

/**
 * When metric `metricIndex` reveals its verdict.
 *
 * Anchored to the *end* of the measured evaluation window rather than its
 * start. Anchoring to generation-end instead would open a fixed ~1.7s window
 * that has almost always expired by the time verdicts reach the client (they
 * are persisted in one blob once every judge returns), so every metric would
 * resolve in the same frame and the top-to-bottom cascade would never render.
 */
function verdictRevealAt(
  timing: TestTiming,
  resolvedAt: number,
  metricIndex: number,
  metricCount: number,
  testId: string
): number {
  // The last metric to return is what ended the test, so it reveals exactly
  // at resolvedAt -- jittering it would resolve the cell before the moment
  // the run actually recorded.
  if (metricCount <= 1 || metricIndex >= metricCount - 1) return resolvedAt;

  const from = evaluationStart(timing);
  const measured = from === null ? MAX_STAGGER_SPAN : resolvedAt - from;
  const span = Math.max(0, Math.min(MAX_STAGGER_SPAN, measured));
  if (span === 0) return resolvedAt;

  const slot = span / metricCount;
  const jitter =
    (seededUnit(testId, metricIndex) - 0.5) * 2 * SLOT_JITTER * slot;
  const reveal = resolvedAt - span + (metricIndex + 1) * slot + jitter;
  return Math.min(resolvedAt, reveal);
}

/**
 * State of one (test, metric) cell at time `t`.
 *
 * The stagger only delays the *reveal* of an outcome already known; it never
 * invents one, and a cell that has begun evaluating never falls back to
 * pending when its verdict is still outstanding.
 */
export function cellState(
  timing: TestTiming | undefined,
  verdictChar: string,
  metricIndex: number,
  metricCount: number,
  testId: string,
  t: number
): CellState {
  const known = CHAR_TO_STATE[verdictChar] ?? 'pending';
  if (known === 'na') return 'na';

  // No timing recorded (cache lapsed, run too large, or a test that never
  // executed): show the outcome as-is rather than animating from nothing.
  if (!timing || timing.startedAt === null) return known;

  if (t < timing.startedAt) return 'pending';
  if (t < generationEnd(timing)) return 'generating';

  // Generation is done. An outcome we don't have yet means judges are running.
  if (known === 'pending') return 'evaluating';

  if (timing.resolvedAt !== null) {
    const revealAt = verdictRevealAt(
      timing,
      timing.resolvedAt,
      metricIndex,
      metricCount,
      testId
    );
    if (t < revealAt) return 'evaluating';
  }

  return known;
}

/**
 * One test's overall state, for the group-header strip and KPI sparkline.
 *
 * A test reads as failed the moment any of its metrics fails, but only settles
 * once all of them have returned.
 */
export function rollUpState(
  timing: TestTiming | undefined,
  verdictChars: string[],
  testId: string,
  t: number
): CellState {
  const metricCount = verdictChars.length;
  const states: CellState[] = [];
  for (let j = 0; j < metricCount; j++) {
    states.push(cellState(timing, verdictChars[j], j, metricCount, testId, t));
  }

  const applicable = states.filter(s => s !== 'na');
  if (applicable.length === 0) return 'na';

  // pending and generating are properties of the test, so they hold for the
  // whole column at once.
  if (applicable.every(s => s === 'pending')) return 'pending';
  if (applicable.some(s => s === 'generating')) return 'generating';
  // A known failure wins immediately, even while a sibling metric is still
  // being revealed -- matching the most-severe-wins rule everywhere else in
  // this module. Checking evaluating/pending first would hide an already-red
  // metric behind the group header's amber pulse until every metric settles.
  if (applicable.some(s => s === 'failed' || s === 'error')) return 'failed';
  if (applicable.some(s => s === 'evaluating' || s === 'pending')) {
    return 'evaluating';
  }
  if (applicable.some(s => s === 'scored')) return 'scored';
  return 'passed';
}

/**
 * One CellState per test, rolled up across a set of metric rows -- the strip
 * shown on a requirement's group header.
 */
export function computeGroupRollup(
  groupRows: VerdictRow[],
  testIds: string[],
  timings: TestTimingMap,
  t: number
): CellState[] {
  const rollup: CellState[] = [];
  for (let i = 0; i < testIds.length; i++) {
    const testId = testIds[i];
    const chars = groupRows.map(row => row.verdicts[i] ?? '.');
    rollup.push(rollUpState(timings.get(testId), chars, testId, t));
  }
  return rollup;
}

/**
 * Total/passed/failed derived from the exact same per-test array as the strip,
 * so the numeric badges and the strip's red cells can never disagree. A test
 * counts as failed if its roll-up is 'failed' or 'error'; 'passed' counts only
 * fully-resolved tests with no failure, so in-flight tests count toward
 * neither -- mirroring how aggregateMetric excludes pending from a metric's
 * own pass rate.
 *
 * Generic over row scope: pass one requirement's rows for a group roll-up, or
 * every row for a run-wide one (the Pass Rate card's sparkline).
 */
export function aggregateGroupByTest(
  groupRows: VerdictRow[],
  testIds: string[],
  timings: TestTimingMap,
  t: number
): GroupTestAggregate {
  const rollup = computeGroupRollup(groupRows, testIds, timings, t);
  let passed = 0;
  let failed = 0;
  for (const state of rollup) {
    if (state === 'passed') passed++;
    else if (state === 'failed' || state === 'error') failed++;
  }
  return { total: rollup.length, passed, failed, rollup };
}

/**
 * Zip the matrix's parallel deciseconds columns into a per-test lookup keyed
 * by test id, converting to the seconds the run clock uses.
 */
export function buildTimingMap(
  testIds: string[],
  startedDs: (number | null)[] | null,
  generatedDs: (number | null)[] | null,
  resolvedDs: (number | null)[] | null
): TestTimingMap {
  const map: TestTimingMap = new Map();
  if (!startedDs && !generatedDs && !resolvedDs) return map;

  const toSeconds = (v: number | null | undefined): number | null =>
    typeof v === 'number' ? v / DS_PER_SECOND : null;

  for (let i = 0; i < testIds.length; i++) {
    const started = toSeconds(startedDs?.[i]);
    const generated = toSeconds(generatedDs?.[i]);
    const resolved = toSeconds(resolvedDs?.[i]);
    if (started === null && generated === null && resolved === null) continue;
    map.set(testIds[i], {
      startedAt: started,
      generatedAt: generated,
      resolvedAt: resolved,
    });
  }
  return map;
}

/** Latest moment any test reached, i.e. how long the run's animation runs. */
export function timelineDuration(timings: TestTimingMap): number {
  let max = 0;
  for (const timing of timings.values()) {
    for (const value of [
      timing.startedAt,
      timing.generatedAt,
      timing.resolvedAt,
    ]) {
      if (value !== null && value > max) max = value;
    }
  }
  return max;
}
