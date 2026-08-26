import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';
import RunSummary from '../RunSummary';
import type {
  VerdictMatrix,
  TestRunDetail,
} from '@/utils/api-client/interfaces/test-run';

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

function makeMatrix(overrides: Partial<VerdictMatrix> = {}): VerdictMatrix {
  return {
    test_run_id: 'run-1',
    project_id: 'proj-1',
    status: 'progress',
    is_terminal: false,
    version: 1,
    test_ids: ['t1'],
    test_status: '.',
    requirements: [],
    rows: [],
    kpis: {
      pass_rate: null,
      tests_executed: 0,
      tests_total: 1,
      verdicts_resolved: 0,
      verdicts_planned: 1,
      failures: 0,
    },
    ...overrides,
  };
}

function makeTestRun(overrides: Partial<TestRunDetail> = {}): TestRunDetail {
  return {
    id: 'run-1',
    name: 'Test Run 1',
    status: { name: 'Progress' },
    attributes: {
      started_at: '2026-01-01T00:00:00Z',
    },
    ...overrides,
  } as TestRunDetail;
}

let mockMatrix: VerdictMatrix | undefined;
jest.mock('../hooks/useTestRunLive', () => ({
  useTestRunLive: () => ({
    matrix: mockMatrix,
    isLoading: false,
    isTerminal: mockMatrix?.is_terminal ?? false,
    isConnected: true,
  }),
}));

function setMatchMediaNarrow(isNarrow: boolean) {
  window.matchMedia = jest.fn().mockImplementation(query => ({
    matches: isNarrow,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  }));
}

describe('RunSummary', () => {
  beforeEach(() => {
    mockMatrix = makeMatrix();
  });

  it('renders the density control at a normal viewport width', () => {
    setMatchMediaNarrow(false);
    render(<RunSummary testRunId="run-1" testRun={makeTestRun()} />);

    expect(screen.getByRole('radiogroup')).toBeInTheDocument();
  });

  it('hides the density control and forces Numbers below 720px', () => {
    setMatchMediaNarrow(true);
    mockMatrix = makeMatrix({
      requirements: [{ id: 'req-1', name: 'Safety', metric_keys: ['m1'] }],
      rows: [
        {
          requirement_id: 'req-1',
          metric_key: 'm1',
          metric_name: 'Toxicity',
          metric_id: 'mid-1',
          ambiguous: false,
          verdicts: 'P',
          overrides: '0',
          passed: 1,
          failed: 0,
          pending: 0,
        },
      ],
    });

    render(<RunSummary testRunId="run-1" testRun={makeTestRun()} />);

    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
    // Numbers mode shows the Total column; forcing it doesn't touch the
    // persisted preference, only what's rendered.
    expect(screen.getByText('Total')).toBeInTheDocument();
  });
});
