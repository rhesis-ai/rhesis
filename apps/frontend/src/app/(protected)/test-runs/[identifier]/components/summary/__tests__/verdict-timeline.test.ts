import {
  cellState,
  rollUpState,
  buildTimingMap,
  computeGroupRollup,
  aggregateGroupByTest,
  timelineDuration,
  type TestTiming,
} from '../verdict-timeline';
import type { VerdictRow } from '@/utils/api-client/interfaces/test-run';

const TEST_ID = 'test-1';

function timing(overrides: Partial<TestTiming> = {}): TestTiming {
  return {
    startedAt: 10,
    generatedAt: 15,
    resolvedAt: 20,
    ...overrides,
  };
}

function makeRow(overrides: Partial<VerdictRow> = {}): VerdictRow {
  return {
    requirement_id: 'req-1',
    metric_key: 'm1',
    metric_name: 'm1',
    metric_id: null,
    ambiguous: false,
    verdicts: '',
    overrides: '',
    passed: 0,
    failed: 0,
    pending: 0,
    ...overrides,
  };
}

describe('cellState', () => {
  it('is pending before the test starts', () => {
    expect(cellState(timing(), '.', 0, 1, TEST_ID, 5)).toBe('pending');
  });

  it('is generating between start and generation end', () => {
    expect(cellState(timing(), '.', 0, 1, TEST_ID, 12)).toBe('generating');
  });

  it('is evaluating once generation ends but the verdict is unknown', () => {
    expect(cellState(timing(), '.', 0, 1, TEST_ID, 17)).toBe('evaluating');
  });

  it('resolves to the known verdict after the reveal moment', () => {
    expect(cellState(timing(), 'P', 0, 1, TEST_ID, 25)).toBe('passed');
    expect(cellState(timing(), 'F', 0, 1, TEST_ID, 25)).toBe('failed');
  });

  it('marks cells outside the requirement as na regardless of time', () => {
    expect(cellState(timing(), 'X', 0, 1, TEST_ID, 0)).toBe('na');
    expect(cellState(timing(), 'X', 0, 1, TEST_ID, 999)).toBe('na');
  });

  it('stays generating while a test is still in flight with no end known', () => {
    const inFlight = timing({ generatedAt: null, resolvedAt: null });
    expect(cellState(inFlight, '.', 0, 1, TEST_ID, 500)).toBe('generating');
  });

  it('renders the settled outcome when no timing was recorded', () => {
    // An old run whose cache lapsed, or one too large to animate.
    expect(cellState(undefined, 'P', 0, 1, TEST_ID, 0)).toBe('passed');
    expect(cellState(undefined, 'F', 0, 1, TEST_ID, 0)).toBe('failed');
    expect(cellState(undefined, '.', 0, 1, TEST_ID, 0)).toBe('pending');
  });

  // The regression this whole timing design exists to prevent: a cell that
  // has begun evaluating must never rewind to pending, which is how it would
  // read if the synthetic reveal window were consulted before the verdict was
  // actually known.
  it('never falls back to pending once evaluating has begun', () => {
    const t = timing();
    for (let time = t.startedAt ?? 0; time < 40; time += 0.25) {
      const state = cellState(t, '.', 0, 7, TEST_ID, time);
      if (time >= 15) {
        expect(state).toBe('evaluating');
      }
    }
  });

  it('keeps a resolved verdict resolved as time advances', () => {
    for (let time = 21; time < 60; time += 0.5) {
      expect(cellState(timing(), 'P', 0, 1, TEST_ID, time)).toBe('passed');
    }
  });
});

describe('cellState metric cascade', () => {
  // Criterion: a column resolves top to bottom across metric rows.
  it('reveals later metrics after earlier ones', () => {
    const t = timing({ generatedAt: 15, resolvedAt: 20 });
    const metricCount = 7;
    const revealTimes: number[] = [];

    for (let j = 0; j < metricCount; j++) {
      let revealed = 20;
      for (let time = 18; time <= 20.01; time += 0.01) {
        if (cellState(t, 'P', j, metricCount, TEST_ID, time) === 'passed') {
          revealed = time;
          break;
        }
      }
      revealTimes.push(revealed);
    }

    const sorted = [...revealTimes].sort((a, b) => a - b);
    expect(revealTimes).toEqual(sorted);
    expect(revealTimes[0]).toBeLessThan(revealTimes[metricCount - 1]);
  });

  // The reason the stagger anchors to resolvedAt rather than generatedAt:
  // verdicts land in one blob well after generation ends, so a
  // generation-anchored window would already have expired and every metric
  // would resolve in the same frame.
  it('still cascades when evaluation took far longer than the stagger span', () => {
    const slow = timing({ startedAt: 0, generatedAt: 2, resolvedAt: 30 });
    const atCascadeStart = cellState(slow, 'P', 6, 7, TEST_ID, 29);
    const afterEnd = cellState(slow, 'P', 6, 7, TEST_ID, 30.01);
    expect(atCascadeStart).toBe('evaluating');
    expect(afterEnd).toBe('passed');
  });

  it('pulses evaluating for the real duration, not a fixed window', () => {
    const slow = timing({ startedAt: 0, generatedAt: 2, resolvedAt: 30 });
    expect(cellState(slow, 'P', 0, 7, TEST_ID, 10)).toBe('evaluating');
    expect(cellState(slow, 'P', 0, 7, TEST_ID, 25)).toBe('evaluating');
  });

  it('no metric reveals after its test resolved', () => {
    const t = timing();
    for (let j = 0; j < 7; j++) {
      expect(cellState(t, 'P', j, 7, TEST_ID, 20.01)).toBe('passed');
    }
  });

  it('is deterministic across repeated calls, so replays match', () => {
    const t = timing();
    const first = cellState(t, 'P', 3, 7, TEST_ID, 19.4);
    for (let i = 0; i < 20; i++) {
      expect(cellState(t, 'P', 3, 7, TEST_ID, 19.4)).toBe(first);
    }
  });
});

describe('cellState with a dropped generating -> evaluating timestamp', () => {
  // Both execution paths report this boundary now, so a missing
  // generatedAt means the timestamp was lost (a Redis hiccup, a TTL lapse),
  // not that the test's execution path doesn't have one to report.
  const missingBoundary = timing({
    startedAt: 0,
    generatedAt: null,
    resolvedAt: 10,
  });

  it('falls back to inferring an evaluation tail from total duration', () => {
    expect(cellState(missingBoundary, '.', 0, 1, TEST_ID, 3)).toBe(
      'generating'
    );
  });

  it('shows a short evaluating tail before resolving', () => {
    expect(cellState(missingBoundary, 'P', 0, 1, TEST_ID, 9.9)).toBe(
      'evaluating'
    );
    expect(cellState(missingBoundary, 'P', 0, 1, TEST_ID, 10.01)).toBe(
      'passed'
    );
  });
});

describe('rollUpState', () => {
  it('is pending when every metric is pending', () => {
    expect(rollUpState(timing(), ['.', '.'], TEST_ID, 5)).toBe('pending');
  });

  it('is generating for the whole column at once', () => {
    expect(rollUpState(timing(), ['.', '.', '.'], TEST_ID, 12)).toBe(
      'generating'
    );
  });

  it('stays evaluating while any metric is unresolved', () => {
    expect(rollUpState(timing(), ['P', 'P', '.'], TEST_ID, 25)).toBe(
      'evaluating'
    );
  });

  it('fails as soon as one metric failed, once all have returned', () => {
    expect(rollUpState(timing(), ['P', 'F', 'P'], TEST_ID, 25)).toBe('failed');
  });

  it('passes only when every metric passed', () => {
    expect(rollUpState(timing(), ['P', 'P'], TEST_ID, 25)).toBe('passed');
  });

  it('treats an errored metric as a failure', () => {
    expect(rollUpState(timing(), ['P', 'E'], TEST_ID, 25)).toBe('failed');
  });

  it('is na when the test belongs to another requirement', () => {
    expect(rollUpState(timing(), ['X', 'X'], TEST_ID, 25)).toBe('na');
  });

  // A known failure must never hide behind a sibling's staggered reveal --
  // a child MetricRow can already be showing red while the group header
  // still says evaluating, which reads as the rollup contradicting its own
  // children.
  it('surfaces a revealed failure even while another metric is still staggering', () => {
    const t = timing({ startedAt: 0, generatedAt: 15, resolvedAt: 20 });
    // Metric 0 (not the last) has revealed 'F' well before resolvedAt;
    // metric 1 (the last) only reveals exactly at resolvedAt.
    expect(rollUpState(t, ['F', 'P'], TEST_ID, 19.5)).toBe('failed');
  });

  it('ignores na cells when rolling up a mixed row set', () => {
    expect(rollUpState(timing(), ['X', 'P'], TEST_ID, 25)).toBe('passed');
  });
});

describe('buildTimingMap', () => {
  it('converts deciseconds to seconds', () => {
    const map = buildTimingMap(['a'], [105], [220], [330]);
    expect(map.get('a')).toEqual({
      startedAt: 10.5,
      generatedAt: 22,
      resolvedAt: 33,
    });
  });

  it('keeps per-phase nulls', () => {
    const map = buildTimingMap(['a'], [10], [null], [null]);
    expect(map.get('a')).toEqual({
      startedAt: 1,
      generatedAt: null,
      resolvedAt: null,
    });
  });

  it('skips tests with no timing at all', () => {
    const map = buildTimingMap(
      ['a', 'b'],
      [10, null],
      [null, null],
      [null, null]
    );
    expect(map.has('a')).toBe(true);
    expect(map.has('b')).toBe(false);
  });

  it('returns an empty map when the run has no timing columns', () => {
    expect(buildTimingMap(['a', 'b'], null, null, null).size).toBe(0);
  });

  it('aligns by index against test_ids order', () => {
    const map = buildTimingMap(['a', 'b', 'c'], [10, 20, 30], null, null);
    expect(map.get('a')?.startedAt).toBe(1);
    expect(map.get('b')?.startedAt).toBe(2);
    expect(map.get('c')?.startedAt).toBe(3);
  });
});

describe('computeGroupRollup and aggregateGroupByTest', () => {
  const testIds = ['t1', 't2', 't3'];
  const rows = [makeRow({ verdicts: 'PFP' }), makeRow({ verdicts: 'PPP' })];
  const settled = buildTimingMap(testIds, null, null, null);

  it('produces one cell per test', () => {
    expect(computeGroupRollup(rows, testIds, settled, 100)).toHaveLength(3);
  });

  it('rolls a failure in any metric up to the test', () => {
    expect(computeGroupRollup(rows, testIds, settled, 100)).toEqual([
      'passed',
      'failed',
      'passed',
    ]);
  });

  it('derives counts from the same array as the strip', () => {
    const agg = aggregateGroupByTest(rows, testIds, settled, 100);
    expect(agg).toMatchObject({ total: 3, passed: 2, failed: 1 });
    expect(agg.rollup).toEqual(['passed', 'failed', 'passed']);
  });

  it('counts in-flight tests as neither passed nor failed', () => {
    const live = buildTimingMap(testIds, [0, 0, 0], [50, 50, 50], null);
    const agg = aggregateGroupByTest(rows, testIds, live, 2);
    expect(agg).toMatchObject({ total: 3, passed: 0, failed: 0 });
  });
});

describe('timelineDuration', () => {
  it('is the latest moment any test reached', () => {
    const map = buildTimingMap(['a', 'b'], [10, 20], [30, 40], [50, 90]);
    expect(timelineDuration(map)).toBe(9);
  });

  it('is zero for an empty map', () => {
    expect(timelineDuration(new Map())).toBe(0);
  });
});
