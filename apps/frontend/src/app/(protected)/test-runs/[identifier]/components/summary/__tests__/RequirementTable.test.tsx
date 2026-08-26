import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';
import RunClockProvider from '../RunClockProvider';
import RequirementTable from '../RequirementTable';
import type { VerdictMatrix } from '@/utils/api-client/interfaces/test-run';

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
    },
    ...overrides,
  };
}

const EMPTY_SET = new Set<string>();

describe('RequirementTable', () => {
  it('renders Verdict Grid title', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="numbers"
        onDensityChange={jest.fn()}
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
      />
    );

    expect(screen.getByText('Verdict Grid')).toBeInTheDocument();
  });

  it('renders density control with toggle buttons', () => {
    const onDensityChange = jest.fn();
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="detail"
        onDensityChange={onDensityChange}
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
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
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
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
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
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
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
      />
    );

    expect(screen.getByText('Metric')).toBeInTheDocument();
    expect(screen.getByText('Total')).toBeInTheDocument();
    expect(screen.getByText('Pass rate')).toBeInTheDocument();
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
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
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
          generatingIds={EMPTY_SET}
          evaluatingIds={EMPTY_SET}
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
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
      />
    );

    expect(screen.getByText('Safety')).toBeInTheDocument();
  });

  it('derives group header Total/Passed/Failed from the per-test rollup', () => {
    // m1 verdicts 'PF.', m2 verdicts 'PP.' across 3 tests:
    // t1: P,P -> passed. t2: F,P -> failed. t3: .,. -> pending (neither).
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="shape"
        onDensityChange={jest.fn()}
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
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
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
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
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
        onViewRequirement={onViewRequirement}
      />
    );

    // Header click should NOT trigger drilldown
    fireEvent.click(screen.getByText('Safety'));
    expect(onViewRequirement).not.toHaveBeenCalled();

    // The drilldown IconButton has an aria-label from the Tooltip
    const drilldownButton = screen.getByLabelText(
      'View failures in Test Cases'
    );
    fireEvent.click(drilldownButton);
    expect(onViewRequirement).toHaveBeenCalledWith('req-1');
  });

  it('calls onViewMetric from the metric-row drilldown button', () => {
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
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
        onViewMetric={onViewMetric}
      />
    );

    const drilldownButton = screen.getByLabelText(
      'View failures in Test Cases'
    );
    fireEvent.click(drilldownButton);
    // A single metric has nothing to share a prefix with, so onViewMetric
    // receives the untrimmed name.
    expect(onViewMetric).toHaveBeenCalledWith(
      'Safety: Toxicity Score',
      'req-1'
    );
  });

  it('renders legend items', () => {
    renderWithClock(
      <RequirementTable
        matrix={makeMatrix()}
        density="shape"
        onDensityChange={jest.fn()}
        generatingIds={EMPTY_SET}
        evaluatingIds={EMPTY_SET}
      />
    );

    // "Passed"/"Failed" also appear as column headers, so there are 2 of each.
    expect(screen.getAllByText('Passed').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Failed').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });
});
