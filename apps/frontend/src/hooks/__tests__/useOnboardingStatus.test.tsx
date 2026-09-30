import React from 'react';
import { renderHook, waitFor, act } from '@testing-library/react';
import {
  QueryClient,
  QueryClientProvider,
  focusManager,
} from '@tanstack/react-query';

import { useOnboardingStatus } from '../useOnboardingStatus';

const mockGetOnboardingStatus = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getUsersClient: () => ({ getOnboardingStatus: mockGetOnboardingStatus }),
  })),
}));

let mockOrganizationId: string | null = 'org-1';

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1', organization_id: mockOrganizationId } },
    status: 'authenticated',
  }),
}));

const STATUS = {
  project_created: true,
  endpoint_setup: false,
  users_invited: false,
  test_cases_created: false,
};

function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

function newClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

describe('useOnboardingStatus', () => {
  beforeEach(() => {
    mockGetOnboardingStatus.mockReset();
    mockGetOnboardingStatus.mockResolvedValue(STATUS);
    mockOrganizationId = 'org-1';
  });

  it('fetches the status when enabled', async () => {
    const { result } = renderHook(() => useOnboardingStatus(true), {
      wrapper: wrapperFor(newClient()),
    });

    await waitFor(() => expect(result.current.data).toEqual(STATUS));
    expect(mockGetOnboardingStatus).toHaveBeenCalledTimes(1);
  });

  it('does not fetch when disabled', () => {
    renderHook(() => useOnboardingStatus(false), {
      wrapper: wrapperFor(newClient()),
    });

    expect(mockGetOnboardingStatus).not.toHaveBeenCalled();
  });

  it('does not fetch for a user without an organization', () => {
    mockOrganizationId = null;

    renderHook(() => useOnboardingStatus(true), {
      wrapper: wrapperFor(newClient()),
    });

    expect(mockGetOnboardingStatus).not.toHaveBeenCalled();
  });

  it('refetches on every mount, even with fresh cached data', async () => {
    const client = newClient();
    const first = renderHook(() => useOnboardingStatus(true), {
      wrapper: wrapperFor(client),
    });
    await waitFor(() => expect(first.result.current.data).toEqual(STATUS));
    first.unmount();

    renderHook(() => useOnboardingStatus(true), {
      wrapper: wrapperFor(client),
    });

    await waitFor(() =>
      expect(mockGetOnboardingStatus).toHaveBeenCalledTimes(2)
    );
  });

  it('refetches when the window regains focus', async () => {
    const { result } = renderHook(() => useOnboardingStatus(true), {
      wrapper: wrapperFor(newClient()),
    });
    await waitFor(() => expect(result.current.data).toEqual(STATUS));

    act(() => {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
    });

    await waitFor(() =>
      expect(mockGetOnboardingStatus).toHaveBeenCalledTimes(2)
    );
    focusManager.setFocused(undefined);
  });
});
