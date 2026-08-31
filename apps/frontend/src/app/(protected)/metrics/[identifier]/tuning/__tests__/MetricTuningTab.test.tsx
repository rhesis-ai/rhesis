import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import MetricTuningTab from '../MetricTuningTab';
import type {
  ImprovedMetricFields,
  MetricTuningAgreement,
  MetricTuningCase,
  MetricTuningImprovement,
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
const mockImproveFromReviews = jest.fn();
const mockGetMetric = jest.fn();
const mockUpdateMetric = jest.fn();

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
      improveFromReviews: mockImproveFromReviews,
    }),
    getMetricsClient: () => ({
      getMetric: mockGetMetric,
      updateMetric: mockUpdateMetric,
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

/** Nothing judged: no ratio at all, which is not the same as a ratio of 1. */
const NO_AGREEMENT: MetricTuningAgreement = {
  ratio: null,
  judged: 0,
  accepted: 0,
  rejected: 0,
  unreviewed: 0,
  errored: 0,
};

const agreement = (
  fields: Partial<MetricTuningAgreement>
): MetricTuningAgreement => ({ ...NO_AGREEMENT, ...fields });

const NEVER_RUN: MetricTuningRun = {
  status: 'never_run',
  started_at: null,
  completed_at: null,
  total_cases: 0,
  completed_cases: 0,
  errored_cases: 0,
  error: null,
  agreement: NO_AGREEMENT,
  predates_metric: false,
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
    agreement: NO_AGREEMENT,
    predates_metric: false,
  };

  const COMPLETED: MetricTuningRun = {
    status: 'completed',
    started_at: '2026-08-13T10:00:00Z',
    completed_at: '2026-08-13T10:01:00Z',
    total_cases: 1,
    completed_cases: 1,
    errored_cases: 0,
    error: null,
    agreement: NO_AGREEMENT,
    predates_metric: false,
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
    // The counts belong to the run that failed, and reading them as the result
    // of the edit that was just made is the whole failure mode.
    expect(screen.queryByText(/over 1 case/i)).not.toBeInTheDocument();
  });

  it('leaves the run control usable after a run failed', async () => {
    // A failed run that disabled the button would be a dead end: the button is
    // disabled on `running`, which is what an abandoned run used to stay.
    mockGetTuningRun.mockResolvedValue({
      ...COMPLETED,
      status: 'failed',
      error: 'the run stopped responding',
    });

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(
      await screen.findByRole('button', { name: /run metric/i })
    ).toBeEnabled();
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
   *
   * Waits for the query to succeed: the grid stays visibility-hidden (and so
   * absent from the accessible tree `getAllByRole` reads) for two animation
   * frames after mount, to avoid a visible column-width snap.
   */
  const headerLabels = () =>
    waitFor(() =>
      screen
        .getAllByRole('columnheader')
        .map(header => header.textContent ?? '')
    );

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMetric.mockResolvedValue(BINARY_METRIC);
    mockGetTuningRun.mockResolvedValue(NEVER_RUN);
    mockGetTuningCases.mockResolvedValue([JUDGEABLE_CASE]);
  });

  it('separates the case, the run and the review into column groups', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('How are you?');
    const labels = await headerLabels();
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
    const labels = await headerLabels();
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
    expect(await headerLabels()).not.toContain('Reference answer');
  });

  it('leaves out the run and review groups before anything has been run', async () => {
    mockGetTuningCases.mockResolvedValue([CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('How are you?');
    const labels = await headerLabels();
    expect(labels).not.toContain('Metric output');
    expect(labels).not.toContain('Review');
    expect(labels).not.toContain('Metric verdict');
  });
});

const acceptMark = () =>
  screen.getByRole('button', { name: /accept this verdict/i });

const rejectMark = () =>
  screen.getByRole('button', { name: /reject this verdict/i });

/** The pressed mark is the recorded judgement — there is no chip to read. */
const findAccepted = async () =>
  await waitFor(() =>
    expect(acceptMark()).toHaveAttribute('aria-pressed', 'true')
  );

const findRejected = async () =>
  await waitFor(() =>
    expect(rejectMark()).toHaveAttribute('aria-pressed', 'true')
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

  it('leaves both marks unpressed while nobody has judged the verdict', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    await waitFor(() => expect(acceptMark()).toBeInTheDocument());
    expect(acceptMark()).toHaveAttribute('aria-pressed', 'false');
    expect(rejectMark()).toHaveAttribute('aria-pressed', 'false');
    // Nothing was taken away, so there is no warning to explain.
    expect(
      screen.queryByLabelText(/review invalidated/i)
    ).not.toBeInTheDocument();
  });

  it('shows an accepted case on the mark that recorded it', async () => {
    mockGetTuningCases.mockResolvedValue([ACCEPTED_CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await findAccepted();
    expect(rejectMark()).toHaveAttribute('aria-pressed', 'false');
  });

  it("shows a rejected case on its mark, with the reviewer's comment", async () => {
    mockGetTuningCases.mockResolvedValue([REJECTED_CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await findRejected();
    // The comment rides on the mark's tooltip, which MUI only mounts once the
    // mark is hovered or focused.
    fireEvent.mouseOver(rejectMark());
    expect(
      await screen.findByText('This answer dodges the question.')
    ).toBeInTheDocument();
  });

  it('lets a judged case be judged again from the same cell', async () => {
    mockGetTuningCases.mockResolvedValue([REJECTED_CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await findRejected();
    expect(acceptMark()).toBeEnabled();
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
    await waitFor(() => expect(acceptMark()).toBeInTheDocument());
    expect(acceptMark()).toHaveAttribute('aria-pressed', 'false');
    expect(rejectMark()).toHaveAttribute('aria-pressed', 'false');
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

    fireEvent.change(screen.getByRole('textbox', { name: /comment/i }), {
      target: { value: '   ' },
    });
    expect(save).toBeDisabled();

    fireEvent.change(screen.getByRole('textbox', { name: /comment/i }), {
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
    fireEvent.change(await screen.findByRole('textbox', { name: /comment/i }), {
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

describe('MetricTuningTab — agreement', () => {
  /** A finished run whose agreement is whatever the test needs it to be. */
  const runWith = (
    fields: Partial<MetricTuningAgreement>
  ): MetricTuningRun => ({
    ...NEVER_RUN,
    status: 'completed',
    started_at: '2026-08-13T10:00:00Z',
    completed_at: '2026-08-13T10:01:00Z',
    total_cases: 3,
    completed_cases: 3,
    agreement: agreement(fields),
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMetric.mockResolvedValue(BINARY_METRIC);
    mockGetTuningCases.mockResolvedValue([JUDGEABLE_CASE]);
    mockGetTuningRun.mockResolvedValue(NEVER_RUN);
  });

  it('shows the number and the count it was computed over', async () => {
    mockGetTuningRun.mockResolvedValue(
      runWith({ ratio: 0.6667, judged: 3, accepted: 2, rejected: 1 })
    );

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('67%')).toBeInTheDocument();
    // The denominator travels with it: three out of three must not read like a
    // solved problem.
    expect(screen.getByText(/2 of 3 cases accepted/i)).toBeInTheDocument();
    expect(screen.getByText('Rejected')).toBeInTheDocument();
  });

  it('reports no agreement rather than full agreement when nothing is judged', async () => {
    mockGetTuningRun.mockResolvedValue(runWith({ unreviewed: 3 }));

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText(/nothing judged yet/i)).toBeInTheDocument();
    expect(screen.queryByText('100%')).not.toBeInTheDocument();
    expect(
      screen.getByTitle(/nothing has been judged yet/i)
    ).toBeInTheDocument();
  });

  it('counts unreviewed cases out of the ratio and reports them beside it', async () => {
    mockGetTuningRun.mockResolvedValue(
      runWith({ ratio: 1, judged: 1, accepted: 1, unreviewed: 2 })
    );

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('100%')).toBeInTheDocument();
    expect(screen.getByText(/1 of 1 case accepted/i)).toBeInTheDocument();
    expect(screen.getByText(/2 unreviewed/i)).toBeInTheDocument();
  });

  it('reports errored cases apart, so a flaky provider is visibly one', async () => {
    mockGetTuningRun.mockResolvedValue(
      runWith({ ratio: 1, judged: 1, accepted: 1, errored: 2 })
    );

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText('100%')).toBeInTheDocument();
    expect(
      screen.getByText(/2 the metric could not be reached on/i)
    ).toBeInTheDocument();
  });

  it('reports no agreement before the metric has been run, rather than a number', async () => {
    mockGetTuningCases.mockResolvedValue([CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText('How are you?');
    expect(screen.getByText('Agreement')).toBeInTheDocument();
    expect(screen.getByText(/nothing judged yet/i)).toBeInTheDocument();
  });

  it('re-reads the agreement after a review, since judging a case moves it', async () => {
    mockGetTuningRun
      .mockResolvedValueOnce(runWith({ unreviewed: 1 }))
      .mockResolvedValue(runWith({ ratio: 1, judged: 1, accepted: 1 }));
    mockReviewTuningCase.mockResolvedValue({
      ...JUDGEABLE_CASE,
      outcome: 'accepted',
      unreviewed_reason: null,
      review: {
        decision: 'accepted',
        comment: null,
        verdict: 'pass',
        reviewed_at: '2026-08-14T09:00:00Z',
      },
    });

    render(<MetricTuningTab metricId={METRIC_ID} />);
    await screen.findByText(/nothing judged yet/i);

    fireEvent.click(
      screen.getByRole('button', { name: /accept this verdict/i })
    );

    expect(await screen.findByText('100%')).toBeInTheDocument();
  });

  it('keeps the tiles on screen while a run is going', async () => {
    // Pressing Run must not pull the numbers out from under the reviewer: they
    // are what the press is about. The run clears the verdicts as it goes, so
    // the tiles empty out on their own; the progress line says why.
    mockGetTuningRun.mockResolvedValue({
      ...runWith({ unreviewed: 3 }),
      status: 'running',
      completed_at: null,
      completed_cases: 1,
    });

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(await screen.findByText(/1 done/i)).toBeInTheDocument();
    expect(screen.getByText('Agreement')).toBeInTheDocument();
    expect(screen.getByText(/nothing judged yet/i)).toBeInTheDocument();
  });
});

describe('MetricTuningTab — improving from reviews', () => {
  /** A metric with the fields the dialog shows on its "current" side. */
  const FULL_METRIC = {
    ...BINARY_METRIC,
    name: 'Toxicity',
    description: 'Whether the answer is toxic.',
    evaluation_prompt: 'Score how toxic the answer is.',
    evaluation_steps: 'Step 1:\nRead the answer.',
    reasoning: 'Say which phrase decided it.',
    explanation: 'A fail means the answer is toxic.',
    min_score: null,
    max_score: null,
    threshold: null,
    threshold_operator: null,
    categories: null,
    passing_categories: null,
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

  const PROPOSED: ImprovedMetricFields = {
    name: 'Toxicity',
    description: 'Whether the answer is toxic.',
    evaluation_prompt: 'Fail any answer that dodges the question.',
    evaluation_steps: 'Step 1:\nRead the answer.',
    reasoning: 'Quote the phrase that dodges.',
    explanation: 'A fail means the answer is toxic.',
    score_type: 'binary',
    min_score: null,
    max_score: null,
    threshold: null,
    threshold_operator: null,
    categories: null,
    passing_categories: null,
  };

  const IMPROVEMENT: MetricTuningImprovement = {
    improvement: PROPOSED,
    changed: ['evaluation_prompt', 'reasoning'],
    rejections_used: 3,
  };

  const RUNNING: MetricTuningRun = {
    ...NEVER_RUN,
    status: 'running',
    started_at: '2026-08-13T10:00:00Z',
    total_cases: 1,
  };

  const improveButton = () => screen.getByRole('button', { name: /improve/i });

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMetric.mockResolvedValue(FULL_METRIC);
    mockGetTuningRun.mockResolvedValue(NEVER_RUN);
    mockGetTuningCases.mockResolvedValue([REJECTED_CASE]);
    mockImproveFromReviews.mockResolvedValue(IMPROVEMENT);
    mockUpdateMetric.mockResolvedValue(FULL_METRIC);
  });

  it('offers Improve once a rejection stands', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    await waitFor(() => expect(improveButton()).toBeEnabled());
  });

  it('refuses to improve with nothing to read, and says why', async () => {
    mockGetTuningCases.mockResolvedValue([JUDGEABLE_CASE]);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await waitFor(() => expect(improveButton()).toBeDisabled());
    expect(
      screen.getByLabelText(/reject a case with a comment first/i)
    ).toBeInTheDocument();
  });

  it('does not improve while a run is in flight, and says that is why', async () => {
    // The verdicts are about to be replaced, so a rewrite of them is premature.
    mockGetTuningRun.mockResolvedValue(RUNNING);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await waitFor(() => expect(improveButton()).toBeDisabled());
    expect(
      screen.getByLabelText(/wait for the run to finish/i)
    ).toBeInTheDocument();
  });

  it('says a rewrite is being written, and how much it is reading', async () => {
    // The button label alone is too quiet for a call that runs most of a minute.
    let arrive: (value: MetricTuningImprovement) => void = () => {};
    mockImproveFromReviews.mockReturnValue(
      new Promise<MetricTuningImprovement>(resolve => {
        arrive = resolve;
      })
    );
    mockGetTuningCases.mockResolvedValue([
      REJECTED_CASE,
      { ...REJECTED_CASE, id: 'other-id' as MetricTuningCase['id'] },
    ]);

    render(<MetricTuningTab metricId={METRIC_ID} />);
    await waitFor(() => expect(improveButton()).toBeEnabled());
    fireEvent.click(improveButton());

    expect(
      await screen.findByText(/rewriting this metric from 2 rejections/i)
    ).toBeInTheDocument();

    arrive(IMPROVEMENT);
    await screen.findByRole('dialog');
    // The dialog says the same thing now, so the line has nothing left to add.
    await waitFor(() =>
      expect(
        screen.queryByText(/rewriting this metric from/i)
      ).not.toBeInTheDocument()
    );
  });

  it('says nothing about rewriting when no call is out', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);

    await waitFor(() => expect(improveButton()).toBeEnabled());
    expect(
      screen.queryByText(/rewriting this metric from/i)
    ).not.toBeInTheDocument();
  });

  it('says it is improving, and opens nothing until the rewrite arrives', async () => {
    let arrive: (value: MetricTuningImprovement) => void = () => {};
    mockImproveFromReviews.mockReturnValue(
      new Promise<MetricTuningImprovement>(resolve => {
        arrive = resolve;
      })
    );

    render(<MetricTuningTab metricId={METRIC_ID} />);
    await waitFor(() => expect(improveButton()).toBeEnabled());
    fireEvent.click(improveButton());

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /improving/i })).toBeDisabled()
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    arrive(IMPROVEMENT);
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });

  it('says how many rejections the rewrite came from', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);
    await waitFor(() => expect(improveButton()).toBeEnabled());

    fireEvent.click(improveButton());

    expect(
      await screen.findByText(/rewritten from 3 rejections/i)
    ).toBeInTheDocument();
  });

  it('shows the current field beside the proposed one', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);
    await waitFor(() => expect(improveButton()).toBeEnabled());

    fireEvent.click(improveButton());

    await screen.findByRole('dialog');
    expect(
      screen.getByText('Score how toxic the answer is.')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Fail any answer that dodges the question.')
    ).toBeInTheDocument();
  });

  it('shows only the changed fields, and names the rest as unchanged', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);
    await waitFor(() => expect(improveButton()).toBeEnabled());

    fireEvent.click(improveButton());

    const dialog = await screen.findByRole('dialog');
    // The field the whole feature exists to rewrite is the one read first.
    const headings = Array.from(
      dialog.querySelectorAll('.MuiTypography-subtitle2')
    ).map(node => node.textContent);
    expect(headings).toEqual(['Evaluation prompt', 'Reasoning']);
    // Unchanged, so it is named rather than shown as a diff.
    expect(screen.queryByText('Description')).not.toBeInTheDocument();
    expect(screen.getByText(/unchanged:/i)).toHaveTextContent('description');
  });

  it('applies every field it showed, not only the changed ones', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);
    await waitFor(() => expect(improveButton()).toBeEnabled());
    fireEvent.click(improveButton());
    await screen.findByRole('dialog');

    fireEvent.click(screen.getByRole('button', { name: /^apply$/i }));

    // All-or-nothing: a half-applied metric has bands and steps that disagree.
    // The fields this metric does not have are left out rather than sent as
    // nulls — the API drops a null on update, so sending one writes nothing and
    // only makes the request disagree with what the reviewer approved.
    await waitFor(() =>
      expect(mockUpdateMetric).toHaveBeenCalledWith(METRIC_ID, {
        name: PROPOSED.name,
        description: PROPOSED.description,
        evaluation_prompt: PROPOSED.evaluation_prompt,
        evaluation_steps: PROPOSED.evaluation_steps,
        reasoning: PROPOSED.reasoning,
        explanation: PROPOSED.explanation,
        score_type: PROPOSED.score_type,
      })
    );
  });

  it('sends the score bands of a metric that has them', async () => {
    const scored: ImprovedMetricFields = {
      ...PROPOSED,
      score_type: 'numeric',
      min_score: 0,
      max_score: 1,
      threshold: 0.9,
      threshold_operator: '>=',
    };
    mockImproveFromReviews.mockResolvedValue({
      ...IMPROVEMENT,
      improvement: scored,
      changed: ['evaluation_prompt', 'threshold'],
    });

    render(<MetricTuningTab metricId={METRIC_ID} />);
    await waitFor(() => expect(improveButton()).toBeEnabled());
    fireEvent.click(improveButton());
    await screen.findByRole('dialog');

    fireEvent.click(screen.getByRole('button', { name: /^apply$/i }));

    await waitFor(() =>
      expect(mockUpdateMetric).toHaveBeenCalledWith(
        METRIC_ID,
        expect.objectContaining({ threshold: 0.9, threshold_operator: '>=' })
      )
    );
  });

  it('tells the page the metric changed, so the other tabs re-read it', async () => {
    // The detail view fetches the metric once per id. Without this it goes on
    // showing the evaluation prompt from before the apply until a page reload.
    const onMetricChanged = jest.fn();
    render(
      <MetricTuningTab metricId={METRIC_ID} onMetricChanged={onMetricChanged} />
    );
    await waitFor(() => expect(improveButton()).toBeEnabled());
    fireEvent.click(improveButton());
    await screen.findByRole('dialog');

    fireEvent.click(screen.getByRole('button', { name: /^apply$/i }));

    await waitFor(() => expect(onMetricChanged).toHaveBeenCalledTimes(1));
  });

  it('does not say the metric changed when the apply failed', async () => {
    const onMetricChanged = jest.fn();
    mockUpdateMetric.mockRejectedValue(new Error('conflict'));
    render(
      <MetricTuningTab metricId={METRIC_ID} onMetricChanged={onMetricChanged} />
    );
    await waitFor(() => expect(improveButton()).toBeEnabled());
    fireEvent.click(improveButton());
    await screen.findByRole('dialog');

    fireEvent.click(screen.getByRole('button', { name: /^apply$/i }));

    await screen.findByText('conflict');
    expect(onMetricChanged).not.toHaveBeenCalled();
  });

  it('re-reads the tab after applying, so the run reads as out of date', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);
    await waitFor(() => expect(improveButton()).toBeEnabled());
    fireEvent.click(improveButton());
    await screen.findByRole('dialog');
    const readsBefore = mockGetTuningRun.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: /^apply$/i }));

    await waitFor(() =>
      expect(mockGetTuningRun.mock.calls.length).toBeGreaterThan(readsBefore)
    );
  });

  const proposedBox = (label: RegExp) =>
    screen.getByRole('textbox', { name: label });

  const openDialog = async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);
    await waitFor(() => expect(improveButton()).toBeEnabled());
    fireEvent.click(improveButton());
    await screen.findByRole('dialog');
  };

  it('applies the reviewer edit rather than what the model proposed', async () => {
    // The rewrite is a draft: someone who can see what is wrong with one clause
    // should be able to fix that clause instead of discarding the whole thing.
    await openDialog();

    fireEvent.change(proposedBox(/evaluation prompt, proposed/i), {
      target: { value: 'Fail any answer that dodges, unless it says why.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^apply$/i }));

    await waitFor(() =>
      expect(mockUpdateMetric).toHaveBeenCalledWith(
        METRIC_ID,
        expect.objectContaining({
          evaluation_prompt: 'Fail any answer that dodges, unless it says why.',
        })
      )
    );
  });

  it('will not apply a field left empty', async () => {
    // An update drops a null instead of writing it, so an empty box would apply
    // successfully and change nothing.
    await openDialog();

    fireEvent.change(proposedBox(/evaluation prompt, proposed/i), {
      target: { value: '   ' },
    });

    expect(screen.getByRole('button', { name: /^apply$/i })).toBeDisabled();
    expect(
      screen.getByText(/an empty field cannot be saved/i)
    ).toBeInTheDocument();
    expect(mockUpdateMetric).not.toHaveBeenCalled();
  });

  it('puts the proposal back when the edits are undone', async () => {
    await openDialog();
    fireEvent.change(proposedBox(/evaluation prompt, proposed/i), {
      target: { value: 'Something I typed by mistake.' },
    });

    fireEvent.click(screen.getByRole('button', { name: /undo my edits/i }));

    expect(proposedBox(/evaluation prompt, proposed/i)).toHaveValue(
      PROPOSED.evaluation_prompt
    );
  });

  it('offers nothing to undo until something is edited', async () => {
    await openDialog();

    expect(
      screen.queryByRole('button', { name: /undo my edits/i })
    ).not.toBeInTheDocument();
  });

  it('applies an edited threshold as a number, not as its text', async () => {
    mockImproveFromReviews.mockResolvedValue({
      ...IMPROVEMENT,
      improvement: {
        ...PROPOSED,
        score_type: 'numeric',
        min_score: 0,
        max_score: 1,
        threshold: 0.9,
        threshold_operator: '>=',
      },
      changed: ['threshold'],
    });
    await openDialog();

    fireEvent.change(
      screen.getByRole('spinbutton', { name: /threshold, proposed/i }),
      {
        target: { value: '0.75' },
      }
    );
    fireEvent.click(screen.getByRole('button', { name: /^apply$/i }));

    await waitFor(() =>
      expect(mockUpdateMetric).toHaveBeenCalledWith(
        METRIC_ID,
        expect.objectContaining({ threshold: 0.75 })
      )
    );
  });

  it('writes nothing when the dialog is closed', async () => {
    render(<MetricTuningTab metricId={METRIC_ID} />);
    await waitFor(() => expect(improveButton()).toBeEnabled());
    fireEvent.click(improveButton());
    await screen.findByRole('dialog');

    fireEvent.click(screen.getByRole('button', { name: /close/i }));

    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    );
    expect(mockUpdateMetric).not.toHaveBeenCalled();
  });

  it('keeps the proposal on screen when applying fails', async () => {
    mockUpdateMetric.mockRejectedValue(new Error('conflict'));

    render(<MetricTuningTab metricId={METRIC_ID} />);
    await waitFor(() => expect(improveButton()).toBeEnabled());
    fireEvent.click(improveButton());
    await screen.findByRole('dialog');

    fireEvent.click(screen.getByRole('button', { name: /^apply$/i }));

    // Asking again returns a different rewrite, so losing this one is not free.
    expect(await screen.findByText('conflict')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});

describe('MetricTuningTab — a run that predates its metric', () => {
  const STALE_RUN: MetricTuningRun = {
    ...NEVER_RUN,
    status: 'completed',
    started_at: '2026-08-13T10:00:00Z',
    completed_at: '2026-08-13T10:01:00Z',
    total_cases: 1,
    completed_cases: 1,
    predates_metric: true,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMetric.mockResolvedValue(BINARY_METRIC);
    mockGetTuningCases.mockResolvedValue([JUDGEABLE_CASE]);
  });

  it('says the numbers belong to the earlier metric, and points at Run metric', async () => {
    mockGetTuningRun.mockResolvedValue(STALE_RUN);

    render(<MetricTuningTab metricId={METRIC_ID} />);

    expect(
      await screen.findByText(/belong to the earlier version/i)
    ).toHaveTextContent(/press run metric/i);
  });

  it('says nothing of the sort about a run of the current metric', async () => {
    mockGetTuningRun.mockResolvedValue({
      ...STALE_RUN,
      predates_metric: false,
    });

    render(<MetricTuningTab metricId={METRIC_ID} />);

    await screen.findByText(/last run/i);
    expect(
      screen.queryByText(/belong to the earlier version/i)
    ).not.toBeInTheDocument();
  });
});
