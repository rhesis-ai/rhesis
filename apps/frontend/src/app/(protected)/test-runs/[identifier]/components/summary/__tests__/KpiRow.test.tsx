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

// The Usage card fetches its own totals; drive them rather than the network.
// Only the hook is stubbed. isCostKnown stays real, so these assertions
// exercise the actual "is this zero a figure or a shrug" rule.
jest.mock('../../../hooks/useTestRunUsage', () => ({
  ...jest.requireActual('../../../hooks/useTestRunUsage'),
  useTestRunUsage: jest.fn(() => null),
}));

import { useTestRunUsage } from '../../../hooks/useTestRunUsage';
import type { TraceMetricsResponse } from '@/utils/api-client/interfaces/telemetry';

function mockUsage(usage: Partial<TraceMetricsResponse> | null) {
  (useTestRunUsage as jest.Mock).mockReturnValue(usage);
}

beforeEach(() => {
  mockUsage(null);
});

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
      annotations_count: 0,
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

  it('omits the Cost card until the token and cost numbers arrive', () => {
    // Showing zeros would read as "this run cost nothing", which is a different
    // claim from "we do not know yet".
    mockUsage(null);
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({})}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.queryByText('Cost')).not.toBeInTheDocument();
  });

  it('leads the Cost card with cost, explained by tokens and the model', () => {
    mockUsage({
      total_traces: 12,
      enriched_traces: 12,
      priced_traces: 12,
      total_spans: 190,
      total_tokens: 45735,
      total_cost_usd: 0.012695,
      models_used: ['gpt-4o'],
      providers_used: ['openai'],
    });
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({})}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('Cost')).toBeInTheDocument();
    // The money formatter drops to two decimals above a cent, same as the
    // Traces page.
    expect(screen.getByText('$0.01')).toBeInTheDocument();
    expect(screen.getByText('45,735 tokens')).toBeInTheDocument();
    expect(screen.getByText('openai/gpt-4o')).toBeInTheDocument();
    expect(screen.queryByText('No cost data')).not.toBeInTheDocument();
  });

  it('holds the card back entirely for a run that traced nothing', () => {
    // An endpoint with no instrumentation produces no traces, so there is no
    // usage rather than usage of zero. "0 tokens, no cost data" would be an
    // answer to a question nobody asked.
    mockUsage({
      total_traces: 0,
      enriched_traces: 0,
      priced_traces: 0,
      total_spans: 0,
      total_tokens: 0,
      total_cost_usd: 0,
    });
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({})}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.queryByText('Cost')).not.toBeInTheDocument();
    expect(screen.queryByText('No cost data')).not.toBeInTheDocument();
  });

  it('shows a long model name in full rather than clipping it', () => {
    // The card is narrow; half a name answers nothing, so the line wraps.
    mockUsage({
      total_traces: 6,
      enriched_traces: 6,
      priced_traces: 6,
      total_spans: 60,
      total_tokens: 112557,
      total_cost_usd: 0.03,
      models_used: ['gemini-2.5-flash-preview-09-2025'],
      providers_used: ['gemini'],
    });
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({})}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    const label = screen.getByText('gemini/gemini-2.5-flash-preview-09-2025');
    expect(label).toBeInTheDocument();
    expect(label).not.toHaveStyle({ textOverflow: 'ellipsis' });
  });

  it('names only the first model, with a count for the rest', () => {
    mockUsage({
      total_traces: 4,
      enriched_traces: 4,
      priced_traces: 4,
      total_spans: 20,
      total_tokens: 900,
      total_cost_usd: 0.05,
      models_used: ['gpt-4o', 'claude-sonnet-4', 'gemini-2.5-flash'],
      providers_used: ['openai', 'anthropic', 'gemini'],
    });
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({})}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('openai/gpt-4o +2')).toBeInTheDocument();
  });

  it('drops the model when the run reported none', () => {
    mockUsage({
      total_traces: 2,
      enriched_traces: 2,
      priced_traces: 2,
      total_spans: 6,
      total_tokens: 400,
      total_cost_usd: 0.004,
      models_used: [],
      providers_used: [],
    });
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({})}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    // No trailing separator with nothing after it.
    expect(screen.getByText('400 tokens')).toBeInTheDocument();
    expect(screen.queryByText('·')).not.toBeInTheDocument();
  });

  it('says there is no cost data, and why, when nothing could be priced', () => {
    // Tokens come off the spans immediately; cost waits for enrichment, and
    // never arrives for a model with no published price. A $0.00 here would
    // claim the run was free, which is the one reading that is certainly wrong.
    mockUsage({
      total_traces: 3,
      enriched_traces: 3,
      priced_traces: 0,
      total_spans: 40,
      total_tokens: 9120,
      total_cost_usd: 0,
    });
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({})}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('No cost data')).toBeInTheDocument();
    expect(screen.getByText(/9,120 tokens/)).toBeInTheDocument();
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument();
  });

  it('says it is still working while enrichment has traces left', () => {
    // Distinct from "nothing here can be priced": that one is final and gets
    // an explanation, this one just needs a moment.
    mockUsage({
      total_traces: 10,
      enriched_traces: 4,
      priced_traces: 0,
      total_spans: 30,
      total_tokens: 2200,
      total_cost_usd: 0,
    });
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({})}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('Working out what this cost')).toBeInTheDocument();
    expect(screen.queryByText('No cost data')).not.toBeInTheDocument();
  });

  it('links the unpriced explanation to the costs documentation', () => {
    mockUsage({
      total_traces: 1,
      enriched_traces: 1,
      priced_traces: 0,
      total_spans: 2,
      total_tokens: 10,
      total_cost_usd: 0,
    });
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({})}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByRole('link', { name: 'Why?' })).toHaveAttribute(
      'href',
      expect.stringContaining('tracing/costs')
    );
  });

  it('shows $0.00 when the run really was free', () => {
    // Priced traces that add up to nothing. "No cost data" above is for a zero
    // nobody computed; this one is an answer.
    mockUsage({
      total_traces: 2,
      enriched_traces: 2,
      priced_traces: 2,
      total_spans: 8,
      total_tokens: 640,
      total_cost_usd: 0,
    });
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({})}
        testRun={makeTestRun()}
        isRunning={false}
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.getByText('$0.00')).toBeInTheDocument();
    expect(screen.queryByText('No cost data')).not.toBeInTheDocument();
  });

  it('tells the hook whether the run is still going', () => {
    // The hook stops polling on its own terms; it cannot work out on its own
    // that a run is mid-flight.
    mockUsage({
      total_traces: 1,
      enriched_traces: 0,
      priced_traces: 0,
      total_spans: 1,
      total_tokens: 5,
      total_cost_usd: 0,
    });
    const testRun = makeTestRun();
    renderWithClock(
      <KpiRow
        matrix={makeMatrix({})}
        testRun={testRun}
        isRunning
        testIds={[]}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(useTestRunUsage).toHaveBeenCalledWith(testRun.id, true);
  });
});
