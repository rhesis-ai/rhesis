import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import TargetFilterChip from '../TargetFilterChip';

jest.mock('@/hooks/useIsAuthenticated', () => ({
  useIsAuthenticated: () => true,
}));

jest.mock('@/hooks/useLookups', () => ({
  useMetricTargets: () => ({
    data: [
      { on: 'turn', label: 'Each turn', description: '', per_span: false },
      {
        on: 'tool_call',
        label: 'Each tool call',
        description: '',
        per_span: true,
        span_kind: 'tool.invoke',
      },
    ],
  }),
}));

const mockGetMetric = jest.fn();
jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getMetricsClient: () => ({ getMetric: mockGetMetric }),
  })),
}));

beforeEach(() => mockGetMetric.mockReset());

describe('TargetFilterChip', () => {
  it('names the target and the metric it came from', async () => {
    mockGetMetric.mockResolvedValue({
      id: 'metric-1',
      name: 'Correct refund arguments',
      config: { target: { on: 'tool_call', name: 'issue_refund' } },
    });

    render(<TargetFilterChip metricId="metric-1" onRemove={jest.fn()} />);

    expect(
      await screen.findByText(
        'Target: each tool call named issue_refund · from Correct refund arguments'
      )
    ).toBeInTheDocument();
    expect(screen.getByTestId('BuildIcon')).toBeInTheDocument();
  });

  it('hands back the filters the target set when removed', async () => {
    mockGetMetric.mockResolvedValue({
      id: 'metric-1',
      name: 'Correct refund arguments',
      config: { target: { on: 'tool_call', name: 'issue_refund' } },
    });
    const onRemove = jest.fn();

    render(<TargetFilterChip metricId="metric-1" onRemove={onRemove} />);
    await screen.findByTestId('target-filter-chip');
    fireEvent.click(screen.getByTestId('CancelIcon'));

    expect(onRemove).toHaveBeenCalledWith({
      spanTypes: ['tool.invoke'],
      tools: ['issue_refund'],
    });
  });

  it('says which parts of the target the list does not apply', async () => {
    mockGetMetric.mockResolvedValue({
      id: 'metric-1',
      name: 'Refund matches the order',
      config: {
        target: {
          on: 'tool_call',
          name: 'issue_refund',
          within: 'billing_agent',
          where: { 'rhesis.reported.metadata.channel': 'web' },
        },
      },
    });

    render(<TargetFilterChip metricId="metric-1" onRemove={jest.fn()} />);

    expect(
      await screen.findByTestId('target-filter-unapplied')
    ).toHaveTextContent(
      'Not applied here: inside billing_agent, rhesis.reported.metadata.channel is web'
    );
  });

  it('shows nothing when the metric cannot be read', async () => {
    mockGetMetric.mockRejectedValue(new Error('not found'));

    render(<TargetFilterChip metricId="gone" onRemove={jest.fn()} />);

    await new Promise(resolve => setTimeout(resolve, 0));
    expect(screen.queryByTestId('target-filter-chip')).not.toBeInTheDocument();
  });
});
