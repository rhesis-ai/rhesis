import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import MetricTuningTab from '../MetricTuningTab';
import type {
  MetricTuningCase,
  MetricTuningRun,
} from '@/utils/api-client/interfaces/metric-tuning';

const mockGetTuningCases = jest.fn();
const mockCreateTuningCase = jest.fn();
const mockUpdateTuningCase = jest.fn();
const mockDeleteTuningCase = jest.fn();
const mockGetTuningRun = jest.fn();
const mockStartTuningRun = jest.fn();
const mockGetMetric = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getMetricTuningClient: () => ({
      getTuningCases: mockGetTuningCases,
      createTuningCase: mockCreateTuningCase,
      updateTuningCase: mockUpdateTuningCase,
      deleteTuningCase: mockDeleteTuningCase,
      getTuningRun: mockGetTuningRun,
      startTuningRun: mockStartTuningRun,
    }),
    getMetricsClient: () => ({
      getMetric: mockGetMetric,
    }),
  })),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

// Always allow editing — capability checks are not the focus of this test.
jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

const METRIC_ID = 'm1m1m1m1-0000-0000-0000-000000000001';

const CASE: MetricTuningCase = {
  id: 't1t1t1t1-0000-0000-0000-000000000001' as MetricTuningCase['id'],
  input: 'How are you?',
  output: 'I am fine, thanks.',
  expected_output: 'A polite reply.',
  expected: 'pass',
  rationale: 'polite answer',
  is_stale: false,
  result: null,
  created_at: '2026-08-06T00:00:00Z',
  updated_at: '2026-08-06T00:00:00Z',
};

const BINARY_METRIC = { score_type: 'binary' as const };

const NEVER_RUN: MetricTuningRun = {
  status: 'never_run',
  started_at: null,
  completed_at: null,
  total_cases: 0,
  completed_cases: 0,
  errored_cases: 0,
  error: null,
};

describe('MetricTuningTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetTuningCases.mockResolvedValue([]);
    mockGetMetric.mockResolvedValue(BINARY_METRIC);
    mockGetTuningRun.mockResolvedValue(NEVER_RUN);
  });

  it('shows the empty state when the metric has no cases', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('No tuning cases yet')).toBeInTheDocument();
    expect(mockGetTuningCases).toHaveBeenCalledWith(METRIC_ID);
  });

  it('lists existing cases', async () => {
    mockGetTuningCases.mockResolvedValue([CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('How are you?')).toBeInTheDocument();
    expect(screen.getByText('I am fine, thanks.')).toBeInTheDocument();
    expect(screen.getByText('polite answer')).toBeInTheDocument();
  });

  it('marks the tab as beta', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('beta')).toBeInTheDocument();
  });

  it('marks a stale case', async () => {
    mockGetTuningCases.mockResolvedValue([{ ...CASE, is_stale: true }]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('Stale')).toBeInTheDocument();
  });

  it('does not mark a case that still fits its metric', async () => {
    mockGetTuningCases.mockResolvedValue([CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('How are you?');
    expect(screen.queryByText('Stale')).not.toBeInTheDocument();
  });

  it('sends the expected output as part of the case', async () => {
    mockCreateTuningCase.mockResolvedValue(CASE);
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /add case/i }));
    fireEvent.change(await screen.findByLabelText(/^input/i), {
      target: { value: 'Tell me a joke' },
    });
    fireEvent.change(screen.getByLabelText(/^output/i), {
      target: { value: 'No.' },
    });
    fireEvent.change(screen.getByLabelText(/expected output/i), {
      target: { value: 'Here is a joke.' },
    });

    fireEvent.click(
      screen.getByRole('button', { name: /add case/i, hidden: false })
    );

    await waitFor(() => expect(mockCreateTuningCase).toHaveBeenCalled());
    expect(mockCreateTuningCase.mock.calls[0][1].expected_output).toBe(
      'Here is a joke.'
    );
  });

  it('omits an empty expected output rather than sending a blank', async () => {
    mockCreateTuningCase.mockResolvedValue(CASE);
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /add case/i }));
    fireEvent.change(await screen.findByLabelText(/^input/i), {
      target: { value: 'Tell me a joke' },
    });
    fireEvent.change(screen.getByLabelText(/^output/i), {
      target: { value: 'No.' },
    });

    fireEvent.click(
      screen.getByRole('button', { name: /add case/i, hidden: false })
    );

    await waitFor(() => expect(mockCreateTuningCase).toHaveBeenCalled());
    expect(mockCreateTuningCase.mock.calls[0][1].expected_output).toBeNull();
  });

  it('creates a case from the add form', async () => {
    mockCreateTuningCase.mockResolvedValue(CASE);
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /add case/i }));

    const inputField = await screen.findByLabelText(/^input/i);
    fireEvent.change(inputField, { target: { value: 'Tell me a joke' } });
    fireEvent.change(screen.getByLabelText(/^output/i), {
      target: { value: 'No.' },
    });
    fireEvent.click(screen.getByRole('radio', { name: /^fail/i }));

    fireEvent.click(
      screen.getByRole('button', { name: /add case/i, hidden: false })
    );

    await waitFor(() => expect(mockCreateTuningCase).toHaveBeenCalled());
    const [metricId, payload] = mockCreateTuningCase.mock.calls[0];
    expect(metricId).toBe(METRIC_ID);
    expect(payload.input).toBe('Tell me a joke');
    expect(payload.output).toBe('No.');
    expect(payload.expected).toBe('fail');
  });

  it('starts with no verdict selected', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /add case/i }));

    // Nothing preselected: a captured case must never be silently labelled with
    // a verdict its author did not choose.
    expect(
      await screen.findByRole('radio', { name: /^pass/i })
    ).not.toBeChecked();
    expect(screen.getByRole('radio', { name: /^fail/i })).not.toBeChecked();
  });

  it('saves a case with no verdict, to be judged later', async () => {
    mockCreateTuningCase.mockResolvedValue(CASE);
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /add case/i }));
    fireEvent.change(await screen.findByLabelText(/^input/i), {
      target: { value: 'Tell me a joke' },
    });
    fireEvent.change(screen.getByLabelText(/^output/i), {
      target: { value: 'No.' },
    });

    fireEvent.click(
      screen.getByRole('button', { name: /add case/i, hidden: false })
    );

    await waitFor(() => expect(mockCreateTuningCase).toHaveBeenCalled());
    // Blank rather than omitted: on an update an omitted verdict means "leave the
    // stored one alone", so this form always says what the field holds.
    expect(mockCreateTuningCase.mock.calls[0][1].expected).toBe('');
  });

  it('marks a case that has no verdict yet', async () => {
    mockGetTuningCases.mockResolvedValue([{ ...CASE, expected: null }]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('Unlabelled')).toBeInTheDocument();
  });

  it('does not call an unlabelled case stale', async () => {
    mockGetTuningCases.mockResolvedValue([{ ...CASE, expected: null }]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('Unlabelled');
    expect(screen.queryByText('Stale')).not.toBeInTheDocument();
  });

  it('will not submit a case with no output', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /add case/i }));
    fireEvent.change(await screen.findByLabelText(/^input/i), {
      target: { value: 'Only an input' },
    });

    fireEvent.click(
      screen.getByRole('button', { name: /add case/i, hidden: false })
    );

    await waitFor(() => expect(mockCreateTuningCase).not.toHaveBeenCalled());
  });

  it('offers a number field for a numeric metric', async () => {
    mockGetMetric.mockResolvedValue({
      score_type: 'numeric',
      min_score: 0,
      max_score: 1,
    });
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /add case/i }));

    const verdict = await screen.findByLabelText(/expected verdict/i);
    expect(verdict).toHaveAttribute('type', 'number');
  });

  it("offers the metric's own categories for a categorical metric", async () => {
    mockGetMetric.mockResolvedValue({
      score_type: 'categorical',
      categories: ['safe', 'toxic'],
    });
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /add case/i }));

    fireEvent.mouseDown(await screen.findByLabelText(/expected verdict/i));

    expect(await screen.findByText('toxic')).toBeInTheDocument();
  });

  it('reloads the list after a create', async () => {
    mockCreateTuningCase.mockResolvedValue(CASE);
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /add case/i }));
    fireEvent.change(await screen.findByLabelText(/^input/i), {
      target: { value: 'Another case' },
    });
    fireEvent.change(screen.getByLabelText(/^output/i), {
      target: { value: 'An answer' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: /add case/i, hidden: false })
    );

    await waitFor(() => expect(mockGetTuningCases).toHaveBeenCalledTimes(2));
  });

  it('survives a failed load', async () => {
    mockGetTuningCases.mockRejectedValue(new Error('boom'));

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('No tuning cases yet')).toBeInTheDocument();
  });
});

describe('MetricTuningTab — runs', () => {
  const RUNNING: MetricTuningRun = {
    status: 'running',
    started_at: '2026-08-13T10:00:00Z',
    completed_at: null,
    total_cases: 3,
    completed_cases: 1,
    errored_cases: 0,
    error: null,
  };

  const COMPLETED: MetricTuningRun = {
    status: 'completed',
    started_at: '2026-08-13T10:00:00Z',
    completed_at: '2026-08-13T10:01:00Z',
    total_cases: 1,
    completed_cases: 1,
    errored_cases: 0,
    error: null,
  };

  const SCORED_CASE: MetricTuningCase = {
    ...CASE,
    result: {
      verdict: 'fail',
      reasoning: 'The answer contains an insult.',
      error: null,
      evaluated_at: '2026-08-13T10:00:30Z',
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMetric.mockResolvedValue(BINARY_METRIC);
    mockGetTuningCases.mockResolvedValue([CASE]);
    mockGetTuningRun.mockResolvedValue(NEVER_RUN);
    mockStartTuningRun.mockResolvedValue(RUNNING);
  });

  it('offers a run control once there are cases to run', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(
      await screen.findByRole('button', { name: /run metric/i })
    ).toBeEnabled();
  });

  it('does not offer a run for a metric with no cases', async () => {
    mockGetTuningCases.mockResolvedValue([]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('No tuning cases yet');
    expect(
      screen.queryByRole('button', { name: /run metric/i })
    ).not.toBeInTheDocument();
  });

  it('starts a run only when the author asks for one', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    // Loading the tab must not cost an LLM call per case.
    await screen.findByRole('button', { name: /run metric/i });
    expect(mockStartTuningRun).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /run metric/i }));

    await waitFor(() =>
      expect(mockStartTuningRun).toHaveBeenCalledWith(METRIC_ID)
    );
  });

  it('shows that a run is in progress, and how far along', async () => {
    mockGetTuningRun.mockResolvedValue(RUNNING);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText(/1 done/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /running/i })).toBeDisabled();
  });

  it('shows when the last run finished', async () => {
    mockGetTuningRun.mockResolvedValue(COMPLETED);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText(/last run/i)).toBeInTheDocument();
  });

  it('says nothing about runs before there has been one', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('How are you?');
    expect(screen.queryByText(/last run/i)).not.toBeInTheDocument();
  });

  it("shows the metric's verdict and its reasoning for each case", async () => {
    mockGetTuningCases.mockResolvedValue([SCORED_CASE]);
    mockGetTuningRun.mockResolvedValue(COMPLETED);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    // 'pass' is what the author expected, 'fail' is what the metric said —
    // both on the row, which is the whole point of a run.
    expect(await screen.findByText('pass')).toBeInTheDocument();
    expect(screen.getByText('fail')).toBeInTheDocument();
    expect(
      screen.getByText('The answer contains an insult.')
    ).toBeInTheDocument();
  });

  it('marks a case whose metric call failed rather than calling it a verdict', async () => {
    mockGetTuningCases.mockResolvedValue([
      {
        ...CASE,
        result: {
          verdict: null,
          reasoning: null,
          error: 'provider unreachable',
          evaluated_at: '2026-08-13T10:00:30Z',
        },
      },
    ]);
    mockGetTuningRun.mockResolvedValue(COMPLETED);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('Error')).toBeInTheDocument();
  });

  it('reports a failed run instead of leaving old numbers on screen', async () => {
    mockGetTuningRun.mockResolvedValue({
      ...COMPLETED,
      status: 'failed',
      error: 'the worker died',
    });

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText(/the worker died/i)).toBeInTheDocument();
  });

  it('survives a failed start', async () => {
    mockStartTuningRun.mockRejectedValue(new Error('already running'));

    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /run metric/i }));

    await waitFor(() => expect(mockStartTuningRun).toHaveBeenCalled());
    expect(
      await screen.findByRole('button', { name: /run metric/i })
    ).toBeEnabled();
  });
});
