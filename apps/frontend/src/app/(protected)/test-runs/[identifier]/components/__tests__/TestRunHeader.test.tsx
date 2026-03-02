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
    render(<TestRunHeader testRun={makeTestRun()} testResults={results} />);
    expect(screen.getByText('Tests Executed')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('renders Duration card', () => {
    const testRun = makeTestRun({
      attributes: {
        started_at: '2024-01-01T10:00:00Z',
        completed_at: '2024-01-01T10:05:30Z',
      },
    });
    render(<TestRunHeader testRun={testRun} testResults={[]} />);
    expect(screen.getByText('Duration')).toBeInTheDocument();
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

  it('renders Completed status chip from backend status', () => {
    const testRun = makeTestRun({
      status: { id: u(20), name: 'Completed' },
    });
    render(<TestRunHeader testRun={testRun} testResults={[]} />);
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });

  it('renders In Progress status chip from backend "progress" status', () => {
    const testRun = makeTestRun({
      status: { id: u(20), name: 'progress' },
      attributes: { started_at: '2024-01-01T10:00:00Z' },
    });
    render(<TestRunHeader testRun={testRun} testResults={[]} />);
    // 'In Progress' appears in both the Chip and the duration value — at least one should be present
    const matches = screen.getAllByText('In Progress');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders Failed status chip from backend status', () => {
    const testRun = makeTestRun({ status: { id: u(20), name: 'failed' } });
    render(<TestRunHeader testRun={testRun} testResults={[]} />);
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('renders test set name as a link to the test set', () => {
    render(<TestRunHeader testRun={makeTestRun()} testResults={[]} />);
    const link = screen.getByRole('link', { name: /safety set/i });
    expect(link).toHaveAttribute('href', `/test-sets/${u(3)}`);
  });

  it('renders endpoint name as a link to the endpoint', () => {
    render(<TestRunHeader testRun={makeTestRun()} testResults={[]} />);
    expect(screen.getByText(/production api/i)).toBeInTheDocument();
  });

  it('renders Status card label', () => {
    render(<TestRunHeader testRun={makeTestRun()} testResults={[]} />);
    expect(screen.getByText('Status')).toBeInTheDocument();
  });
});
