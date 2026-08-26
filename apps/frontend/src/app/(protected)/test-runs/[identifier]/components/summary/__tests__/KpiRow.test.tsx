import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';
import KpiRow from '../KpiRow';
import type {
  VerdictMatrix,
  TestRunDetail,
} from '@/utils/api-client/interfaces/test-run';

function makeMatrix(
  kpiOverrides: Partial<VerdictMatrix['kpis']> = {}
): VerdictMatrix {
  return {
    test_run_id: 'run-1',
    project_id: 'proj-1',
    status: 'completed',
    is_terminal: true,
    version: 1,
    test_ids: ['t1'],
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
      ...kpiOverrides,
    },
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
    render(
      <KpiRow matrix={makeMatrix()} testRun={makeTestRun()} isRunning={false} />
    );
    expect(screen.getByText('--')).toBeInTheDocument();
  });

  it('displays formatted pass rate percentage', () => {
    render(
      <KpiRow
        matrix={makeMatrix({ pass_rate: 0.85 })}
        testRun={makeTestRun()}
        isRunning={false}
      />
    );
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('displays tests executed ratio', () => {
    render(
      <KpiRow
        matrix={makeMatrix({
          tests_executed: 5,
          tests_total: 10,
        })}
        testRun={makeTestRun()}
        isRunning={true}
      />
    );
    expect(screen.getByText('5/10')).toBeInTheDocument();
  });

  it('displays "Metric Verdicts" title with ratio', () => {
    render(
      <KpiRow
        matrix={makeMatrix({
          verdicts_resolved: 8,
          verdicts_planned: 20,
        })}
        testRun={makeTestRun()}
        isRunning={false}
      />
    );
    expect(screen.getByText('Metric Verdicts')).toBeInTheDocument();
    expect(screen.getByText('8/20')).toBeInTheDocument();
  });

  it('displays failures count', () => {
    render(
      <KpiRow
        matrix={makeMatrix({ failures: 3 })}
        testRun={makeTestRun()}
        isRunning={false}
      />
    );
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('shows progress bar when running', () => {
    const { container } = render(
      <KpiRow
        matrix={makeMatrix({
          tests_executed: 5,
          tests_total: 10,
        })}
        testRun={makeTestRun()}
        isRunning={true}
      />
    );
    const progressBar = container.querySelector('[role="progressbar"]');
    expect(progressBar).toBeTruthy();
    expect(progressBar?.getAttribute('aria-valuenow')).toBe('50');
  });

  it('shows resolved verdicts subtitle', () => {
    render(
      <KpiRow
        matrix={makeMatrix({
          pass_rate: 0.5,
          verdicts_resolved: 12,
        })}
        testRun={makeTestRun()}
        isRunning={false}
      />
    );
    expect(screen.getByText('12 verdicts resolved')).toBeInTheDocument();
  });

  it('shows elapsed run time on the Tests Executed card when terminal', () => {
    render(
      <KpiRow
        matrix={makeMatrix()}
        testRun={makeTestRun({
          attributes: {
            started_at: '2026-01-01T00:00:00Z',
            completed_at: '2026-01-01T00:00:24Z',
          },
        })}
        isRunning={false}
      />
    );
    expect(screen.getByText('Ran for 0m 24s')).toBeInTheDocument();
  });

  it('does not show elapsed time while running', () => {
    render(
      <KpiRow matrix={makeMatrix()} testRun={makeTestRun()} isRunning={true} />
    );
    expect(screen.queryByText(/Ran for/)).not.toBeInTheDocument();
  });

  it('calls onViewFailures when the Failures card is clicked and failures exist', () => {
    const onViewFailures = jest.fn();
    render(
      <KpiRow
        matrix={makeMatrix({ failures: 2 })}
        testRun={makeTestRun()}
        isRunning={false}
        onViewFailures={onViewFailures}
      />
    );
    fireEvent.click(screen.getByText('Failures'));
    expect(onViewFailures).toHaveBeenCalledTimes(1);
  });

  it('does not make the Failures card clickable when there are no failures', () => {
    const onViewFailures = jest.fn();
    render(
      <KpiRow
        matrix={makeMatrix({ failures: 0 })}
        testRun={makeTestRun()}
        isRunning={false}
        onViewFailures={onViewFailures}
      />
    );
    fireEvent.click(screen.getByText('Failures'));
    expect(onViewFailures).not.toHaveBeenCalled();
  });
});
