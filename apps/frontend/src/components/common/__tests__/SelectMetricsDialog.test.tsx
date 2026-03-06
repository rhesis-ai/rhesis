import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import SelectMetricsDialog from '../SelectMetricsDialog';
import { MetricsClient } from '@/utils/api-client/metrics-client';

jest.mock('@/utils/api-client/metrics-client');

const SESSION_TOKEN = 'test-token';

// A stable (module-level) reference avoids re-triggering the useCallback/useEffect
// cycle that would happen with a default `[]` created on each render.
const STABLE_EMPTY_IDS: never[] = [];

function makeMetric(overrides: Record<string, unknown> = {}) {
  return {
    id: 'metric-1',
    name: 'Accuracy',
    description: 'Measures accuracy of responses',
    backend_type: { type_value: 'llm_judge' },
    metric_type: null,
    metric_scope: ['Single-Turn'],
    score_type: 'binary',
    ...overrides,
  };
}

function makePaginatedResponse(items: unknown[]) {
  return { data: items, pagination: { totalCount: items.length } };
}

let mockGetMetrics: jest.Mock;

beforeEach(() => {
  mockGetMetrics = jest.fn().mockResolvedValue(makePaginatedResponse([]));
  (MetricsClient as jest.Mock).mockImplementation(() => ({
    getMetrics: mockGetMetrics,
  }));
});

afterEach(() => {
  jest.clearAllMocks();
});

function renderDialog(
  props: Partial<React.ComponentProps<typeof SelectMetricsDialog>> = {}
) {
  const defaults = {
    open: true,
    onClose: jest.fn(),
    onSelect: jest.fn(),
    sessionToken: SESSION_TOKEN,
    excludeMetricIds: STABLE_EMPTY_IDS,
  };
  return render(<SelectMetricsDialog {...defaults} {...props} />);
}

describe('SelectMetricsDialog', () => {
  it('shows a loading indicator while fetching metrics', async () => {
    mockGetMetrics.mockImplementation(() => new Promise(() => {}));
    renderDialog();
    expect(screen.getByText(/loading metrics/i)).toBeInTheDocument();
  });

  it('renders the dialog title', async () => {
    renderDialog();
    await screen.findByRole('dialog');
    expect(screen.getByText('Add Metric')).toBeInTheDocument();
  });

  it('renders a custom title when provided', async () => {
    renderDialog({ title: 'Pick a Metric' });
    await screen.findByRole('dialog');
    expect(screen.getByText('Pick a Metric')).toBeInTheDocument();
  });

  it('shows "No metrics available" when the API returns an empty list', async () => {
    mockGetMetrics.mockResolvedValue(makePaginatedResponse([]));
    renderDialog();
    await screen.findByText(/no metrics available/i);
  });

  it('renders a list of metrics after loading', async () => {
    mockGetMetrics.mockResolvedValue(
      makePaginatedResponse([
        makeMetric({ id: 'm-1', name: 'Coherence' }),
        makeMetric({ id: 'm-2', name: 'Relevance' }),
      ])
    );
    renderDialog();
    await screen.findByText('Coherence');
    expect(screen.getByText('Relevance')).toBeInTheDocument();
  });

  it('excludes already-selected metrics from the list', async () => {
    mockGetMetrics.mockResolvedValue(
      makePaginatedResponse([
        makeMetric({ id: 'excluded-id', name: 'Already Added' }),
        makeMetric({ id: 'available-id', name: 'Available Metric' }),
      ])
    );
    renderDialog({ excludeMetricIds: ['excluded-id' as never] });
    await screen.findByText('Available Metric');
    expect(screen.queryByText('Already Added')).not.toBeInTheDocument();
  });

  it('shows an error message when the fetch fails', async () => {
    mockGetMetrics.mockRejectedValue(
      new Error('API error: 500 - Server error')
    );
    renderDialog();
    await screen.findByText(/API error: 500 - Server error/i);
  });

  it('filters metrics by search query (name match)', async () => {
    const user = userEvent.setup();
    mockGetMetrics.mockResolvedValue(
      makePaginatedResponse([
        makeMetric({ id: 'm-1', name: 'Coherence' }),
        makeMetric({ id: 'm-2', name: 'Relevance' }),
      ])
    );
    renderDialog();
    await screen.findByText('Coherence');

    await user.type(screen.getByPlaceholderText(/search metrics/i), 'coh');

    expect(screen.queryByText('Relevance')).not.toBeInTheDocument();
    expect(screen.getByText('Coherence')).toBeInTheDocument();
  });

  it('filters metrics by search query (description match)', async () => {
    const user = userEvent.setup();
    mockGetMetrics.mockResolvedValue(
      makePaginatedResponse([
        makeMetric({ id: 'm-1', name: 'Alpha', description: 'judges fluency' }),
        makeMetric({ id: 'm-2', name: 'Beta', description: 'checks safety' }),
      ])
    );
    renderDialog();
    await screen.findByText('Alpha');

    await user.type(screen.getByPlaceholderText(/search metrics/i), 'safety');

    expect(screen.queryByText('Alpha')).not.toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });

  it('shows "No metrics match your search" when search yields no results', async () => {
    const user = userEvent.setup();
    mockGetMetrics.mockResolvedValue(
      makePaginatedResponse([makeMetric({ id: 'm-1', name: 'Coherence' })])
    );
    renderDialog();
    await screen.findByText('Coherence');

    await user.type(
      screen.getByPlaceholderText(/search metrics/i),
      'zzznomatch'
    );

    await screen.findByText(/no metrics match your search/i);
  });

  it('calls onSelect with the metric id and closes when a metric is clicked', async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    const onClose = jest.fn();
    mockGetMetrics.mockResolvedValue(
      makePaginatedResponse([
        makeMetric({ id: 'metric-abc', name: 'Precision' }),
      ])
    );
    renderDialog({ onSelect, onClose });
    await screen.findByText('Precision');

    await user.click(screen.getByText('Precision'));

    expect(onSelect).toHaveBeenCalledWith('metric-abc');
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when Cancel is clicked without selecting', async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    const onClose = jest.fn();
    renderDialog({ onSelect, onClose });
    await screen.findByRole('dialog');

    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onClose).toHaveBeenCalled();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('applies scope filter: only shows metrics matching the given scope', async () => {
    mockGetMetrics.mockResolvedValue(
      makePaginatedResponse([
        makeMetric({
          id: 'm-1',
          name: 'Single Turn Metric',
          metric_scope: ['Single-Turn'],
        }),
        makeMetric({
          id: 'm-2',
          name: 'Multi Turn Metric',
          metric_scope: ['Multi-Turn'],
        }),
      ])
    );
    renderDialog({ scopeFilter: 'Single-Turn' as never });
    await screen.findByText('Single Turn Metric');
    expect(screen.queryByText('Multi Turn Metric')).not.toBeInTheDocument();
  });

  it('fetches metrics when the dialog opens (open=true)', async () => {
    mockGetMetrics.mockResolvedValue(makePaginatedResponse([]));
    renderDialog({ open: true });
    await waitFor(() => {
      expect(mockGetMetrics).toHaveBeenCalledTimes(1);
    });
  });

  it('does not fetch metrics when dialog is closed', () => {
    renderDialog({ open: false });
    expect(mockGetMetrics).not.toHaveBeenCalled();
  });
});
