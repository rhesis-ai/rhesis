import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import lightTheme from '@/styles/theme';
import RunClockProvider from '../RunClockProvider';
import RequirementTable from '../RequirementTable';
import type {
  VerdictMatrix,
  VerdictRow,
} from '@/utils/api-client/interfaces/test-run';
import type { TestTimingMap } from '../verdict-timeline';

jest.mock('@/hooks/useReducedMotion', () => ({
  useReducedMotion: () => false,
}));

beforeAll(() => {
  HTMLCanvasElement.prototype.getContext = jest.fn().mockReturnValue({
    clearRect: jest.fn(),
    save: jest.fn(),
    restore: jest.fn(),
    scale: jest.fn(),
    fillRect: jest.fn(),
    strokeRect: jest.fn(),
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 0,
    globalAlpha: 1,
  });
});

function renderWithClock(ui: React.ReactElement) {
  return render(<RunClockProvider active={false}>{ui}</RunClockProvider>);
}

function makeMatrix(overrides: Partial<VerdictMatrix> = {}): VerdictMatrix {
  return {
    test_run_id: 'run-1',
    project_id: 'proj-1',
    status: 'completed',
    is_terminal: true,
    version: 1,
    test_ids: ['t1', 't2', 't3'],
    test_started_ds: null,
    test_generated_ds: null,
    test_resolved_ds: null,
    elapsed_ds: null,
    test_status: '...',
    requirements: [
      {
        id: 'req-1',
        name: 'Safety',
        metric_keys: ['m1', 'm2'],
      },
    ],
    rows: [
      {
        requirement_id: 'req-1',
        metric_key: 'm1',
        metric_name: 'Safety: Toxicity Score',
        metric_id: 'mid-1',
        ambiguous: false,
        verdicts: 'PF.',
        overrides: '000',
        passed: 1,
        failed: 1,
        pending: 1,
      },
      {
        requirement_id: 'req-1',
        metric_key: 'm2',
        metric_name: 'Safety: Bias Check',
        metric_id: 'mid-2',
        ambiguous: false,
        verdicts: 'PP.',
        overrides: '000',
        passed: 2,
        failed: 0,
        pending: 1,
      },
    ],
    kpis: {
      pass_rate: 0.75,
      tests_executed: 3,
      tests_total: 3,
      verdicts_resolved: 4,
      verdicts_planned: 6,
      failures: 1,
      reviews_count: 0,
    },
    ...overrides,
  };
}

const EMPTY_TIMINGS: TestTimingMap = new Map();

describe('RequirementTable', () => {
  it('renders Requirements performance title', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="numbers"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    expect(screen.getByText('Requirements performance')).toBeInTheDocument();
  });

  it('renders density control with toggle buttons', () => {
    const onDensityChange = jest.fn();
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="detail"
        onDensityChange={onDensityChange}
        timings={EMPTY_TIMINGS}
      />
    );

    expect(screen.getByText('Numbers')).toBeInTheDocument();
    expect(screen.getByText('Numbers + Shape')).toBeInTheDocument();
    expect(screen.getByText('Detail')).toBeInTheDocument();
  });

  it('hides the density control when hideDensityControl is set (narrow viewport)', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="numbers"
        onDensityChange={jest.fn()}
        hideDensityControl
        timings={EMPTY_TIMINGS}
      />
    );

    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
  });

  it('shows empty state when no requirements', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix({ requirements: [] })}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    expect(screen.getByText('No verdict data available.')).toBeInTheDocument();
  });

  it('renders column headers, including the mode-specific strip label', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    expect(screen.getByText('Requirement / Metric')).toBeInTheDocument();
    expect(screen.getByText('Total')).toBeInTheDocument();
    expect(screen.getByText('Pass rate')).toBeInTheDocument();
    expect(screen.getByText('Review status')).toBeInTheDocument();
    // "Passed"/"Failed" also appear in the legend, so there are 2 of each.
    expect(screen.getAllByText('Passed').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Failed').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Distribution')).toBeInTheDocument();
  });

  it('changes the strip header label with density', () => {
    const { rerender } = renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="numbers"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );
    expect(screen.queryByText('Distribution')).not.toBeInTheDocument();
    expect(screen.queryByText('Every test')).not.toBeInTheDocument();

    rerender(
      <RunClockProvider active={false}>
        <RequirementTable
          matrix={makeMatrix()}
          density="detail"
          onDensityChange={jest.fn()}
          timings={EMPTY_TIMINGS}
        />
      </RunClockProvider>
    );
    expect(screen.getByText('Every test')).toBeInTheDocument();
  });

  it('renders requirement group name', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    expect(screen.getByText('Safety')).toBeInTheDocument();
  });

  it('renders a requirement-less group without a group header', () => {
    // Execution-time/test-set metrics never linked to a requirement --
    // "Unassigned" would misleadingly present them as a requirement.
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix({
          requirements: [
            { id: null, name: 'Unassigned', metric_keys: ['m1', 'm2'] },
          ],
        })}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    // The metric rows themselves still render (shared-prefix trimmed, same
    // as any other group)...
    expect(screen.getByText('Toxicity Score')).toBeInTheDocument();
    expect(screen.getByText('Bias Check')).toBeInTheDocument();
    // ...but there is no clickable/collapsible group header for them, and
    // no "Unassigned" label presented as if it were a requirement.
    expect(
      screen.queryByRole('button', { expanded: true })
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Unassigned')).not.toBeInTheDocument();
  });

  it('derives group header Total/Passed/Failed from the per-test rollup', () => {
    // m1 verdicts 'PF.', m2 verdicts 'PP.' across 3 tests:
    // t1: P,P -> passed. t2: F,P -> failed. t3: .,. -> pending (neither).
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    const groupHeader = screen.getByRole('button', { expanded: true });
    expect(groupHeader).toHaveTextContent('3'); // total
    expect(groupHeader).toHaveTextContent('1'); // passed and failed both 1
    expect(groupHeader).toHaveTextContent('50%'); // 1 passed / (1 passed + 1 failed)
  });

  it('toggles aria-expanded on group header click', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    const groupHeader = screen.getByRole('button', { expanded: true });
    expect(groupHeader).toBeInTheDocument();

    fireEvent.click(groupHeader);

    expect(screen.getByRole('button', { expanded: false })).toBeInTheDocument();
  });

  it('calls onViewRequirement from drilldown button, not header click', () => {
    const onViewRequirement = jest.fn();

    renderWithClock(
      <RequirementTable
        matrix={makeMatrix({
          rows: [
            {
              requirement_id: 'req-1',
              metric_key: 'm1',
              metric_name: 'Safety: Toxicity Score',
              metric_id: 'mid-1',
              ambiguous: false,
              verdicts: 'PF.',
              overrides: '000',
              passed: 1,
              failed: 1,
              pending: 1,
            },
          ],
        })}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
        onViewRequirement={onViewRequirement}
      />
    );

    // Header click should NOT trigger drilldown
    fireEvent.click(screen.getByText('Safety'));
    expect(onViewRequirement).not.toHaveBeenCalled();

    // The drilldown IconButton has an aria-label from the Tooltip
    const drilldownButton = screen.getByLabelText('View failures in Tests');
    fireEvent.click(drilldownButton);
    expect(onViewRequirement).toHaveBeenCalledWith('req-1');
  });

  it('calls onViewMetric when a failing metric row is clicked', () => {
    const onViewMetric = jest.fn();

    renderWithClock(
      <RequirementTable
        matrix={makeMatrix({
          rows: [
            {
              requirement_id: 'req-1',
              metric_key: 'm1',
              metric_name: 'Safety: Toxicity Score',
              metric_id: 'mid-1',
              ambiguous: false,
              verdicts: 'PF.',
              overrides: '000',
              passed: 1,
              failed: 1,
              pending: 1,
            },
          ],
        })}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
        onViewMetric={onViewMetric}
      />
    );

    const row = screen.getByRole('button', {
      name: 'View failures for Safety: Toxicity Score',
    });
    fireEvent.click(row);
    // A single metric has nothing to share a prefix with, so onViewMetric
    // receives the untrimmed name.
    expect(onViewMetric).toHaveBeenCalledWith(
      'Safety: Toxicity Score',
      'req-1'
    );
  });

  it('does not make a metric row clickable when it has no failures', () => {
    const onViewMetric = jest.fn();

    renderWithClock(
      <RequirementTable
        matrix={makeMatrix({
          rows: [
            {
              requirement_id: 'req-1',
              metric_key: 'm1',
              metric_name: 'Safety: Toxicity Score',
              metric_id: 'mid-1',
              ambiguous: false,
              verdicts: 'PP.',
              overrides: '000',
              passed: 2,
              failed: 0,
              pending: 1,
            },
          ],
        })}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
        onViewMetric={onViewMetric}
      />
    );

    expect(
      screen.queryByRole('button', {
        name: 'View failures for Safety: Toxicity Score',
      })
    ).not.toBeInTheDocument();
  });

  it('renders legend items', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    // "Passed"/"Failed" also appear as column headers, so there are 2 of each.
    expect(screen.getAllByText('Passed').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Failed').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('Generating')).toBeInTheDocument();
    expect(screen.getByText('Evaluating')).toBeInTheDocument();
    // Not "Scored" -- a metric with no pass/fail threshold is a permanent
    // outcome, not a provisional one, and "Scored" reads as if every other
    // result weren't also a score.
    expect(screen.getByText('No verdict')).toBeInTheDocument();
    expect(screen.queryByText('Scored')).not.toBeInTheDocument();
  });

  it('explains each legend status via the info icon tooltip', async () => {
    const user = userEvent.setup();
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    const infoIcon = screen.getByLabelText('What these statuses mean');
    await user.hover(infoIcon);

    expect(
      await screen.findByText(/Generation is done; this metric's judge/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/no pass\/fail threshold -- permanent, not provisional/)
    ).toBeInTheDocument();
  });

  it('colors the "No verdict" legend swatch differently from the in-flight states', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    // Permanent (no verdict) and temporary (in-flight) states must not share
    // a colour family, or a finished run's "No verdict" cells read as if
    // they were still being judged.
    const noVerdictSwatch = screen.getByText('No verdict').previousSibling;
    const generatingSwatch = screen.getByText('Generating').previousSibling;
    expect(noVerdictSwatch).toHaveStyle({
      backgroundColor: lightTheme.palette.info.main,
    });
    expect(generatingSwatch).not.toHaveStyle({
      backgroundColor: lightTheme.palette.info.main,
    });
  });

  it('distinguishes Generating from Evaluating by opacity, since they share a hue', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="shape"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    // Both are the theme's warning colour; a swatch forced to full opacity
    // would render them identically. The dim/bright split must survive into
    // the legend, not just the animated grid.
    const generatingSwatch = screen.getByText('Generating')
      .previousSibling as HTMLElement;
    const evaluatingSwatch = screen.getByText('Evaluating')
      .previousSibling as HTMLElement;
    const generatingOpacity = parseFloat(
      getComputedStyle(generatingSwatch).opacity
    );
    const evaluatingOpacity = parseFloat(
      getComputedStyle(evaluatingSwatch).opacity
    );

    expect(generatingOpacity).toBeLessThan(evaluatingOpacity);
    expect(generatingOpacity).toBeLessThan(1);
    expect(evaluatingOpacity).toBeLessThan(1);
  });

  it('renders a non-zero failed count in red, on both the metric row and the group header', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix({
          rows: [
            {
              requirement_id: 'req-1',
              metric_key: 'm1',
              metric_name: 'Safety: Toxicity Score',
              metric_id: 'mid-1',
              ambiguous: false,
              verdicts: 'PFF',
              overrides: '000',
              passed: 1,
              failed: 2,
              pending: 0,
            },
          ],
        })}
        density="numbers"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    // The metric row's own failed count (2) and the group header's rolled-up
    // failed count (also 2, since there's only one metric) both render red.
    const failedCells = screen.getAllByText('2');
    expect(failedCells.length).toBeGreaterThanOrEqual(2);
    for (const cell of failedCells) {
      expect(cell).toHaveStyle({ color: lightTheme.palette.error.main });
    }
  });

  describe('review status column', () => {
    function renderAt(
      density: 'numbers' | 'shape' | 'detail',
      row: VerdictRow
    ) {
      renderWithClock(
        <RequirementTable
          matrix={makeMatrix({
            requirements: [
              { id: 'req-1', name: 'Safety', metric_keys: ['m1'] },
            ],
            rows: [row],
            // One test id per verdict char -- the group header rolls up over
            // test_ids, so a short list would silently ignore later verdicts
            // and band the header off a different sample than the row.
            test_ids: row.verdicts.split('').map((_c, i) => `t${i + 1}`),
          })}
          density={density}
          onDensityChange={jest.fn()}
          timings={EMPTY_TIMINGS}
        />
      );
    }

    const baseRow: VerdictRow = {
      requirement_id: 'req-1',
      metric_key: 'm1',
      metric_name: 'Safety: Toxicity Score',
      metric_id: 'mid-1',
      ambiguous: false,
      verdicts: 'PPP',
      overrides: '000',
      passed: 3,
      failed: 0,
      pending: 0,
    };

    it('bands a clean metric as OK, on both the row and its group header', () => {
      renderAt('numbers', baseRow);
      // The metric row and the group header rolled up from it both band OK.
      expect(screen.getAllByText('OK')).toHaveLength(2);
    });

    it('bands a mostly-passing metric as Watch', () => {
      // 8/10 = 80%: below the 100 "OK" cut, above the 70 "review" cut.
      renderAt('numbers', {
        ...baseRow,
        verdicts: 'PPPPPPPPFF',
        overrides: '0000000000',
        passed: 8,
        failed: 2,
      });
      expect(screen.getAllByText('Watch').length).toBeGreaterThanOrEqual(1);
      expect(screen.queryByText('OK')).not.toBeInTheDocument();
    });

    it('bands a failing metric as Needs Review', () => {
      renderAt('numbers', {
        ...baseRow,
        verdicts: 'PFF',
        passed: 1,
        failed: 2,
      });
      expect(screen.getAllByText('Needs Review').length).toBeGreaterThanOrEqual(
        1
      );
    });

    it('shows no chip while nothing has resolved -- not a premature OK', () => {
      renderAt('numbers', {
        ...baseRow,
        verdicts: '...',
        passed: 0,
        failed: 0,
        pending: 3,
      });
      expect(screen.queryByText('OK')).not.toBeInTheDocument();
      expect(screen.queryByText('Watch')).not.toBeInTheDocument();
      expect(screen.queryByText('Needs Review')).not.toBeInTheDocument();
    });

    it('bands from the same rate it renders, so the two cannot disagree', () => {
      renderAt('numbers', {
        ...baseRow,
        verdicts: 'PPPPPPPPFF',
        overrides: '0000000000',
        passed: 8,
        failed: 2,
      });
      // 80% is a Watch on the shared 100/70 scale. If the chip ever banded
      // off a different denominator (e.g. including pending) this pairing
      // would break.
      expect(screen.getAllByText('80%').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Watch').length).toBeGreaterThanOrEqual(1);
    });

    it('is present in Numbers + Shape too', () => {
      renderAt('shape', baseRow);
      expect(screen.getAllByText('OK').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('verdict cell shape', () => {
    // Cells fill their strip's full height and share a cell width, so equal
    // strip heights are what make a rollup cell and the cells under it the
    // same shape. The rollup used to be pinned to its own 16px, which drew
    // the requirement row as squares above rectangular metric rows.
    function stripHeights(density: 'numbers' | 'shape' | 'detail'): string[] {
      const { container } = renderWithClock(
        <RequirementTable
          matrix={makeMatrix()}
          density={density}
          onDensityChange={jest.fn()}
          timings={EMPTY_TIMINGS}
        />
      );
      return Array.from(container.querySelectorAll('canvas[role="img"]')).map(
        c => (c.parentElement as HTMLElement).style.height
      );
    }

    it.each(['numbers', 'shape', 'detail'] as const)(
      'gives the requirement rollup and its metric rows one height in %s',
      density => {
        const heights = stripHeights(density);
        // One rollup + two metric rows in the default matrix.
        expect(heights).toHaveLength(3);
        expect(new Set(heights).size).toBe(1);
      }
    );

    it('still grows the cells from Shape to Detail', () => {
      // Guards the fix from being "make everything 0" -- the modes must
      // stay visually distinct.
      const shape = parseFloat(stripHeights('shape')[0]);
      const detail = parseFloat(stripHeights('detail')[0]);
      expect(shape).toBeGreaterThan(0);
      expect(detail).toBeGreaterThan(shape);
    });
  });

  it('renders a zero failed count in a muted color, not red', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix({
          rows: [
            {
              requirement_id: 'req-1',
              metric_key: 'm1',
              metric_name: 'Safety: Toxicity Score',
              metric_id: 'mid-1',
              ambiguous: false,
              verdicts: 'PPP',
              overrides: '000',
              passed: 3,
              failed: 0,
              pending: 0,
            },
          ],
        })}
        density="numbers"
        onDensityChange={jest.fn()}
        timings={EMPTY_TIMINGS}
      />
    );

    const failedCells = screen.getAllByText('0');
    expect(failedCells.length).toBeGreaterThanOrEqual(1);
    for (const cell of failedCells) {
      expect(cell).not.toHaveStyle({ color: lightTheme.palette.error.main });
    }
  });
});
