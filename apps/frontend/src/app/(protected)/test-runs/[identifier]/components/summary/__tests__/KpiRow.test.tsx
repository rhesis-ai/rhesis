import React from 'react';
import { render, screen, fireEvent, within } from '@/test-utils';
import '@testing-library/jest-dom';
import lightTheme from '@/styles/theme';
import KpiRow from '../KpiRow';
import RunClockProvider from '../RunClockProvider';
import type { TestTimingMap } from '../verdict-timeline';
import type {
  VerdictMatrix,
  VerdictRow,
  TestRunDetail,
} from '@/utils/api-client/interfaces/test-run';

beforeAll(() => {
  HTMLCanvasElement.prototype.getContext = jest.fn().mockReturnValue({
    clearRect: jest.fn(),
    save: jest.fn(),
    restore: jest.fn(),
    scale: jest.fn(),
    beginPath: jest.fn(),
    roundRect: jest.fn(),
    rect: jest.fn(),
    fill: jest.fn(),
    stroke: jest.fn(),
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 0,
    globalAlpha: 1,
  });
});

function renderWithClock(ui: React.ReactElement) {
  return render(<RunClockProvider active={false}>{ui}</RunClockProvider>);
}

const EMPTY_TIMINGS: TestTimingMap = new Map();

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

function makeMatrix(
  kpiOverrides: Partial<VerdictMatrix['kpis']> = {},
  overrides: Partial<VerdictMatrix> = {}
): VerdictMatrix {
  return {
    test_run_id: 'run-1',
    project_id: 'proj-1',
    status: 'completed',
    is_terminal: true,
    version: 1,
    test_ids: ['t1'],
    test_started_ds: null,
    test_generated_ds: null,
    test_resolved_ds: null,
    elapsed_ds: null,
    test_status: '.',
    requirements: [],
    rows: [],
    kpis: {
      pass_rate: null,
      tests_executed: 0,
      tests_total: 0,
      verdicts_resolved: 0,
      verdicts_planned: 0,
      failures: 0,
      reviews_count: 0,
      ...kpiOverrides,
    },
    ...overrides,
  };
}

function makeTestRun(overrides: Partial<TestRunDetail> = {}): TestRunDetail {
  return {
    id: 'run-1',
    name: 'Test Run 1',
    status: { name: 'Completed' },
    attributes: {
      started_at: '2026-01-01T00:00:00Z',
      completed_at: '2026-01-01T00:00:24Z',
    },
    ...overrides,
  } as TestRunDetail;
}

describe('KpiRow', () => {
  it('displays dash for null pass rate', () => {
    renderWithClock(
      <KpiRow
        matrix={makeMatrix()}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('--')).toBeInTheDocument();
  });

  it('displays pass rate to one decimal place, with % as a suffix', () => {
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({ pass_rate: 0.85 })}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('85.0')).toBeInTheDocument();
    expect(screen.getByText('%')).toBeInTheDocument();
  });

  it('displays tests executed as value/suffix', () => {
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({
          tests_executed: 5,
          tests_total: 10,
        })}
        testRun={makeTestRun()}
        isRunning={true}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('/ 10')).toBeInTheDocument();
  });

  it('displays "Verdicts" title with value/suffix', () => {
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({
          verdicts_resolved: 8,
          verdicts_planned: 20,
        })}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('Verdicts')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getByText('/ 20')).toBeInTheDocument();
  });

  it('displays a "blocks" subtitle derived from per-requirement test/metric shape', () => {
    const rows = [
      makeRow({
        requirement_id: 'req-1',
        metric_key: 'm1',
        passed: 20,
        failed: 5,
        pending: 2,
      }),
      makeRow({
        requirement_id: 'req-2',
        metric_key: 'm2',
        passed: 8,
        failed: 2,
        pending: 1,
      }),
    ];
    renderWithClock(
      <KpiRow
        matrix={makeMatrix(
          {},
          {
            requirements: [
              { id: 'req-1', name: 'Req1', metric_keys: ['m1'] },
              { id: 'req-2', name: 'Req2', metric_keys: ['m2'] },
            ],
            rows,
          }
        )}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    // req-1: 27 tests x 1 metric, req-2: 11 tests x 1 metric
    expect(screen.getByText('blocks: 27×1 and 11×1')).toBeInTheDocument();
  });

  it('becomes a "Failures" card leading with the failure count when failures exist', () => {
    const rows = [makeRow({ metric_key: 'm1', failed: 3 })];
    renderWithClock(
      <KpiRow
        matrix={makeMatrix(
          {
            failures: 3,
            tests_total: 38,
            verdicts_resolved: 8,
            verdicts_planned: 20,
          },
          { rows }
        )}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('Failures')).toBeInTheDocument();
    expect(screen.queryByText('Verdicts')).not.toBeInTheDocument();
    // The headline number is now the failure count, not verdicts resolved,
    // suffixed the same "/ total" way every other card's headline is. No
    // "failed" label on the number itself -- the card title already says it.
    expect(screen.getByText('3')).toHaveStyle({
      color: lightTheme.palette.error.main,
    });
    // Scoped to the Failures card itself -- "/ 38" also appears on the Tests
    // executed card here, since both share kpis.tests_total as denominator.
    const failuresCard = screen.getByText('Failures').closest('.MuiCard-root');
    expect(failuresCard).not.toBeNull();
    expect(
      within(failuresCard as HTMLElement).getByText('/ 38')
    ).toBeInTheDocument();
    // Verdicts resolved/planned moves down to the subtitle instead.
    expect(screen.getByText(/8 of 20 verdicts/)).toBeInTheDocument();
    expect(screen.getByText(/1 metric affected/)).toBeInTheDocument();
  });

  it('falls back to the blocks subtitle on the Verdicts card when there are no failures', () => {
    const rows = [
      makeRow({ requirement_id: 'req-1', metric_key: 'm1', passed: 5 }),
    ];
    renderWithClock(
      <KpiRow
        matrix={makeMatrix(
          { failures: 0 },
          {
            requirements: [{ id: 'req-1', name: 'Req1', metric_keys: ['m1'] }],
            rows,
          }
        )}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.queryByText(/failed/)).not.toBeInTheDocument();
    expect(screen.getByText('blocks: 5×1')).toBeInTheDocument();
  });

  it('shows progress bar when running', () => {
    const { container } = renderWithClock(
      <KpiRow
        matrix={makeMatrix({
          tests_executed: 5,
          tests_total: 10,
        })}
        testRun={makeTestRun()}
        isRunning={true}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    const progressBar = container.querySelector('[role="progressbar"]');
    expect(progressBar).toBeTruthy();
    expect(progressBar?.getAttribute('aria-valuenow')).toBe('50');
  });

  it('shows progress bar when terminal too, filled to completion', () => {
    const { container } = renderWithClock(
      <KpiRow
        matrix={makeMatrix({
          tests_executed: 10,
          tests_total: 10,
        })}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    const progressBar = container.querySelector('[role="progressbar"]');
    expect(progressBar).toBeTruthy();
    expect(progressBar?.getAttribute('aria-valuenow')).toBe('100');
  });

  it('shows a "N of M tests" subtitle and sparkline strip on the Pass Rate card', () => {
    const rows = [
      makeRow({
        metric_key: 'm1',
        verdicts: 'PPF',
        passed: 2,
        failed: 1,
        pending: 0,
      }),
    ];
    renderWithClock(
      <KpiRow
        matrix={makeMatrix(
          { pass_rate: 0.5 },
          {
            test_ids: ['t1', 't2', 't3'],
            requirements: [{ id: 'req-1', name: 'Req1', metric_keys: ['m1'] }],
            rows,
          }
        )}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={['t1', 't2', 't3']}
        timings={EMPTY_TIMINGS}
      />
    );
    // 2 of 3 tests passed (verdicts 'PPF')
    expect(screen.getByText('2 of 3 tests')).toBeInTheDocument();
  });

  it('shows elapsed run time on the Tests Executed card when terminal', () => {
    renderWithClock(
      <KpiRow
        matrix={makeMatrix()}
        testRun={makeTestRun({
          attributes: {
            started_at: '2026-01-01T00:00:00Z',
            completed_at: '2026-01-01T00:00:24Z',
          },
        })}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('Ran for 0m 24s')).toBeInTheDocument();
  });

  it('does not show elapsed time while running', () => {
    renderWithClock(
      <KpiRow
        matrix={makeMatrix()}
        testRun={makeTestRun()}
        isRunning={true}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.queryByText(/Ran for/)).not.toBeInTheDocument();
  });

  it('calls onViewFailures when the Failures card is clicked and failures exist', () => {
    const onViewFailures = jest.fn();
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({ failures: 2 })}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
        onViewFailures={onViewFailures}
      />
    );
    fireEvent.click(screen.getByText('Failures'));
    expect(onViewFailures).toHaveBeenCalledTimes(1);
  });

  it('does not make the Verdicts card clickable when there are no failures', () => {
    const onViewFailures = jest.fn();
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({ failures: 0 })}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
        onViewFailures={onViewFailures}
      />
    );
    fireEvent.click(screen.getByText('Verdicts'));
    expect(onViewFailures).not.toHaveBeenCalled();
  });

  it('shows "No reviews yet" on the Reviews card when nothing has been reviewed', () => {
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({ reviews_count: 0 })}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('Reviews')).toBeInTheDocument();
    expect(screen.getByText('No reviews yet')).toBeInTheDocument();
  });

  it('shows the review count and a "of N tests" subtitle when reviews exist', () => {
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({ reviews_count: 3, tests_executed: 5 })}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('of 5 tests')).toBeInTheDocument();
  });
});
