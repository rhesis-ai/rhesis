import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { useTags } from '../useLookups';
import { EntityType } from '@/types/entity-type';

const mockGetTags = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTagsClient: () => ({ getTags: mockGetTags }),
  })),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1' } },
    status: 'authenticated',
  }),
}));

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

describe('useTags', () => {
  beforeEach(() => {
    mockGetTags.mockReset();
    mockGetTags.mockResolvedValue([{ id: 't1', name: 'release' }]);
  });

  it('asks for more than the default 10 tags', async () => {
    const { result } = renderHook(() => useTags(), {
      wrapper: wrapperFor(newClient()),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGetTags).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 100 })
    );
    expect(mockGetTags.mock.calls[0][0]).not.toHaveProperty('$filter');
  });

  it('lists only tags used on the given entity type', async () => {
    const { result } = renderHook(() => useTags(true, EntityType.TEST_SET), {
      wrapper: wrapperFor(newClient()),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGetTags).toHaveBeenCalledWith(
      expect.objectContaining({
        $filter: "tagged_items/any(i: i/entity_type eq 'TestSet')",
      })
    );
  });

  it('keeps a separate list per entity type', async () => {
    const wrapper = wrapperFor(newClient());
    const sets = renderHook(() => useTags(true, EntityType.TEST_SET), {
      wrapper,
    });
    await waitFor(() => expect(sets.result.current.isSuccess).toBe(true));

    const runs = renderHook(() => useTags(true, EntityType.TEST_RUN), {
      wrapper,
    });
    await waitFor(() => expect(runs.result.current.isSuccess).toBe(true));
    expect(mockGetTags).toHaveBeenCalledTimes(2);
  });

  it('refetches on each mount so newly added tags show up', async () => {
    const wrapper = wrapperFor(newClient());
    const first = renderHook(() => useTags(true, EntityType.TEST_SET), {
      wrapper,
    });
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true));
    first.unmount();

    renderHook(() => useTags(true, EntityType.TEST_SET), { wrapper });
    await waitFor(() => expect(mockGetTags).toHaveBeenCalledTimes(2));
  });

  it('does not fetch while disabled', () => {
    renderHook(() => useTags(false), { wrapper: wrapperFor(newClient()) });
    expect(mockGetTags).not.toHaveBeenCalled();
  });
});
