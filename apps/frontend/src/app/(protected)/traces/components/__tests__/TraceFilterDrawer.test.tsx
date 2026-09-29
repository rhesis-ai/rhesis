import React from 'react';
import { render, screen, fireEvent } from '@/test-utils';
import '@testing-library/jest-dom';

import TraceFilterDrawer from '../TraceFilterDrawer';
import { EMPTY_TRACE_DRAWER_FILTERS } from '../trace-filter-params';

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'authenticated' }),
}));

jest.mock('@/hooks/useEndpoints', () => ({
  useEndpoints: () => ({ data: [] }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getProjectsClient: () => ({ getProjects: async () => [] }),
    getTelemetryClient: () => ({ getProviders: async () => [] }),
  })),
}));

function renderDrawer(
  props: Partial<React.ComponentProps<typeof TraceFilterDrawer>> = {}
) {
  const onApply = jest.fn();
  render(
    <TraceFilterDrawer
      open
      onClose={jest.fn()}
      filters={EMPTY_TRACE_DRAWER_FILTERS}
      onApply={onApply}
      {...props}
    />
  );
  return { onApply };
}

describe('TraceFilterDrawer conversation filter', () => {
  it('applies the picked turn type', async () => {
    const { onApply } = renderDrawer();

    fireEvent.click(await screen.findByRole('button', { name: 'Multi-Turn' }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({ traceType: 'Multi-Turn' })
    );
  });

  it('clears the turn type when the active chip is clicked again', async () => {
    const { onApply } = renderDrawer({
      filters: { ...EMPTY_TRACE_DRAWER_FILTERS, traceType: 'Multi-Turn' },
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Multi-Turn' }));
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(onApply.mock.calls[0][0].traceType).toBeUndefined();
  });

  it('is hidden on a test run', async () => {
    renderDrawer({ fixedTestRunId: 'run-1' });

    expect(await screen.findByText('Evaluation')).toBeInTheDocument();
    expect(screen.queryByText('Conversation')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Single-Turn' })
    ).not.toBeInTheDocument();
  });
});
