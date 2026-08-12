import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import MetricTuningTab from '../MetricTuningTab';
import type { MetricTuningCase } from '@/utils/api-client/interfaces/metric-tuning';

const mockGetTuningCases = jest.fn();
const mockCreateTuningCase = jest.fn();
const mockUpdateTuningCase = jest.fn();
const mockDeleteTuningCase = jest.fn();
const mockGetMetric = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getMetricTuningClient: () => ({
      getTuningCases: mockGetTuningCases,
      createTuningCase: mockCreateTuningCase,
      updateTuningCase: mockUpdateTuningCase,
      deleteTuningCase: mockDeleteTuningCase,
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
  created_at: '2026-08-06T00:00:00Z',
  updated_at: '2026-08-06T00:00:00Z',
};

const BINARY_METRIC = { score_type: 'binary' as const };

describe('MetricTuningTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetTuningCases.mockResolvedValue([]);
    mockGetMetric.mockResolvedValue(BINARY_METRIC);
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
