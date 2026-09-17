import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { annotationKeys } from '@/constants/query-keys';
import { useTestRunAnnotations } from '../useTestRunAnnotations';
import type { Annotation } from '@/utils/api-client/interfaces/annotation';

const getAnnotations = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getAnnotationsClient: () => ({ getAnnotations }),
  })),
}));

jest.mock('@/hooks/useIsAuthenticated', () => ({
  useIsAuthenticated: () => true,
}));

function annotation(id: string): Annotation {
  return {
    id,
    entity_type: 'TestResult',
    entity_id: `result-${id}`,
  } as Annotation;
}

function resolvesTo(rows: Annotation[], totalCount = rows.length) {
  getAnnotations.mockResolvedValue({
    data: rows,
    pagination: { totalCount, skip: 0, limit: 100 },
  });
}

let queryClient: QueryClient;

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useTestRunAnnotations', () => {
  beforeEach(() => {
    getAnnotations.mockReset();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  it('counts zero and lists nothing before the request resolves', () => {
    resolvesTo([annotation('a1')]);
    const { result } = renderHook(() => useTestRunAnnotations('run1'), {
      wrapper,
    });

    expect(result.current.count).toBe(0);
    expect(result.current.annotations).toEqual([]);
    expect(result.current.isLoading).toBe(true);
  });

  it('returns the annotations recorded across the run', async () => {
    resolvesTo([annotation('a1'), annotation('a2'), annotation('a3')]);
    const { result } = renderHook(() => useTestRunAnnotations('run1'), {
      wrapper,
    });

    await waitFor(() => expect(result.current.count).toBe(3));
    expect(result.current.annotations).toHaveLength(3);
  });

  it('counts the server total, not the rows it happened to render', async () => {
    // A run past the page cap: the badge must still say how many there are.
    resolvesTo([annotation('a1'), annotation('a2')], 137);
    const { result } = renderHook(() => useTestRunAnnotations('run1'), {
      wrapper,
    });

    await waitFor(() => expect(result.current.count).toBe(137));
    expect(result.current.annotations).toHaveLength(2);
  });

  it('shares one request between every caller on the same run', async () => {
    resolvesTo([annotation('a1')]);
    const { result: first } = renderHook(() => useTestRunAnnotations('run1'), {
      wrapper,
    });
    const { result: second } = renderHook(() => useTestRunAnnotations('run1'), {
      wrapper,
    });

    await waitFor(() => expect(first.current.count).toBe(1));
    expect(second.current.count).toBe(1);
    expect(getAnnotations).toHaveBeenCalledTimes(1);
  });

  it('refetches when an annotation is written', async () => {
    // What useAnnotationMutations does after a create, edit or delete. The badge
    // only tracks those writes if this key sits under the prefix it invalidates.
    resolvesTo([annotation('a1')]);
    const { result } = renderHook(() => useTestRunAnnotations('run1'), {
      wrapper,
    });
    await waitFor(() => expect(result.current.count).toBe(1));

    resolvesTo([annotation('a1'), annotation('a2')]);
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: annotationKeys.all() });
    });

    await waitFor(() => expect(result.current.count).toBe(2));
  });

  it('scopes the request to the run', async () => {
    resolvesTo([]);
    renderHook(() => useTestRunAnnotations('run1'), { wrapper });

    await waitFor(() => expect(getAnnotations).toHaveBeenCalled());
    expect(getAnnotations).toHaveBeenCalledWith(
      expect.objectContaining({ test_run_id: 'run1' })
    );
  });
});
