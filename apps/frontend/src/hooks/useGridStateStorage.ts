import { useCallback, useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import type { GridInitialState } from '@mui/x-data-grid';

const STORAGE_KEY_PREFIX = 'rhesis_grid_state_';

/**
 * Sanitize pathname to create a valid localStorage key
 */
function sanitizePathname(pathname: string): string {
  return pathname
    .replace(/^\//, '') // Remove leading slash
    .replace(/\//g, '_') // Replace slashes with underscores
    .replace(/[^a-zA-Z0-9_-]/g, ''); // Remove invalid characters
}

/**
 * Load grid state from localStorage
 */
function loadState(storageKey: string): GridInitialState | null {
  if (typeof window === 'undefined') return null;

  try {
    const stored = localStorage.getItem(storageKey);
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.error('Failed to load grid state:', error);
  }

  return null;
}

/**
 * Save grid state to localStorage
 */
function saveState(storageKey: string, state: GridInitialState): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem(storageKey, JSON.stringify(state));
  } catch (error) {
    console.error('Failed to save grid state:', error);
  }
}

interface UseGridStateStorageOptions {
  /**
   * Custom storage key. If not provided, uses the current pathname.
   */
  storageKey?: string;
  /**
   * Debounce delay in milliseconds for saving state. Default: 500ms
   */
  debounceMs?: number;
}

interface UseGridStateStorageReturn {
  /**
   * Initial state to pass to the DataGrid
   */
  initialState: GridInitialState | undefined;
  /**
   * Save the current grid state. Call this when state changes.
   */
  saveGridState: (apiRef: React.MutableRefObject<any>) => void;
  /**
   * The storage key being used
   */
  storageKey: string;
  /**
   * Whether the persisted state has been loaded (always true after first client render)
   */
  isLoaded: boolean;
}

/**
 * Hook for persisting MUI DataGrid state to localStorage.
 *
 * Usage:
 * ```tsx
 * const { initialState, saveGridState, storageKey } = useGridStateStorage();
 *
 * // Pass initialState to DataGrid
 * <DataGrid initialState={initialState} ... />
 *
 * // Call saveGridState when state changes (e.g., in event handlers)
 * ```
 */
export function useGridStateStorage(
  options: UseGridStateStorageOptions = {}
): UseGridStateStorageReturn {
  const pathname = usePathname();
  const { storageKey: customKey, debounceMs = 500 } = options;

  // Generate storage key from pathname or use custom key
  const storageKey = customKey
    ? `${STORAGE_KEY_PREFIX}${customKey}`
    : `${STORAGE_KEY_PREFIX}${sanitizePathname(pathname || 'default')}`;

  // Track whether we've loaded the persisted state (for SSR hydration)
  const [isLoaded, setIsLoaded] = useState(false);

  // Load initial state from localStorage
  // Start with undefined, then load on client after mount
  const [initialState, setInitialState] = useState<
    GridInitialState | undefined
  >(undefined);

  // Load state on mount (client-side only, runs once after hydration)
  useEffect(() => {
    const savedState = loadState(storageKey);
    if (savedState) {
      setInitialState(savedState);
    }
    setIsLoaded(true);
  }, [storageKey]);

  // Debounce timer ref
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * Save grid state with debouncing.
   * Exports only the relevant parts of the state to keep localStorage lean.
   */
  const saveGridState = useCallback(
    (apiRef: React.MutableRefObject<any>) => {
      // Clear existing debounce timer
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(() => {
        debounceTimerRef.current = null;

        try {
          // Export the full state from DataGrid
          const exportedState = apiRef.current.exportState();

          // Extract only the parts we want to persist
          const stateToSave: GridInitialState = {};

          // Column visibility
          if (exportedState.columns?.columnVisibilityModel) {
            stateToSave.columns = {
              ...stateToSave.columns,
              columnVisibilityModel:
                exportedState.columns.columnVisibilityModel,
            };
          }

          // Column order (orderedFields)
          if (exportedState.columns?.orderedFields) {
            stateToSave.columns = {
              ...stateToSave.columns,
              orderedFields: exportedState.columns.orderedFields,
            };
          }

          // Column dimensions (widths)
          if (exportedState.columns?.dimensions) {
            stateToSave.columns = {
              ...stateToSave.columns,
              dimensions: exportedState.columns.dimensions,
            };
          }

          // Sorting
          if (exportedState.sorting?.sortModel) {
            stateToSave.sorting = {
              sortModel: exportedState.sorting.sortModel,
            };
          }

          // Filtering (only for client-side filtering)
          if (exportedState.filter?.filterModel) {
            stateToSave.filter = {
              filterModel: exportedState.filter.filterModel,
            };
          }

          // Density
          if (exportedState.density) {
            stateToSave.density = exportedState.density;
          }

          // Pagination (only page size, not current page)
          if (exportedState.pagination?.paginationModel?.pageSize) {
            stateToSave.pagination = {
              paginationModel: {
                pageSize: exportedState.pagination.paginationModel.pageSize,
                page: 0, // Always start on first page
              },
            };
          }

          saveState(storageKey, stateToSave);
        } catch (error) {
          console.error('Failed to export grid state:', error);
        }
      }, debounceMs);
    },
    [storageKey, debounceMs]
  );

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return {
    initialState,
    saveGridState,
    storageKey,
    isLoaded,
  };
}

/**
 * Clear stored grid state for a specific key or all grid states
 */
export function clearGridState(storageKey?: string): void {
  if (typeof window === 'undefined') return;

  try {
    if (storageKey) {
      localStorage.removeItem(`${STORAGE_KEY_PREFIX}${storageKey}`);
    } else {
      // Clear all grid states
      const keys = Object.keys(localStorage);
      keys.forEach(key => {
        if (key.startsWith(STORAGE_KEY_PREFIX)) {
          localStorage.removeItem(key);
        }
      });
    }
  } catch (error) {
    console.error('Failed to clear grid state:', error);
  }
}
