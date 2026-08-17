import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEndpointDetail } from '../useEndpointDetail';
import { endpointKeys } from '@/constants/query-keys';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), refresh: jest.fn() }),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'tok', user: { id: 'u1', name: 'Alice' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn(), close: jest.fn() }),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

const mockUpdateEndpoint = jest.fn();
const mockCreateEndpoint = jest.fn();

jest.mock('@/actions/endpoints', () => ({
  updateEndpoint: (...args: unknown[]) => mockUpdateEndpoint(...args),
  createEndpoint: (...args: unknown[]) => mockCreateEndpoint(...args),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getProjectsClient: () => ({ getProjects: jest.fn().mockResolvedValue([]) }),
  })),
}));

const initialEndpoint: Endpoint = {
  id: 'b6e8f1a2-3c4d-4e5f-8a9b-0c1d2e3f4a5b',
  name: 'Test Endpoint',
  connection_type: 'REST',
  environment: 'development',
  config_source: 'manual',
  response_format: 'json',
  status: {
    id: 'b6e8f1a2-3c4d-4e5f-8a9b-0c1d2e3f4a5c',
    name: 'Active',
    entity_type: 'endpoint',
  },
};

const wrapper = (queryClient: QueryClient) =>
  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };

describe('useEndpointDetail', () => {
  it('invalidates endpoint queries after a successful save', async () => {
    mockUpdateEndpoint.mockResolvedValue({
      success: true,
      data: initialEndpoint,
    });
    const queryClient = new QueryClient();
    const invalidateSpy = jest.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useEndpointDetail(initialEndpoint), {
      wrapper: wrapper(queryClient),
    });

    await result.current.saveFields({ name: 'Renamed Endpoint' });

    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: endpointKeys.all(),
      })
    );
  });

  it('keeps the just-saved change in the detail cache', async () => {
    mockUpdateEndpoint.mockResolvedValue({
      success: true,
      data: initialEndpoint,
    });
    const queryClient = new QueryClient();
    queryClient.setQueryData(
      endpointKeys.detail(initialEndpoint.id),
      initialEndpoint
    );

    const { result } = renderHook(() => useEndpointDetail(initialEndpoint), {
      wrapper: wrapper(queryClient),
    });

    await result.current.saveFields({ name: 'Renamed Endpoint' });

    const cached = queryClient.getQueryData<Endpoint>(
      endpointKeys.detail(initialEndpoint.id)
    );
    expect(cached?.name).toBe('Renamed Endpoint');
  });
});
