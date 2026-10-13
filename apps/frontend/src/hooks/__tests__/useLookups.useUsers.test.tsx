import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { useUsers } from '../useLookups';
import { userKeys } from '@/constants/query-keys';

const mockGetAllUsers = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getUsersClient: () => ({ getAllUsers: mockGetAllUsers }),
  })),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1' } },
    status: 'authenticated',
  }),
}));

const USERS = Array.from({ length: 150 }, (_, i) => ({
  id: `u${i}`,
  name: `User ${i}`,
}));

function newClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

describe('useUsers', () => {
  beforeEach(() => {
    mockGetAllUsers.mockReset();
    mockGetAllUsers.mockResolvedValue(USERS);
  });

  it('returns every user, not just the first page', async () => {
    const client = newClient();
    const { result } = renderHook(() => useUsers(), {
      wrapper: wrapperFor(client),
    });

    await waitFor(() => expect(result.current.data).toHaveLength(150));
    expect(client.getQueryData(userKeys.list())).toHaveLength(150);
  });

  it('shares one fetch between drawers', async () => {
    const wrapper = wrapperFor(newClient());
    const first = renderHook(() => useUsers(), { wrapper });
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true));

    const second = renderHook(() => useUsers(), { wrapper });
    expect(second.result.current.data).toHaveLength(150);
    expect(mockGetAllUsers).toHaveBeenCalledTimes(1);
  });

  it('does not fetch while disabled', () => {
    renderHook(() => useUsers(false), { wrapper: wrapperFor(newClient()) });
    expect(mockGetAllUsers).not.toHaveBeenCalled();
  });
});
