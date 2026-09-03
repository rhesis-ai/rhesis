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
});
