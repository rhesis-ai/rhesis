import { renderHook, act, waitFor } from '@testing-library/react';
import { useGridStateStorage, clearGridState } from '../useGridStateStorage';

// next/navigation is mocked globally in jest.setup.js

const STORAGE_KEY_PREFIX = 'rhesis_grid_state_';

describe('useGridStateStorage', () => {
  let getItemSpy: jest.SpyInstance;
  let setItemSpy: jest.SpyInstance;
  let removeItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    // Spy on Storage.prototype so we intercept jsdom's real localStorage
    getItemSpy = jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    setItemSpy = jest
      .spyOn(Storage.prototype, 'setItem')
      .mockImplementation(() => {});
    removeItemSpy = jest
      .spyOn(Storage.prototype, 'removeItem')
      .mockImplementation(() => {});
  });

  afterEach(() => {
    getItemSpy.mockRestore();
    setItemSpy.mockRestore();
    removeItemSpy.mockRestore();
  });

  describe('initialization', () => {
    it('returns undefined initialState when localStorage is empty', async () => {
      const { result } = renderHook(() => useGridStateStorage());

      await waitFor(() => {
        expect(result.current.isLoaded).toBe(true);
      });

      expect(result.current.initialState).toBeUndefined();
    });

    it('loads persisted state from localStorage on mount', async () => {
      const savedState = {
        columns: { columnVisibilityModel: { name: false } },
        sorting: { sortModel: [{ field: 'name', sort: 'asc' as const }] },
      };
      getItemSpy.mockReturnValue(JSON.stringify(savedState));

      const { result } = renderHook(() => useGridStateStorage());

      await waitFor(() => {
        expect(result.current.isLoaded).toBe(true);
      });

      expect(result.current.initialState).toEqual(savedState);
    });

    it('handles corrupted localStorage data gracefully', async () => {
      getItemSpy.mockReturnValue('invalid-json{{{');

      const { result } = renderHook(() => useGridStateStorage());

      await waitFor(() => {
        expect(result.current.isLoaded).toBe(true);
      });

      expect(result.current.initialState).toBeUndefined();
    });

    it('generates storage key from pathname by default', async () => {
      const { result } = renderHook(() => useGridStateStorage());

      await waitFor(() => {
        expect(result.current.isLoaded).toBe(true);
      });

      // pathname is '/' from the jest.setup.js mock → sanitized to '' (leading slash removed)
      expect(result.current.storageKey).toBe(`${STORAGE_KEY_PREFIX}`);
    });

    it('uses custom storage key when provided', async () => {
      const { result } = renderHook(() =>
        useGridStateStorage({ storageKey: 'my-custom-grid' })
      );

      await waitFor(() => {
        expect(result.current.isLoaded).toBe(true);
      });

      expect(result.current.storageKey).toBe(
        `${STORAGE_KEY_PREFIX}my-custom-grid`
      );
    });
  });

  describe('saveGridState', () => {
    it('saves grid state to localStorage via the apiRef', async () => {
      jest.useFakeTimers();

      const mockState = {
        columns: {
          columnVisibilityModel: { description: false },
          orderedFields: ['id', 'name'],
          dimensions: {},
        },
        sorting: { sortModel: [] },
        filter: { filterModel: { items: [] } },
        density: 'standard' as const,
        pagination: { paginationModel: { page: 2, pageSize: 25 } },
      };

      const mockApiRef = {
        current: {
          exportState: jest.fn().mockReturnValue(mockState),
        },
      };

      const { result } = renderHook(() => useGridStateStorage());

      await waitFor(() => {
        expect(result.current.isLoaded).toBe(true);
      });

      act(() => {
        result.current.saveGridState(mockApiRef as never);
      });

      // State is debounced — advance timers to trigger the save
      act(() => {
        jest.advanceTimersByTime(600);
      });

      expect(setItemSpy).toHaveBeenCalledWith(
        expect.stringContaining(STORAGE_KEY_PREFIX),
        expect.stringContaining('"pageSize":25')
      );

      // Pagination page should always be reset to 0
      const savedArg = setItemSpy.mock.calls[0][1];
      const parsed = JSON.parse(savedArg);
      expect(parsed.pagination.paginationModel.page).toBe(0);

      jest.useRealTimers();
    });

    it('does nothing when apiRef.current is null', async () => {
      jest.useFakeTimers();

      const mockApiRef = { current: null };

      const { result } = renderHook(() => useGridStateStorage());

      await waitFor(() => {
        expect(result.current.isLoaded).toBe(true);
      });

      act(() => {
        result.current.saveGridState(mockApiRef as never);
      });

      act(() => {
        jest.advanceTimersByTime(600);
      });

      expect(setItemSpy).not.toHaveBeenCalled();

      jest.useRealTimers();
    });

    it('debounces rapid saves and only writes once', async () => {
      jest.useFakeTimers();

      const mockState = {
        columns: { columnVisibilityModel: {} },
        pagination: { paginationModel: { page: 0, pageSize: 10 } },
      };
      const mockApiRef = {
        current: { exportState: jest.fn().mockReturnValue(mockState) },
      };

      const { result } = renderHook(() =>
        useGridStateStorage({ debounceMs: 500 })
      );

      await waitFor(() => {
        expect(result.current.isLoaded).toBe(true);
      });

      act(() => {
        result.current.saveGridState(mockApiRef as never);
        result.current.saveGridState(mockApiRef as never);
        result.current.saveGridState(mockApiRef as never);
      });

      act(() => {
        jest.advanceTimersByTime(600);
      });

      // Should only have written once despite three calls
      expect(setItemSpy).toHaveBeenCalledTimes(1);

      jest.useRealTimers();
    });
  });
});

describe('clearGridState', () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it('removes a specific grid state key from localStorage', () => {
    window.localStorage.setItem(
      `${STORAGE_KEY_PREFIX}my-grid`,
      '{"columns":{}}'
    );

    clearGridState('my-grid');

    expect(
      window.localStorage.getItem(`${STORAGE_KEY_PREFIX}my-grid`)
    ).toBeNull();
  });

  it('clears all grid state keys but leaves unrelated keys', () => {
    window.localStorage.setItem(`${STORAGE_KEY_PREFIX}page-a`, '{}');
    window.localStorage.setItem(`${STORAGE_KEY_PREFIX}page-b`, '{}');
    window.localStorage.setItem('unrelated-key', 'value');

    clearGridState();

    expect(
      window.localStorage.getItem(`${STORAGE_KEY_PREFIX}page-a`)
    ).toBeNull();
    expect(
      window.localStorage.getItem(`${STORAGE_KEY_PREFIX}page-b`)
    ).toBeNull();
    expect(window.localStorage.getItem('unrelated-key')).toBe('value');
  });
});
