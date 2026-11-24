import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

let mockAccessibilityMode = true;
jest.mock('@/hooks/useAccessibilityMode', () => ({
  useAccessibilityMode: () => mockAccessibilityMode,
}));
jest.mock('../TestRunSummarizeFab', () => ({
  __esModule: true,
  default: () => null,
}));

import { TestRunActions } from '../TestRunDetailHeader';

function renderActions(status: string, queryClient = new QueryClient()) {
  const testRun = {
    id: 'run-1',
    status: { name: status },
  } as unknown as TestRunDetail;
  render(
    <QueryClientProvider client={queryClient}>
      <TestRunActions
        testRun={testRun}
        onCompare={jest.fn()}
        onDownload={jest.fn()}
        onRerun={jest.fn()}
      />
    </QueryClientProvider>
  );
}

describe('Refresh results button', () => {
  beforeEach(() => {
    mockAccessibilityMode = true;
  });

  it('reloads a running test run on demand in accessibility mode', async () => {
    const queryClient = new QueryClient();
    const invalidate = jest.spyOn(queryClient, 'invalidateQueries');
    renderActions('progress', queryClient);

    fireEvent.click(screen.getByRole('button', { name: 'Refresh results' }));

    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['test-runs'] })
    );
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['test-run-usage'] });
  });

  it('is not shown once the run has finished', () => {
    renderActions('completed');
    expect(
      screen.queryByRole('button', { name: 'Refresh results' })
    ).not.toBeInTheDocument();
  });

  it('is not shown outside accessibility mode, where results update live', () => {
    mockAccessibilityMode = false;
    renderActions('progress');
    expect(
      screen.queryByRole('button', { name: 'Refresh results' })
    ).not.toBeInTheDocument();
  });
});
