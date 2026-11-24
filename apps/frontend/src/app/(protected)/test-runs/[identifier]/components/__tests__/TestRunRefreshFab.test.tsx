import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

let mockAccessibilityMode = true;
jest.mock('@/hooks/useAccessibilityMode', () => ({
  useAccessibilityMode: () => mockAccessibilityMode,
}));
const mockAnnounce = jest.fn();
jest.mock('@/components/common/LiveAnnouncer', () => ({
  useAnnounce: () => mockAnnounce,
}));
jest.mock('../TestRunSummarizeFab', () => ({
  __esModule: true,
  default: () => null,
}));

import { TestRunActions, describeRefreshedRun } from '../TestRunDetailHeader';

function run(status: string, stats?: TestRunDetail['stats']) {
  return {
    id: 'run-1',
    status: { name: status },
    stats,
  } as unknown as TestRunDetail;
}

function actions(testRun: TestRunDetail, queryClient: QueryClient) {
  return (
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

function renderActions(status: string, queryClient = new QueryClient()) {
  return render(actions(run(status), queryClient));
}

describe('Refresh results button', () => {
  beforeEach(() => {
    mockAccessibilityMode = true;
    mockAnnounce.mockReset();
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

  it('stays and announces the new state when the run finished meanwhile', async () => {
    const queryClient = new QueryClient();
    let rerender: (ui: React.ReactElement) => void = () => {};
    jest
      .spyOn(queryClient, 'invalidateQueries')
      .mockImplementation(async () => {
        // The refetch lands before invalidateQueries resolves.
        rerender(
          actions(run('completed', { total: 4, passed: 3 }), queryClient)
        );
      });
    ({ rerender } = render(actions(run('progress'), queryClient)));

    fireEvent.click(screen.getByRole('button', { name: 'Refresh results' }));

    await waitFor(() =>
      expect(mockAnnounce).toHaveBeenCalledWith(
        'Results updated. Status: Completed. 3 of 4 tests passed.'
      )
    );
    expect(
      screen.getByRole('button', { name: 'Refresh results' })
    ).toBeInTheDocument();
  });

  it('is not shown for a run that had already finished', () => {
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

describe('describeRefreshedRun', () => {
  it('leaves out counts the run does not have', () => {
    expect(describeRefreshedRun(run('progress'))).toBe(
      'Results updated. Status: In Progress.'
    );
  });
});
