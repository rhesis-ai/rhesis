import { renderHook, act, waitFor } from '@testing-library/react';
import { usePaginatedList } from '../usePaginatedList';

const mockUseSession = jest.fn();
jest.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
}));

describe('usePaginatedList with server-prefetched data', () => {
  beforeEach(() => {
    mockUseSession.mockReset();
  });

  it('does not refetch (or flip isLoading) when the session and auth gate settle', async () => {
    const fetchPage = jest.fn();
    mockUseSession.mockReturnValue({ status: 'loading' });
    let enabled = false;

    const { result, rerender } = renderHook(() =>
      usePaginatedList<{ id: string }>({
        fetchPage,
        filterFingerprint: 'fp',
        initialData: [],
        initialTotalCount: 0,
        enabled,
      })
    );
    expect(result.current.isLoading).toBe(false);

    mockUseSession.mockReturnValue({ status: 'authenticated' });
    enabled = true;
    rerender();

    await act(async () => {});
    expect(fetchPage).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.totalCount).toBe(0);
  });

  it('still fetches once the filters change', async () => {
    const fetchPage = jest.fn().mockResolvedValue({
      data: [{ id: '1' }],
      pagination: { totalCount: 1 },
    });
    mockUseSession.mockReturnValue({ status: 'authenticated' });
    let fingerprint = 'fp';

    const { result, rerender } = renderHook(() =>
      usePaginatedList<{ id: string }>({
        fetchPage,
        filterFingerprint: fingerprint,
        initialData: [],
        initialTotalCount: 0,
      })
    );
    expect(fetchPage).not.toHaveBeenCalled();

    fingerprint = 'fp2';
    rerender();

    await waitFor(() => expect(result.current.totalCount).toBe(1));
    expect(fetchPage).toHaveBeenCalledTimes(1);
  });

  it('fetches only page 0 when the filters change on a later page', async () => {
    const fetchPage = jest.fn().mockResolvedValue({
      data: [{ id: '1' }],
      pagination: { totalCount: 100 },
    });
    mockUseSession.mockReturnValue({ status: 'authenticated' });
    let fingerprint = 'fp';

    const { result, rerender } = renderHook(() =>
      usePaginatedList<{ id: string }>({
        fetchPage,
        filterFingerprint: fingerprint,
        initialData: [],
        initialTotalCount: 100,
        defaultPageSize: 10,
      })
    );

    act(() => result.current.onPageChange(2));
    await waitFor(() => expect(fetchPage).toHaveBeenCalledTimes(1));
    expect(fetchPage).toHaveBeenLastCalledWith({ skip: 20, limit: 10 });

    fingerprint = 'fp2';
    rerender();

    await waitFor(() => expect(result.current.page).toBe(0));
    await act(async () => {});
    expect(fetchPage.mock.calls.slice(1)).toEqual([[{ skip: 0, limit: 10 }]]);
  });
});
