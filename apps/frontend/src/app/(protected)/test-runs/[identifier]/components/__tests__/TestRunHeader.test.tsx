import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import TestRunHeader from '../TestRunHeader';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type { UUID } from 'crypto';

const u = (n: number): UUID =>
  `00000000-0000-0000-0000-${String(n).padStart(12, '0')}` as UUID;

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

// ---- Fixtures ----

let _resultCounter = 0;

const makeTestRun = (
  overrides: Partial<TestRunDetail> = {}
): TestRunDetail => ({
  id: u(1),
  name: 'My Test Run',
  status: { id: u(2), name: 'Completed' },
  test_configuration: {
    id: u(6),
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    endpoint_id: u(5),
    test_set_id: u(3),
    user_id: u(7),
    test_set: {
      id: u(3),
      name: 'Safety Set',
      status: 'active',
      is_published: false,
      test_set_type: {
        id: u(4),
        type_name: 'Evaluation',
        type_value: 'evaluation',
      },
    },
    endpoint: {
      id: u(5),
      name: 'Production API',
      connection_type: 'REST',
      environment: 'production',
      config_source: 'manual',
      response_format: 'json',
    },
  },
  attributes: {
    started_at: '2024-01-01T10:00:00Z',
    completed_at: '2024-01-01T10:05:30Z',
    total_tests: 10,
  },
  tags: [],
  counts: { comments: 0, tasks: 0 },
  created_at: '2024-01-01T10:00:00Z',
  updated_at: '2024-01-01T10:05:30Z',
  ...overrides,
});

const makeResult = (status: 'pass' | 'fail' | 'error'): TestResultDetail =>
  ({
    id: u(++_resultCounter),
    test_configuration_id: u(11),
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    test_metrics: {
      execution_time: 0,
      metrics: {
        result: {
          score: status === 'pass' ? 1 : 0,
          reason: '',
          backend: 'test',
          description: '',
          is_successful: status === 'pass',
        },
      },
    },
    test_output: undefined,
    status: {
      id: u(10),
      name: status === 'pass' ? 'Pass' : status === 'fail' ? 'Fail' : 'Error',
    },
  }) as unknown as TestResultDetail;

// ---- Tests ----

describe('TestRunHeader', () => {
  it('renders Pass Rate card with correct percentage', () => {
    const results = [
      makeResult('pass'),
      makeResult('pass'),
      makeResult('pass'),
      makeResult('fail'),
    ];
    render(<TestRunHeader testRun={makeTestRun()} testResults={results} />);
    expect(screen.getByText('Pass Rate')).toBeInTheDocument();
    expect(screen.getByText('75.0%')).toBeInTheDocument();
  });

  it('shows 0.0% pass rate when all tests fail', () => {
    const results = [makeResult('fail'), makeResult('fail')];
    render(<TestRunHeader testRun={makeTestRun()} testResults={results} />);
    expect(screen.getByText('0.0%')).toBeInTheDocument();
  });

  it('shows 100.0% pass rate when all tests pass', () => {
    const results = [makeResult('pass'), makeResult('pass')];
    render(<TestRunHeader testRun={makeTestRun()} testResults={results} />);
    expect(screen.getByText('100.0%')).toBeInTheDocument();
  });

  it('renders Tests Executed card with total count', () => {
    const results = [
      makeResult('pass'),
      makeResult('fail'),
      makeResult('pass'),
    ];
    render(
      <TestRunHeader
        testRun={makeTestRun({
          attributes: {
            started_at: '2024-01-01T10:00:00Z',
            completed_at: '2024-01-01T10:05:30Z',
            total_tests: 3,
          },
        })}
        testResults={results}
      />
    );
    expect(screen.getByText('Tests Executed')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('Avg. 1 turn')).toBeInTheDocument();
  });

  it('prefers run total_tests over stale test set metadata when complete', () => {
    const base = makeTestRun();
    const testRun = makeTestRun({
      attributes: {
        started_at: '2024-01-01T10:00:00Z',
        completed_at: '2024-01-01T10:05:30Z',
        total_tests: 5,
      },
      test_configuration: {
        ...base.test_configuration!,
        test_set: {
          ...base.test_configuration!.test_set!,
          attributes: { metadata: { total_tests: 7 } },
        },
      },
    });
    const results = [
      makeResult('pass'),
      makeResult('fail'),
      makeResult('fail'),
      makeResult('fail'),
      makeResult('fail'),
    ];

    render(
      <TestRunHeader
        testRun={testRun}
        testResults={results}
        overallStats={{ total: 5, passed: 1, failed: 4, pass_rate: 20 }}
      />
    );

    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.queryByText('5/7')).not.toBeInTheDocument();
  });

  it('shows executed over expected while a run is in progress', () => {
    const testRun = makeTestRun({
      status: { id: u(20), name: 'progress' },
      attributes: {
        started_at: '2024-01-01T10:00:00Z',
        total_tests: 5,
      },
    });

    render(
      <TestRunHeader
        testRun={testRun}
        testResults={[makeResult('pass'), makeResult('fail')]}
        overallStats={{ total: 2, passed: 1, failed: 1, pass_rate: 50 }}
      />
    );

    expect(screen.getByText('2/5')).toBeInTheDocument();
  });

  it('averages turn depth from test output for multi-turn results', () => {
    const multiTurnResult = (turns: number): TestResultDetail =>
      ({
        ...makeResult('pass'),
        test_output: {
          turns_used: turns,
          output: '',
          context: [],
          session_id: 'session-1',
        },
      }) as unknown as TestResultDetail;

    render(
      <TestRunHeader
        testRun={makeTestRun()}
        testResults={[
          multiTurnResult(2),
          multiTurnResult(4),
          multiTurnResult(6),
        ]}
      />
    );

    expect(screen.getByText('Avg. 4 turns')).toBeInTheDocument();
  });

  it('renders Status card with duration', () => {
    const testRun = makeTestRun({
      attributes: {
        started_at: '2024-01-01T10:00:00Z',
        completed_at: '2024-01-01T10:05:30Z',
      },
    });
    render(<TestRunHeader testRun={testRun} testResults={[]} />);
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('5m 30s')).toBeInTheDocument();
  });

  it('shows "In Progress" duration when started but not completed', () => {
    const testRun = makeTestRun({
      attributes: { started_at: '2024-01-01T10:00:00Z' },
    });
    render(<TestRunHeader testRun={testRun} testResults={[]} />);
    // "In Progress" appears in both the duration value and the status chip
    const matches = screen.getAllByText('In Progress');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('shows N/A when no start time', () => {
    const testRun = makeTestRun({ attributes: {} });
    render(<TestRunHeader testRun={testRun} testResults={[]} />);
    // 'N/A' appears as both the duration value and its subtitle
    const matches = screen.getAllByText('N/A');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders Completed status chip on Status card', () => {
    const testRun = makeTestRun({
      status: { id: u(20), name: 'Completed' },
    });
    render(<TestRunHeader testRun={testRun} testResults={[]} />);
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });

  it('renders In Progress status below duration date', () => {
    const testRun = makeTestRun({
      status: { id: u(20), name: 'progress' },
      attributes: { started_at: '2024-01-01T10:00:00Z' },
    });
    render(<TestRunHeader testRun={testRun} testResults={[]} />);
    const matches = screen.getAllByText('In Progress');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders Failed status below duration date', () => {
    const testRun = makeTestRun({ status: { id: u(20), name: 'failed' } });
    render(<TestRunHeader testRun={testRun} testResults={[]} />);
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('renders Reviews card with default empty state', () => {
    render(<TestRunHeader testRun={makeTestRun()} testResults={[]} />);
    expect(screen.getByText('Reviews')).toBeInTheDocument();
    expect(screen.getByText('No reviews yet')).toBeInTheDocument();
  });

  it('renders Reviews card with review summary', () => {
    render(
      <TestRunHeader
        testRun={makeTestRun()}
        testResults={[]}
        reviewSummary={{
          testReviewCount: 2,
          metricReviewCount: 1,
          testCorrectionCount: 0,
          metricCorrectionCount: 0,
          correctionCount: 0,
          headline: '2 tests',
          subtitle: '1 metric · confirmed',
        }}
      />
    );
    expect(screen.getByText('Reviews')).toBeInTheDocument();
    expect(screen.getByText('2 tests')).toBeInTheDocument();
    expect(screen.getByText('1 metric · confirmed')).toBeInTheDocument();
  });
});
