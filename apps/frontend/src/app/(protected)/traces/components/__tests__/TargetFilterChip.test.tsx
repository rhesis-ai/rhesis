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

const REFUND_TARGET = {
  on: 'tool_call',
  name: 'issue_refund',
  within: 'billing_agent',
  where: [{ field: 'app.channel', op: '!=', value: 'internal' }],
};
const REFUND_METRIC = {
  id: 'metric-1',
  name: 'Correct refund arguments',
  config: { target: REFUND_TARGET },
  target_summary_short:
    'each tool call named `issue_refund` inside `billing_agent`, where `app.channel` is not `internal`',
};

describe('TargetFilterChip', () => {
  it("names the target in the API's words and the metric it came from", async () => {
    mockGetMetric.mockResolvedValue(REFUND_METRIC);

    render(
      <TargetFilterChip
        metricId="metric-1"
        target={JSON.stringify(REFUND_TARGET)}
        onRemove={jest.fn()}
      />
    );

    const chip = await screen.findByText(/· from Correct refund arguments/);
    expect(chip).toHaveTextContent(
      'Target: each tool call named issue_refund inside billing_agent, where app.channel is not internal · from Correct refund arguments'
    );
    expect(screen.getByTestId('BuildIcon')).toBeInTheDocument();
  });

  it('notes nothing as unapplied: every target filters exactly', async () => {
    mockGetMetric.mockResolvedValue(REFUND_METRIC);

    render(
      <TargetFilterChip
        metricId="metric-1"
        target={JSON.stringify(REFUND_TARGET)}
        onRemove={jest.fn()}
      />
    );

    await screen.findByText(/· from Correct refund arguments/);
    expect(screen.queryByText(/Not applied here/)).not.toBeInTheDocument();
  });

  it('calls onRemove when removed', async () => {
    mockGetMetric.mockResolvedValue(REFUND_METRIC);
    const onRemove = jest.fn();

    render(
      <TargetFilterChip
        metricId="metric-1"
        target={JSON.stringify(REFUND_TARGET)}
        onRemove={onRemove}
      />
    );
    await screen.findByText(/· from Correct refund arguments/);
    fireEvent.click(screen.getByTestId('CancelIcon'));

    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it("doesn't borrow the metric's words for a different target", async () => {
    mockGetMetric.mockResolvedValue(REFUND_METRIC);

    render(
      <TargetFilterChip
        metricId="metric-1"
        target={JSON.stringify({ on: 'turn' })}
        onRemove={jest.fn()}
      />
    );

    expect(await screen.findByTestId('target-filter-chip')).toHaveTextContent(
      /^Target: Each turn$/
    );
  });

  it('shows a target with no metric behind it by its preset', () => {
    render(
      <TargetFilterChip
        target={JSON.stringify({ on: 'tool_call', name: 'issue_refund' })}
        onRemove={jest.fn()}
      />
    );

    expect(screen.getByTestId('target-filter-chip')).toHaveTextContent(
      'Target: Each tool call (issue_refund)'
    );
  });

  it('still names an old link’s metric, which carries no target', async () => {
    mockGetMetric.mockResolvedValue(REFUND_METRIC);

    render(<TargetFilterChip metricId="metric-1" onRemove={jest.fn()} />);

    expect(
      await screen.findByText(/· from Correct refund arguments/)
    ).toBeInTheDocument();
  });

  it("hands an old link the metric's target, so the list filters what the chip names", async () => {
    mockGetMetric.mockResolvedValue(REFUND_METRIC);
    const onTargetLoaded = jest.fn();

    render(
      <TargetFilterChip
        metricId="metric-1"
        onRemove={jest.fn()}
        onTargetLoaded={onTargetLoaded}
      />
    );

    await screen.findByText(/· from Correct refund arguments/);
    expect(onTargetLoaded).toHaveBeenCalledWith(JSON.stringify(REFUND_TARGET));
  });

  it('leaves a link that carries its target alone', async () => {
    mockGetMetric.mockResolvedValue(REFUND_METRIC);
    const onTargetLoaded = jest.fn();

    render(
      <TargetFilterChip
        metricId="metric-1"
        target={JSON.stringify(REFUND_TARGET)}
        onRemove={jest.fn()}
        onTargetLoaded={onTargetLoaded}
      />
    );

    await screen.findByText(/· from Correct refund arguments/);
    expect(onTargetLoaded).not.toHaveBeenCalled();
  });

  it('shows nothing when the metric cannot be read and no target is set', async () => {
    mockGetMetric.mockRejectedValue(new Error('not found'));

    render(<TargetFilterChip metricId="gone" onRemove={jest.fn()} />);

    await new Promise(resolve => setTimeout(resolve, 0));
    expect(screen.queryByTestId('target-filter-chip')).not.toBeInTheDocument();
  });
});
