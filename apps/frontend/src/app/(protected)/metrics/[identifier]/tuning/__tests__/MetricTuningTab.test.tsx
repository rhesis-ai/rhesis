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
const mockReviewTuningCase = jest.fn();
const mockAcceptRemainingTuningCases = jest.fn();
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
      reviewTuningCase: mockReviewTuningCase,
      acceptRemainingTuningCases: mockAcceptRemainingTuningCases,
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
  reference_answer: null,
  result: null,
  outcome: 'unreviewed',
  review: null,
  unreviewed_reason: 'never_judged',
  created_at: '2026-08-06T00:00:00Z',
  updated_at: '2026-08-06T00:00:00Z',
};

/** A case the metric has been run over, so there is a verdict to judge. */
const JUDGEABLE_CASE: MetricTuningCase = {
  ...CASE,
  result: {
    verdict: 'pass',
    reasoning: 'The answer is polite.',
    error: null,
    evaluated_at: '2026-08-13T10:00:30Z',
  },
};

const BINARY_METRIC = {
  score_type: 'binary' as const,
  ground_truth_required: false,
};

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
  });

  it('marks the tab as beta', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('beta')).toBeInTheDocument();
  });

  it('creates a case from the add form', async () => {
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
    const [metricId, payload] = mockCreateTuningCase.mock.calls[0];
    expect(metricId).toBe(METRIC_ID);
    expect(payload).toEqual({
      input: 'Tell me a joke',
      output: 'No.',
      // Blank rather than absent: the form submits every field, and on an update
      // an omitted reference answer means "leave the stored one alone".
      reference_answer: '',
    });
  });

  it('asks for a reference answer only when the metric needs one', async () => {
    mockGetMetric.mockResolvedValue({
      ...BINARY_METRIC,
      ground_truth_required: true,
    });
    mockCreateTuningCase.mockResolvedValue(CASE);
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /add case/i }));
    fireEvent.change(await screen.findByLabelText(/^input/i), {
      target: { value: 'Tell me a joke' },
    });
    fireEvent.change(screen.getByLabelText(/^output/i), {
      target: { value: 'No.' },
    });
    fireEvent.change(screen.getByLabelText(/reference answer/i), {
      target: { value: 'Here is a joke.' },
    });

    fireEvent.click(
      screen.getByRole('button', { name: /add case/i, hidden: false })
    );

    await waitFor(() => expect(mockCreateTuningCase).toHaveBeenCalled());
    expect(mockCreateTuningCase.mock.calls[0][1].reference_answer).toBe(
      'Here is a joke.'
    );
  });

  it('does not ask for a reference answer a metric never uses', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(await screen.findByRole('button', { name: /add case/i }));

    await screen.findByLabelText(/^input/i);
    expect(
      screen.queryByLabelText(/reference answer/i)
    ).not.toBeInTheDocument();
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

    expect(await screen.findByText('fail')).toBeInTheDocument();
    expect(
      screen.getByText('The answer contains an insult.')
    ).toBeInTheDocument();
  });

  it('marks a case whose metric call failed rather than calling it a verdict', async () => {
    mockGetTuningCases.mockResolvedValue([
      {
        ...CASE,
        outcome: 'errored',
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

describe('MetricTuningTab — the grid', () => {
  /**
   * Header text, groups included. Read off the grid rather than the whole page:
   * the add-case drawer stays mounted while closed, so its own Input and Output
   * fields would otherwise count as matches.
   */
  const headerLabels = () =>
    screen.getAllByRole('columnheader').map(header => header.textContent ?? '');

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMetric.mockResolvedValue(BINARY_METRIC);
    mockGetTuningRun.mockResolvedValue(NEVER_RUN);
    mockGetTuningCases.mockResolvedValue([JUDGEABLE_CASE]);
  });

  it('separates the case, the run and the review into column groups', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('How are you?');
    const labels = headerLabels();
    expect(labels).toContain('Case');
    expect(labels).toContain('Metric output');
    // Review stands outside the group bands, so its name appears exactly once.
    expect(labels.filter(label => label === 'Review')).toHaveLength(1);
  });

  it('labels the case columns without reusing a noun from the run', async () => {
    mockGetTuningCases.mockResolvedValue([
      { ...JUDGEABLE_CASE, reference_answer: 'A polite reply.' },
    ]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('How are you?');
    const labels = headerLabels();
    expect(labels).toContain('Input');
    expect(labels).toContain('Output');
    expect(labels).toContain('Reference answer');
    expect(labels).toContain('Metric verdict');
    expect(labels).toContain('Reasoning');
    expect(labels.join(' ')).not.toMatch(/expected/i);
  });

  it('leaves out a column no case fills', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('How are you?');
    expect(headerLabels()).not.toContain('Reference answer');
  });

  it('leaves out the run and review groups before anything has been run', async () => {
    mockGetTuningCases.mockResolvedValue([CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('How are you?');
    const labels = headerLabels();
    expect(labels).not.toContain('Metric output');
    expect(labels).not.toContain('Review');
    expect(labels).not.toContain('Metric verdict');
  });
});

const acceptThumb = () =>
  screen.getByRole('button', { name: /accept this verdict/i });

const rejectThumb = () =>
  screen.getByRole('button', { name: /reject this verdict/i });

/** The pressed thumb is the recorded judgement — there is no chip to read. */
const findAccepted = async () =>
  await waitFor(() =>
    expect(acceptThumb()).toHaveAttribute('aria-pressed', 'true')
  );

const findRejected = async () =>
  await waitFor(() =>
    expect(rejectThumb()).toHaveAttribute('aria-pressed', 'true')
  );

describe('MetricTuningTab — reviewing', () => {
  const ACCEPTED_CASE: MetricTuningCase = {
    ...JUDGEABLE_CASE,
    outcome: 'accepted',
    unreviewed_reason: null,
    review: {
      decision: 'accepted',
      comment: null,
      verdict: 'pass',
      reviewed_at: '2026-08-14T09:00:00Z',
    },
  };

  const REJECTED_CASE: MetricTuningCase = {
    ...JUDGEABLE_CASE,
    outcome: 'rejected',
    unreviewed_reason: null,
    review: {
      decision: 'rejected',
      comment: 'This answer dodges the question.',
      verdict: 'pass',
      reviewed_at: '2026-08-14T09:00:00Z',
    },
  };

  const ERRORED_CASE: MetricTuningCase = {
    ...CASE,
    outcome: 'errored',
    result: {
      verdict: null,
      reasoning: null,
      error: 'provider unreachable',
      evaluated_at: '2026-08-13T10:00:30Z',
    },
  };

  const INVALIDATED_CASE: MetricTuningCase = {
    ...JUDGEABLE_CASE,
    outcome: 'unreviewed',
    unreviewed_reason: 'invalidated',
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMetric.mockResolvedValue(BINARY_METRIC);
    mockGetTuningRun.mockResolvedValue(NEVER_RUN);
    mockGetTuningCases.mockResolvedValue([JUDGEABLE_CASE]);
  });

  it('leaves both thumbs unpressed while nobody has judged the verdict', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    await waitFor(() => expect(acceptThumb()).toBeInTheDocument());
    expect(acceptThumb()).toHaveAttribute('aria-pressed', 'false');
    expect(rejectThumb()).toHaveAttribute('aria-pressed', 'false');
    // Nothing was taken away, so there is no warning to explain.
    expect(
      screen.queryByLabelText(/review invalidated/i)
    ).not.toBeInTheDocument();
  });

  it('shows an accepted case on the thumb that recorded it', async () => {
    mockGetTuningCases.mockResolvedValue([ACCEPTED_CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await findAccepted();
    expect(rejectThumb()).toHaveAttribute('aria-pressed', 'false');
  });

  it("shows a rejected case on its thumb, with the reviewer's comment", async () => {
    mockGetTuningCases.mockResolvedValue([REJECTED_CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await findRejected();
    // The comment rides on the thumb's tooltip, which MUI only mounts once the
    // thumb is hovered or focused.
    fireEvent.mouseOver(rejectThumb());
    expect(
      await screen.findByText('This answer dodges the question.')
    ).toBeInTheDocument();
  });

  it('lets a judged case be judged again from the same cell', async () => {
    mockGetTuningCases.mockResolvedValue([REJECTED_CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await findRejected();
    expect(acceptThumb()).toBeEnabled();
  });

  it('offers no review buttons for a case whose metric call failed', async () => {
    mockGetTuningCases.mockResolvedValue([ERRORED_CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('Error')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /accept this verdict/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /reject this verdict/i })
    ).not.toBeInTheDocument();
  });

  it('marks a review a material change took away, and says why', async () => {
    mockGetTuningCases.mockResolvedValue([INVALIDATED_CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(
      await screen.findByLabelText(/review invalidated/i)
    ).toBeInTheDocument();
    expect(acceptThumb()).toHaveAttribute('aria-pressed', 'false');
    expect(rejectThumb()).toHaveAttribute('aria-pressed', 'false');
  });

  it('accepts a case in one click', async () => {
    mockReviewTuningCase.mockResolvedValue(ACCEPTED_CASE);
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(
      await screen.findByRole('button', { name: /accept this verdict/i })
    );

    await waitFor(() =>
      expect(mockReviewTuningCase).toHaveBeenCalledWith(
        METRIC_ID,
        JUDGEABLE_CASE.id,
        { decision: 'accepted' }
      )
    );
    await findAccepted();
  });

  it('will not save a rejection until there is a comment', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(
      await screen.findByRole('button', { name: /reject this verdict/i })
    );

    const save = await screen.findByRole('button', { name: 'Save' });
    expect(save).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/comment/i), {
      target: { value: '   ' },
    });
    expect(save).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/comment/i), {
      target: { value: 'Far too lenient.' },
    });
    expect(save).toBeEnabled();
  });

  it('rejects a case with the comment the reviewer wrote', async () => {
    mockReviewTuningCase.mockResolvedValue({
      ...REJECTED_CASE,
      review: {
        decision: 'rejected',
        comment: 'Far too lenient.',
        verdict: 'pass',
        reviewed_at: '2026-08-14T09:00:00Z',
      },
    });
    render(<MetricTuningTab metricId={METRIC_ID} />);

    fireEvent.click(
      await screen.findByRole('button', { name: /reject this verdict/i })
    );
    fireEvent.change(await screen.findByLabelText(/comment/i), {
      target: { value: 'Far too lenient.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() =>
      expect(mockReviewTuningCase).toHaveBeenCalledWith(
        METRIC_ID,
        JUDGEABLE_CASE.id,
        { decision: 'rejected', comment: 'Far too lenient.' }
      )
    );
    await findRejected();
  });

  it('accepts every case still unreviewed in one action', async () => {
    mockAcceptRemainingTuningCases.mockResolvedValue([ACCEPTED_CASE]);
    render(<MetricTuningTab metricId={METRIC_ID} />);

    const acceptRest = await screen.findByRole('button', {
      name: /accept the rest/i,
    });
    // The button exists before the cases land, disabled until one is unreviewed.
    await waitFor(() => expect(acceptRest).toBeEnabled());
    fireEvent.click(acceptRest);

    await waitFor(() =>
      expect(mockAcceptRemainingTuningCases).toHaveBeenCalledWith(METRIC_ID)
    );
    await findAccepted();
  });

  it('has nothing left to accept once every case is judged', async () => {
    mockGetTuningCases.mockResolvedValue([ACCEPTED_CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await findAccepted();
    expect(
      screen.getByRole('button', { name: /accept the rest/i })
    ).toBeDisabled();
  });

  it('has nothing to accept before the metric has been run', async () => {
    mockGetTuningCases.mockResolvedValue([CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('How are you?');
    expect(
      screen.getByRole('button', { name: /accept the rest/i })
    ).toBeDisabled();
  });
});
