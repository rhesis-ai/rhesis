/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { Project } from '@/utils/api-client/interfaces/project';
import ProjectTraceMetrics from '../ProjectTraceMetrics';

const mockFetchProjectTraceMetrics = jest.fn();

jest.mock('../project-data', () => ({
  ...jest.requireActual('../project-data'),
  fetchProjectTraceMetrics: (...args: unknown[]) =>
    mockFetchProjectTraceMetrics(...args),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn(),
}));

// The real grid needs layout jsdom doesn't have; the row names are enough here.
jest.mock('@/components/common/BaseDataGrid', () => ({
  __esModule: true,
  default: ({ rows }: { rows: MetricDetail[] }) => (
    <ul>
      {rows.map(row => (
        <li key={row.id}>{row.name}</li>
      ))}
    </ul>
  ),
}));

jest.mock('@/components/common/SelectMetricsDialog', () => ({
  __esModule: true,
  default: () => null,
}));

const metric = (id: string, name: string) =>
  ({ id, name, score_type: 'binary' }) as unknown as MetricDetail;

const project = (traceMetrics: string[]) =>
  ({
    id: 'project-1',
    attributes: { trace_metrics: traceMetrics },
  }) as any as Project;

describe('ProjectTraceMetrics', () => {
  it('refetches when a metric is added after the server render', async () => {
    // Same default staleTime as the app, so the seed would otherwise stay fresh.
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 5 * 60_000 } },
    });
    const onProjectUpdate = jest.fn().mockResolvedValue(true);
    const wrap = (ids: string[]) => (
      <QueryClientProvider client={queryClient}>
        <ProjectTraceMetrics
          project={project(ids)}
          onProjectUpdate={onProjectUpdate}
          initialMetrics={[metric('m-1', 'Toxicity')]}
        />
      </QueryClientProvider>
    );
    mockFetchProjectTraceMetrics.mockResolvedValue([
      metric('m-1', 'Toxicity'),
      metric('m-2', 'Relevance'),
    ]);

    const { rerender } = render(wrap(['m-1']));
    expect(screen.getByText('Toxicity')).toBeInTheDocument();
    expect(mockFetchProjectTraceMetrics).not.toHaveBeenCalled();

    rerender(wrap(['m-1', 'm-2']));

    expect(await screen.findByText('Relevance')).toBeInTheDocument();
    await waitFor(() =>
      expect(mockFetchProjectTraceMetrics).toHaveBeenCalledWith(
        expect.anything(),
        ['m-1', 'm-2']
      )
    );
  });
});
