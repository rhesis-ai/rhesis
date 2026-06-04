import React, {
  useState,
  useEffect,
  useCallback,
  ReactNode,
  useRef,
} from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  styled,
  useTheme,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
  ButtonGroup,
  Popper,
  Grow,
  ClickAwayListener,
  MenuList,
  CircularProgress,
  TextField,
  InputAdornment,
  Menu,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import IconButton from '@mui/material/IconButton';
import {
  DataGrid,
  GridColDef,
  GridPaginationModel,
  GridRowModel,
  GridEditMode,
  GridDensity,
  GridRowSelectionModel,
  GridToolbar,
  GridToolbarQuickFilter,
  useGridApiRef,
  useGridApiContext,
  useGridSelector,
  gridPaginationModelSelector,
  gridRowCountSelector,
  GridFilterModel,
  GridSortModel,
  GridInitialState,
  GridRowParams,
  GridCellParams,
  GridColumnMenu,
  type GridColumnMenuProps,
  type GridToolbarProps,
} from '@mui/x-data-grid';
import type { SxProps, Theme } from '@mui/material/styles';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import ArrowBackIosNewIcon from '@mui/icons-material/ArrowBackIosNew';
import ArrowForwardIosIcon from '@mui/icons-material/ArrowForwardIos';
import { useGridStateStorage } from '@/hooks/useGridStateStorage';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';

interface FilterOption {
  value: string;
  label: string;
}

interface FilterConfig {
  name: string;
  label: string;
  filterField: string;
  options: FilterOption[];
  defaultValue: string;
}

interface BaseDataGridProps {
  columns: GridColDef[];
  rows: GridRowModel[];
  title?: string;
  loading?: boolean;
  getRowId?: (row: GridRowModel) => string | number;
  showToolbar?: boolean;
  onRowClick?: (params: GridRowParams) => void;
  density?: GridDensity;
  sx?: SxProps<Theme>;
  disableMultipleRowSelection?: boolean;
  actionButtons?: {
    href?: string;
    label: string;
    onClick?: () => void;
    icon?: React.ReactNode;
    variant?: 'text' | 'outlined' | 'contained';
    color?:
      | 'inherit'
      | 'primary'
      | 'secondary'
      | 'success'
      | 'error'
      | 'info'
      | 'warning';
    disabled?: boolean;
    splitButton?: {
      options: {
        label: string;
        onClick: () => void;
        disabled?: boolean;
      }[];
    };
    dataTour?: string;
  }[];
  // CRUD related props
  enableEditing?: boolean;
  editMode?: GridEditMode;
  processRowUpdate?: (
    newRow: GridRowModel,
    oldRow: GridRowModel
  ) => Promise<GridRowModel> | GridRowModel;
  onProcessRowUpdateError?: (error: unknown) => void;
  isCellEditable?: (params: GridCellParams) => boolean;
  // Selection related props
  checkboxSelection?: boolean;
  disableRowSelectionOnClick?: boolean;
  onRowSelectionModelChange?: (selectionModel: GridRowSelectionModel) => void;
  rowSelectionModel?: GridRowSelectionModel;
  /**
   * Per-row predicate that gates checkbox selection. Useful when some
   * rows in a grid aren't deletable (e.g. always-on overlay rows or
   * inline draft rows) and shouldn't appear "selectable" in a bulk
   * delete workflow. When omitted, every row is selectable — the MUI
   * default.
   */
  isRowSelectable?: (params: GridRowParams) => boolean;
  // Filter related props
  filters?: FilterConfig[];
  filterHandler?: (filteredRows: GridRowModel[]) => void;
  customToolbarContent?: ReactNode;
  /**
   * Extra content rendered inside the DataGrid's built-in toolbar, immediately
   * to the right of the standard Columns / Filters / Density / Export buttons
   * (and to the left of the search input). Use this for filter toggles that
   * conceptually belong next to the grid's existing filter UI rather than
   * alongside the page-level action buttons.
   */
  gridToolbarExtra?: ReactNode;
  // Server-side filtering props
  serverSideFiltering?: boolean;
  filterModel?: GridFilterModel;
  onFilterModelChange?: (model: GridFilterModel) => void;
  // Server-side sorting props
  sortingMode?: 'client' | 'server';
  sortModel?: GridSortModel;
  onSortModelChange?: (model: GridSortModel) => void;
  // Link related props
  linkPath?: string;
  linkField?: string;
  /**
   * Derive a detail-page URL from a row. When provided, grid rows support
   * right-click → "Open in new tab", middle-click, and Cmd/Ctrl+click in
   * addition to the standard left-click navigation. Falls back to
   * `linkPath`/`linkField` if not set.
   */
  getRowUrl?: (row: GridRowModel) => string | undefined;
  // Server-side pagination props
  serverSidePagination?: boolean;
  totalRows?: number;
  // Pagination props
  paginationModel?: GridPaginationModel;
  onPaginationModelChange?: (model: GridPaginationModel) => void;
  pageSizeOptions?: number[];
  // Quick filter props
  enableQuickFilter?: boolean;
  // Custom toolbar slot (overrides default CustomToolbarWithFilters when serverSideFiltering=true)
  toolbarSlot?: React.ComponentType;
  // Styling props
  disablePaperWrapper?: boolean;
  /** Hide column resize handles (enabled by default). */
  disableColumnResize?: boolean;
  /**
   * Grow the grid to fit all rows (no internal vertical scroll). Default true.
   * Set false to give the grid a fixed/flex height so its rows scroll
   * internally and the header + pagination footer stay pinned.
   */
  autoHeight?: boolean;
  // Initial state props
  initialState?: GridInitialState;
  // State persistence props
  persistState?: boolean;
  storageKey?: string;
  hideFooter?: boolean;
  /**
   * Hide rows-per-page selector when total row count is below this value.
   * Set to 0 to always show the selector. Default: 10.
   */
  hideRowsPerPageBelow?: number;
}

/**
 * Reconcile a persisted column order with the current column definitions.
 *
 * Without this, a column added to `columns` after a user already has a
 * persisted `orderedFields` is appended at the end by MUI (it isn't in the
 * saved order). This keeps the user's relative ordering for known fields while
 * slotting any brand-new field next to the neighbour it's defined after.
 */
function reconcileOrderedFields(
  persistedOrder: string[],
  columnFields: string[]
): string[] {
  const result = [...persistedOrder];
  const present = new Set(persistedOrder);

  columnFields.forEach((field, idx) => {
    if (present.has(field)) return;

    // Find the nearest preceding defined column that's already in the order.
    let insertAfter: string | null = null;
    for (let i = idx - 1; i >= 0; i--) {
      if (present.has(columnFields[i])) {
        insertAfter = columnFields[i];
        break;
      }
    }

    let insertIndex: number;
    if (insertAfter !== null) {
      insertIndex = result.indexOf(insertAfter) + 1;
    } else {
      // No preceding defined column yet — insert before the first one present
      // (keeps it after special leading fields like the selection checkbox).
      const firstPresentColField = columnFields.find(f => present.has(f));
      insertIndex = firstPresentColField
        ? result.indexOf(firstPresentColField)
        : result.length;
    }

    result.splice(insertIndex, 0, field);
    present.add(field);
  });

  return result;
}

// Create a styled version of DataGrid with Figma-aligned borders and headers
const StyledDataGrid = styled(DataGrid)(({ theme }) => ({
  border: 'none',
  // Column header: white bg, bold text, bottom divider matching Figma
  '& .MuiDataGrid-columnHeaders': {
    backgroundColor: theme.palette.background.paper,
    fontWeight: 'bold',
  },
  '& .MuiDataGrid-columnHeaderTitle': {
    fontWeight: 700,
  },
  '& .MuiDataGrid-columnHeader': {
    fontWeight: 'bold',
  },
  '& .MuiDataGrid-cell': {
    display: 'flex',
    alignItems: 'center',
    overflow: 'hidden',
    borderColor: theme.palette.greyscale.border,
  },
  // Figma: 30px horizontal inset for first/last column, aligned with the
  // toolbar and pagination footer (both use px: '30px').
  // Use MUI's own --first/--last classes for headers (reliable, avoids the
  // scrollbar-filler div that breaks :first/:last-of-type selectors).
  // Use :first-child for cells (no element precedes the first cell in a row).
  // The trailing empty filler cell gets paddingRight via :last-of-type which
  // creates the visual 30px right gap at the grid edge.
  '&& .MuiDataGrid-columnHeader--first': {
    paddingLeft: '30px',
  },
  '&& .MuiDataGrid-columnHeader--last': {
    paddingRight: '30px',
  },
  '&& .MuiDataGrid-cell:first-child': {
    paddingLeft: '30px',
  },
  '&& .MuiDataGrid-cell:last-of-type': {
    paddingRight: '30px',
  },
  '& .MuiDataGrid-cell:focus': {
    outline: 'none',
  },
  '& .MuiDataGrid-row:hover': {
    cursor: 'pointer',
    backgroundColor:
      theme.palette.mode === 'light' ? '#f7f8f9' : 'rgba(255,255,255,0.04)',
  },
  // Faint row separator above the footer
  '& .MuiDataGrid-footerContainer': {
    borderTop: `1px solid ${theme.palette.mode === 'light' ? '#cdd2da' : theme.palette.divider}`,
  },
}));

function QuickFilterToolbar() {
  return (
    <Box
      sx={{
        px: '30px',
        py: '16px',
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      <GridToolbarQuickFilter debounceMs={300} />
    </Box>
  );
}

// Column menu that only shows sort actions (no Filter, no Hide/Manage columns).
function SortOnlyColumnMenu(props: GridColumnMenuProps) {
  return (
    <GridColumnMenu
      {...props}
      slots={{
        columnMenuFilterItem: null,
        columnMenuColumnsItem: null,
      }}
    />
  );
}

// Context to pass pageSizeOptions into the DataGrid footer slot
const PaginationSizeContext = React.createContext<number[]>([10, 25, 50]);

/** When row count is below this value, hide the rows-per-page selector in the footer. */
const HideRowsPerPageBelowContext = React.createContext<number | undefined>(
  undefined
);

function FigmaPaginationFooter() {
  const theme = useTheme();
  const textColor = theme.palette.greyscale.body;
  const mutedBorderColor = theme.palette.greyscale.border;

  const apiRef = useGridApiContext();
  const paginationModel = useGridSelector(apiRef, gridPaginationModelSelector);
  const rowCount = useGridSelector(apiRef, gridRowCountSelector);
  const pageSizeOptions = React.useContext(PaginationSizeContext);
  const hideRowsPerPageBelow = React.useContext(HideRowsPerPageBelowContext);

  const { page, pageSize } = paginationModel;
  const from = rowCount === 0 ? 0 : page * pageSize + 1;
  const to = Math.min((page + 1) * pageSize, rowCount);
  const isFirst = page === 0;
  const isLast = rowCount === 0 || to >= rowCount;
  const showRowsPerPage =
    (hideRowsPerPageBelow ?? 0) <= 0 || rowCount >= (hideRowsPerPageBelow ?? 0);

  const navBtnSx = (active: boolean): SxProps<Theme> => ({
    border: '2px solid',
    borderColor: active ? 'primary.main' : mutedBorderColor,
    borderRadius: BORDER_RADIUS.sm,
    p: '9px',
    width: 38,
    height: 38,
    flexShrink: 0,
    color: active ? 'primary.main' : mutedBorderColor,
    '&.Mui-disabled': {
      borderColor: mutedBorderColor,
      color: mutedBorderColor,
      opacity: 1,
    },
    '&:hover': {
      bgcolor: active ? 'rgba(0, 128, 175, 0.06)' : 'transparent',
    },
    '& .MuiSvgIcon-root': { fontSize: 16 },
  });

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: showRowsPerPage ? 'space-between' : 'flex-end',
        px: '30px',
        py: '16px',
      }}
    >
      {showRowsPerPage ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <Typography
            sx={{
              fontSize: 12,
              fontWeight: 600,
              color: textColor,
              whiteSpace: 'nowrap',
            }}
          >
            Rows per page:
          </Typography>
          <Select
            value={pageSize}
            onChange={e =>
              apiRef.current.setPaginationModel({
                page: 0,
                pageSize: Number(e.target.value),
              })
            }
            variant="standard"
            disableUnderline
            sx={{
              fontSize: 14,
              fontWeight: 700,
              color: textColor,
              '& .MuiSelect-icon': { color: textColor },
            }}
          >
            {pageSizeOptions.map(opt => (
              <MenuItem key={opt} value={opt} sx={{ fontSize: 14 }}>
                {opt}
              </MenuItem>
            ))}
          </Select>
        </Box>
      ) : null}

      {/* Prev / range / Next */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: '30px' }}>
        <IconButton
          onClick={() =>
            apiRef.current.setPaginationModel({ page: page - 1, pageSize })
          }
          disabled={isFirst}
          aria-label="Previous page"
          sx={navBtnSx(!isFirst)}
        >
          <ArrowBackIosNewIcon />
        </IconButton>

        <Typography
          sx={{
            fontSize: 12,
            fontWeight: 600,
            color: textColor,
            whiteSpace: 'nowrap',
          }}
        >
          {from}–{to} of {rowCount}
        </Typography>

        <IconButton
          onClick={() =>
            apiRef.current.setPaginationModel({ page: page + 1, pageSize })
          }
          disabled={isLast}
          aria-label="Next page"
          sx={navBtnSx(!isLast)}
        >
          <ArrowForwardIosIcon />
        </IconButton>
      </Box>
    </Box>
  );
}

export default function BaseDataGrid({
  columns,
  rows,
  title,
  loading = false,
  getRowId,
  showToolbar: _showToolbar = true,
  onRowClick,
  density,
  sx: _sx,
  disableMultipleRowSelection,
  actionButtons,
  enableEditing = false,
  editMode = 'row',
  processRowUpdate,
  onProcessRowUpdateError,
  isCellEditable,
  checkboxSelection = false,
  disableRowSelectionOnClick,
  onRowSelectionModelChange,
  rowSelectionModel,
  isRowSelectable,
  filters,
  filterHandler,
  customToolbarContent,
  gridToolbarExtra,
  serverSideFiltering = false,
  filterModel,
  onFilterModelChange,
  sortingMode = 'client',
  sortModel,
  onSortModelChange,
  linkPath,
  linkField = 'id',
  getRowUrl,
  serverSidePagination = false,
  totalRows,
  paginationModel,
  onPaginationModelChange,
  pageSizeOptions = [10, 25, 50],
  enableQuickFilter = false,
  toolbarSlot,
  disablePaperWrapper = false,
  disableColumnResize = false,
  autoHeight = true,
  initialState,
  persistState = false,
  storageKey,
  hideFooter = false,
  hideRowsPerPageBelow = 10,
}: BaseDataGridProps) {
  const _theme = useTheme();
  const router = useRouter();
  const apiRef = useGridApiRef();

  // Grid state persistence
  const {
    initialState: persistedState,
    saveGridState,
    isLoaded: isPersistedStateLoaded,
  } = useGridStateStorage({
    storageKey,
  });

  // Merge persisted state with any passed initialState
  // IMPORTANT: Persisted state takes precedence because it represents user's explicit choices
  // The passed initialState is only used as a fallback for values not in persisted state
  const mergedInitialState = React.useMemo(() => {
    if (!persistState) return initialState;
    if (!persistedState && !initialState) return undefined;
    if (!persistedState) return initialState;
    if (!initialState) return persistedState;

    // Deep merge: initialState as base, persistedState overrides (user's saved preferences win)
    return {
      ...initialState,
      ...persistedState,
      columns: {
        ...initialState.columns,
        ...persistedState.columns,
        // Deep merge columnVisibilityModel: persisted values override initial values
        columnVisibilityModel: {
          ...initialState.columns?.columnVisibilityModel,
          ...persistedState.columns?.columnVisibilityModel,
        },
        // Deep merge orderedFields only if persisted (user reordered columns).
        // Reconcile against the current columns so a newly added column lands
        // next to its defined neighbour instead of being appended at the end.
        ...(persistedState.columns?.orderedFields && {
          orderedFields: reconcileOrderedFields(
            persistedState.columns.orderedFields,
            columns.map(col => col.field)
          ),
        }),
        // Deep merge dimensions only if persisted (user resized columns)
        ...(persistedState.columns?.dimensions && {
          dimensions: {
            ...initialState.columns?.dimensions,
            ...persistedState.columns.dimensions,
          },
        }),
      },
      sorting: {
        ...initialState.sorting,
        ...persistedState.sorting,
      },
      filter: {
        ...initialState.filter,
        ...persistedState.filter,
      },
      pagination: {
        ...initialState.pagination,
        ...persistedState.pagination,
      },
      // Density: persisted overrides initial
      ...(persistedState.density && { density: persistedState.density }),
    };
  }, [persistState, persistedState, initialState, columns]);

  // Save state callback - memoized to avoid unnecessary re-subscriptions
  const handleStateChange = useCallback(() => {
    if (persistState && apiRef.current) {
      saveGridState(apiRef);
    }
  }, [persistState, apiRef, saveGridState]);

  // Safe mounting implementation internal to the component
  const isMountedRef = useRef(false);
  const [isInitialized, setIsInitialized] = useState(false);

  // Initialization effect
  useEffect(() => {
    isMountedRef.current = true;
    // Delay DataGrid initialization to prevent state update on unmounted component
    const initTimer = setTimeout(() => {
      if (isMountedRef.current) {
        setIsInitialized(true);
      }
    }, 0);

    return () => {
      clearTimeout(initTimer);
      isMountedRef.current = false;
    };
  }, []);

  // Subscribe to state change events for persistence
  useEffect(() => {
    if (!persistState || !isInitialized || !apiRef.current) return;

    const api = apiRef.current;

    // Subscribe to relevant state change events
    const unsubscribeColumnVisibility = api.subscribeEvent(
      'columnVisibilityModelChange',
      handleStateChange
    );
    const unsubscribeColumnOrder = api.subscribeEvent(
      'columnOrderChange',
      handleStateChange
    );
    const unsubscribeColumnResize = api.subscribeEvent(
      'columnWidthChange',
      handleStateChange
    );
    const unsubscribeSortModel = api.subscribeEvent(
      'sortModelChange',
      handleStateChange
    );
    const unsubscribeFilterModel = api.subscribeEvent(
      'filterModelChange',
      handleStateChange
    );
    const unsubscribeDensity = api.subscribeEvent(
      'densityChange',
      handleStateChange
    );
    const unsubscribePagination = api.subscribeEvent(
      'paginationModelChange',
      handleStateChange
    );

    return () => {
      unsubscribeColumnVisibility();
      unsubscribeColumnOrder();
      unsubscribeColumnResize();
      unsubscribeSortModel();
      unsubscribeFilterModel();
      unsubscribeDensity();
      unsubscribePagination();
    };
  }, [persistState, isInitialized, apiRef, handleStateChange]);

  const [filterValues, setFilterValues] = useState<Record<string, string>>({});
  const [filteredRows, setFilteredRows] = useState<GridRowModel[]>(rows);

  // Create refs and state for action buttons
  const buttonRefs = React.useRef<
    Array<React.RefObject<HTMLDivElement | null>>
  >(
    Array(actionButtons?.length || 0)
      .fill(null)
      .map(() => React.createRef<HTMLDivElement | null>())
  );
  const [openStates, setOpenStates] = React.useState<boolean[]>(
    Array(actionButtons?.length || 0).fill(false)
  );

  // Initialize filter values on component mount
  useEffect(() => {
    if (filters && filters.length > 0) {
      const initialValues: Record<string, string> = {};
      filters.forEach(filter => {
        initialValues[filter.name] = filter.defaultValue;
      });
      setFilterValues(initialValues);
    }
  }, [filters]);

  // Update filtered rows when rows change
  useEffect(() => {
    if (!serverSidePagination) {
      setFilteredRows(rows);
    }
  }, [rows, serverSidePagination]);

  // Apply filters when rows or filter values change
  useEffect(() => {
    if (serverSidePagination || !filters || filters.length === 0) {
      return;
    }

    const result = rows.filter(row => {
      return filters.every(filter => {
        const currentValue = filterValues[filter.name];
        if (currentValue === 'all') return true;

        const rowValue = filter.filterField
          .split('.')
          .reduce(
            (obj: unknown, key: string) =>
              obj && typeof obj === 'object' && key in obj
                ? (obj as Record<string, unknown>)[key]
                : undefined,
            row
          );

        return rowValue === currentValue;
      });
    });

    setFilteredRows(result);

    if (filterHandler) {
      filterHandler(result);
    }
  }, [rows, filterValues, filters, filterHandler, serverSidePagination]);

  const handleFilterChange =
    (filterName: string) => (event: SelectChangeEvent<string>) => {
      setFilterValues(prev => ({
        ...prev,
        [filterName]: event.target.value,
      }));
    };

  const [contextMenu, setContextMenu] = useState<{
    mouseX: number;
    mouseY: number;
    url: string;
  } | null>(null);

  const resolveRowUrl = useCallback(
    (params: GridRowParams): string | undefined => {
      if (getRowUrl) return getRowUrl(params.row);
      if (linkPath) {
        const fieldValue = params.row[linkField];
        return fieldValue ? `${linkPath}/${fieldValue}` : undefined;
      }
      return undefined;
    },
    [getRowUrl, linkPath, linkField]
  );

  const handleRowClickWithLink = (
    params: GridRowParams,
    event: React.MouseEvent
  ) => {
    const url = resolveRowUrl(params);

    if (url && (event.metaKey || event.ctrlKey)) {
      window.open(url, '_blank', 'noopener,noreferrer');
      return;
    }

    if (onRowClick) {
      onRowClick(params);
      return;
    }

    if (url) {
      router.push(url);
    }
  };

  const handleContainerContextMenu = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const rowEl = (event.target as HTMLElement).closest(
        '[data-id]'
      ) as HTMLElement | null;
      if (!rowEl) return;

      const rowId = rowEl.dataset.id;
      if (!rowId) return;

      const row = apiRef.current.getRow(rowId);
      if (!row) return;

      const url = resolveRowUrl({ id: rowId, row } as GridRowParams);
      if (!url) return;

      event.preventDefault();
      setContextMenu({ mouseX: event.clientX, mouseY: event.clientY, url });
    },
    [resolveRowUrl, apiRef]
  );

  const handleContainerAuxClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (event.button !== 1) return;
      const rowEl = (event.target as HTMLElement).closest(
        '[data-id]'
      ) as HTMLElement | null;
      if (!rowEl) return;

      const rowId = rowEl.dataset.id;
      if (!rowId) return;

      const row = apiRef.current.getRow(rowId);
      if (!row) return;

      const url = resolveRowUrl({ id: rowId, row } as GridRowParams);
      if (!url) return;

      event.preventDefault();
      window.open(url, '_blank', 'noopener,noreferrer');
    },
    [resolveRowUrl, apiRef]
  );

  const handleToggle = (index: number) => {
    setOpenStates(prev => {
      const newStates = [...prev];
      newStates[index] = !newStates[index];
      return newStates;
    });
  };

  const handleClose = (event: Event, index: number) => {
    if (
      buttonRefs.current[index]?.current &&
      buttonRefs.current[index].current?.contains(event.target as HTMLElement)
    ) {
      return;
    }
    setOpenStates(prev => {
      const newStates = [...prev];
      newStates[index] = false;
      return newStates;
    });
  };

  const handleMenuItemClick = (onClick: () => void, index: number) => {
    onClick();
    setOpenStates(prev => {
      const newStates = [...prev];
      newStates[index] = false;
      return newStates;
    });
  };

  // Refs for server-side filtering with stable toolbar
  // Using uncontrolled input to avoid re-render/focus issues
  const quickFilterInputRef = useRef<HTMLInputElement | null>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const onFilterModelChangeRef = useRef(onFilterModelChange);
  const filterModelRef = useRef(filterModel);
  const gridToolbarExtraRef = useRef(gridToolbarExtra);

  // Keep callback refs up to date without causing re-renders
  useEffect(() => {
    onFilterModelChangeRef.current = onFilterModelChange;
    filterModelRef.current = filterModel;
    gridToolbarExtraRef.current = gridToolbarExtra;
  });

  // Sync input value with external filterModel changes (e.g., "Clear All Filters")
  useEffect(() => {
    if (!filterModel || !quickFilterInputRef.current) return;

    const quickFilterItem = filterModel.items.find(
      item => item.field === 'quickFilter' || item.field === '__quickFilter__'
    );
    const newValue = quickFilterItem?.value || '';

    // Only update if different and not during active typing (debounce in progress)
    if (
      quickFilterInputRef.current.value !== newValue &&
      !debounceTimerRef.current
    ) {
      quickFilterInputRef.current.value = newValue;
    }
  }, [filterModel]);

  /**
   * Handles quick filter input changes with debouncing.
   * Updates the filter model after 300ms of inactivity.
   */
  const handleQuickFilterChange = useCallback(() => {
    const value = quickFilterInputRef.current?.value || '';

    // Clear existing debounce timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Debounced filter model update
    debounceTimerRef.current = setTimeout(() => {
      debounceTimerRef.current = null;

      if (onFilterModelChangeRef.current && filterModelRef.current) {
        const otherFilters = filterModelRef.current.items.filter(
          item =>
            item.field !== 'quickFilter' && item.field !== '__quickFilter__'
        );

        const newFilterModel = {
          ...filterModelRef.current,
          items: value
            ? [
                ...otherFilters,
                { field: 'quickFilter', operator: 'contains', value },
              ]
            : otherFilters,
        };

        onFilterModelChangeRef.current(newFilterModel);
      }
    }, 300);
  }, []);

  /**
   * Clears the quick filter input and updates the filter model immediately.
   */
  const handleQuickFilterClear = useCallback(() => {
    if (quickFilterInputRef.current) {
      quickFilterInputRef.current.value = '';
    }

    // Clear any pending debounce
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    // Immediately update filter model
    if (onFilterModelChangeRef.current && filterModelRef.current) {
      const otherFilters = filterModelRef.current.items.filter(
        item => item.field !== 'quickFilter' && item.field !== '__quickFilter__'
      );
      onFilterModelChangeRef.current({
        ...filterModelRef.current,
        items: otherFilters,
      });
    }
  }, []);

  /**
   * Stable toolbar component using uncontrolled input.
   * Created once and stored in ref to prevent remounting and focus loss.
   * The input manages its own value via DOM, avoiding React state/re-render complexity.
   */
  const CustomToolbarWithFiltersRef =
    useRef<React.JSXElementConstructor<GridToolbarProps> | null>(null);
  if (!CustomToolbarWithFiltersRef.current) {
    CustomToolbarWithFiltersRef.current = function CustomToolbar() {
      return (
        <Box
          sx={{
            px: '30px',
            py: '16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <GridToolbar />
            {gridToolbarExtraRef.current}
          </Box>
          <TextField
            inputRef={quickFilterInputRef}
            size="small"
            placeholder="Search..."
            defaultValue=""
            onChange={handleQuickFilterChange}
            sx={{ minWidth: 250 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    size="small"
                    onClick={handleQuickFilterClear}
                    aria-label="Clear search"
                  >
                    <ClearIcon fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </Box>
      );
    };
  }
  const CustomToolbarWithFilters = CustomToolbarWithFiltersRef.current;

  // Wait for initialization and persisted state to be loaded before rendering DataGrid
  // This ensures initialState is correctly set before the grid mounts
  const isReady = isInitialized && (!persistState || isPersistedStateLoaded);

  if (!isReady) {
    return (
      <Box
        sx={{ width: '100%', display: 'flex', justifyContent: 'center', p: 4 }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Consolidated slots — computed once, used in both DataGrid render paths
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const resolvedSlots: Record<string, React.ComponentType<any>> = {
    columnMenu: SortOnlyColumnMenu,
  };
  if (!hideFooter) {
    resolvedSlots.footer = FigmaPaginationFooter;
  }
  if (toolbarSlot) {
    resolvedSlots.toolbar = toolbarSlot;
  } else if (serverSideFiltering) {
    resolvedSlots.toolbar = CustomToolbarWithFilters;
  } else if (enableQuickFilter) {
    resolvedSlots.toolbar = QuickFilterToolbar;
  }

  const dataGridSx: SxProps<Theme> = [
    disableColumnResize && {
      '& .MuiDataGrid-columnSeparator': {
        display: 'none',
      },
    },
    _sx,
  ].filter(Boolean) as SxProps<Theme>;

  const hasHeaderContent = !!(
    title ||
    (filters && filters.length > 0) ||
    (actionButtons && actionButtons.length > 0) ||
    customToolbarContent
  );

  const hasRowUrl = !!(getRowUrl || linkPath);

  return (
    <>
      {hasHeaderContent && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'flex-start',
            alignItems: 'center',
            mb: 2,
            gap: 2,
          }}
        >
          {title && (
            <Typography variant="h6" component="h1">
              {title}
            </Typography>
          )}

          {filters && filters.length > 0 && (
            <Box sx={{ display: 'flex', gap: 2 }}>
              {filters.map(filter => (
                <FormControl
                  key={filter.name}
                  variant="outlined"
                  size="small"
                  sx={{ minWidth: 150 }}
                >
                  <InputLabel id={`${filter.name}-label`}>
                    {filter.label}
                  </InputLabel>
                  <Select
                    labelId={`${filter.name}-label`}
                    id={filter.name}
                    value={filterValues[filter.name] || filter.defaultValue}
                    onChange={handleFilterChange(filter.name)}
                    label={filter.label}
                  >
                    {filter.options.map(option => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              ))}
            </Box>
          )}

          {actionButtons && actionButtons.length > 0 && (
            <Box sx={{ display: 'flex', gap: 1 }}>
              {actionButtons.map((button, index) => {
                if (button.splitButton) {
                  const options = button.splitButton.options; // Extract options to satisfy TypeScript
                  return (
                    <React.Fragment key={button.label}>
                      <ButtonGroup
                        variant={button.variant || 'contained'}
                        color={button.color || 'primary'}
                        ref={buttonRefs.current[index]}
                        aria-label="split button"
                        disabled={button.disabled}
                      >
                        <Button
                          onClick={button.onClick}
                          startIcon={button.icon}
                          disabled={button.disabled}
                        >
                          {button.label}
                        </Button>
                        <Button
                          size="small"
                          aria-controls={
                            openStates[index] ? 'split-button-menu' : undefined
                          }
                          aria-expanded={openStates[index] ? 'true' : undefined}
                          aria-label="select option"
                          aria-haspopup="menu"
                          onClick={() => handleToggle(index)}
                          disabled={button.disabled}
                        >
                          <ArrowDropDownIcon />
                        </Button>
                      </ButtonGroup>
                      <Popper
                        sx={{
                          zIndex: 1,
                        }}
                        open={openStates[index]}
                        anchorEl={buttonRefs.current[index].current}
                        role={undefined}
                        transition
                        disablePortal
                      >
                        {({ TransitionProps, placement }) => (
                          <Grow
                            {...TransitionProps}
                            style={{
                              transformOrigin:
                                placement === 'bottom'
                                  ? 'center top'
                                  : 'center bottom',
                            }}
                          >
                            <Paper>
                              <ClickAwayListener
                                onClickAway={event => handleClose(event, index)}
                              >
                                <MenuList id="split-button-menu" autoFocusItem>
                                  {options.map(option => (
                                    <MenuItem
                                      key={option.label}
                                      disabled={option.disabled}
                                      onClick={() =>
                                        handleMenuItemClick(
                                          option.onClick,
                                          index
                                        )
                                      }
                                    >
                                      {option.label}
                                    </MenuItem>
                                  ))}
                                </MenuList>
                              </ClickAwayListener>
                            </Paper>
                          </Grow>
                        )}
                      </Popper>
                    </React.Fragment>
                  );
                }

                return button.href ? (
                  <Link
                    key={button.label}
                    href={button.href}
                    style={{ textDecoration: 'none' }}
                  >
                    <Button
                      variant={button.variant || 'contained'}
                      color={button.color || 'primary'}
                      startIcon={button.icon}
                      data-tour={button.dataTour}
                      disabled={button.disabled}
                    >
                      {button.label}
                    </Button>
                  </Link>
                ) : (
                  <Button
                    key={button.label}
                    variant={button.variant || 'contained'}
                    color={button.color || 'primary'}
                    onClick={button.onClick}
                    startIcon={button.icon}
                    data-tour={button.dataTour}
                    disabled={button.disabled}
                  >
                    {button.label}
                  </Button>
                );
              })}
            </Box>
          )}
          {customToolbarContent}
        </Box>
      )}

      <Box
        onContextMenu={hasRowUrl ? handleContainerContextMenu : undefined}
        onAuxClick={hasRowUrl ? handleContainerAuxClick : undefined}
      >
        {disablePaperWrapper ? (
          <HideRowsPerPageBelowContext.Provider value={hideRowsPerPageBelow}>
            <PaginationSizeContext.Provider value={pageSizeOptions}>
              <StyledDataGrid
                apiRef={apiRef}
                rows={serverSidePagination ? rows : filteredRows}
                columns={columns}
                getRowId={getRowId}
                {...(autoHeight && { autoHeight: true })}
                pagination
                hideFooter={hideFooter}
                paginationMode={serverSidePagination ? 'server' : 'client'}
                rowCount={serverSidePagination ? totalRows : undefined}
                paginationModel={paginationModel}
                onPaginationModelChange={onPaginationModelChange}
                pageSizeOptions={pageSizeOptions}
                checkboxSelection={checkboxSelection}
                disableVirtualization={false}
                loading={loading}
                slots={resolvedSlots}
                sx={dataGridSx}
                onRowClick={
                  enableEditing
                    ? undefined
                    : hasRowUrl || onRowClick
                      ? handleRowClickWithLink
                      : undefined
                }
                disableMultipleRowSelection={disableMultipleRowSelection}
                {...(density && { density })}
                {...(mergedInitialState && {
                  initialState: mergedInitialState,
                })}
                {...(serverSideFiltering && {
                  filterMode: 'server',
                  filterModel,
                  onFilterModelChange,
                })}
                {...(sortingMode === 'server' && {
                  sortingMode: 'server',
                  sortModel,
                  onSortModelChange,
                })}
                {...(enableEditing && {
                  editMode,
                  processRowUpdate,
                  onProcessRowUpdateError,
                  isCellEditable,
                })}
                {...(onRowSelectionModelChange && {
                  onRowSelectionModelChange,
                })}
                {...(rowSelectionModel !== undefined && {
                  rowSelectionModel,
                })}
                {...(isRowSelectable && { isRowSelectable })}
                {...(disableRowSelectionOnClick && {
                  disableRowSelectionOnClick,
                })}
              />
            </PaginationSizeContext.Provider>
          </HideRowsPerPageBelowContext.Provider>
        ) : (
          <Paper
            elevation={0}
            sx={{
              width: '100%',
              borderRadius: BORDER_RADIUS.md,
              border: theme => `1px solid ${theme.palette.greyscale.border}`,
              boxShadow: ELEVATION.xs,
              overflow: 'hidden',
            }}
          >
            <HideRowsPerPageBelowContext.Provider value={hideRowsPerPageBelow}>
              <PaginationSizeContext.Provider value={pageSizeOptions}>
                <StyledDataGrid
                  apiRef={apiRef}
                  rows={serverSidePagination ? rows : filteredRows}
                  columns={columns}
                  getRowId={getRowId}
                  {...(autoHeight && { autoHeight: true })}
                  pagination
                  hideFooter={hideFooter}
                  paginationMode={serverSidePagination ? 'server' : 'client'}
                  rowCount={serverSidePagination ? totalRows : undefined}
                  paginationModel={paginationModel}
                  onPaginationModelChange={onPaginationModelChange}
                  pageSizeOptions={pageSizeOptions}
                  checkboxSelection={checkboxSelection}
                  disableVirtualization={false}
                  loading={loading}
                  slots={resolvedSlots}
                  sx={dataGridSx}
                  onRowClick={
                    enableEditing
                      ? undefined
                      : hasRowUrl || onRowClick
                        ? handleRowClickWithLink
                        : undefined
                  }
                  disableMultipleRowSelection={disableMultipleRowSelection}
                  {...(density && { density })}
                  {...(mergedInitialState && {
                    initialState: mergedInitialState,
                  })}
                  {...(serverSideFiltering && {
                    filterMode: 'server',
                    filterModel,
                    onFilterModelChange,
                  })}
                  {...(sortingMode === 'server' && {
                    sortingMode: 'server',
                    sortModel,
                    onSortModelChange,
                  })}
                  {...(enableEditing && {
                    editMode,
                    processRowUpdate,
                    onProcessRowUpdateError,
                    isCellEditable,
                  })}
                  {...(onRowSelectionModelChange && {
                    onRowSelectionModelChange,
                  })}
                  {...(rowSelectionModel !== undefined && {
                    rowSelectionModel,
                  })}
                  {...(disableRowSelectionOnClick && {
                    disableRowSelectionOnClick,
                  })}
                />
              </PaginationSizeContext.Provider>
            </HideRowsPerPageBelowContext.Provider>
          </Paper>
        )}
      </Box>

      <Menu
        open={contextMenu !== null}
        onClose={() => setContextMenu(null)}
        anchorReference="anchorPosition"
        anchorPosition={
          contextMenu !== null
            ? { top: contextMenu.mouseY, left: contextMenu.mouseX }
            : undefined
        }
      >
        <MenuItem
          onClick={() => {
            if (contextMenu) {
              window.open(contextMenu.url, '_blank', 'noopener,noreferrer');
            }
            setContextMenu(null);
          }}
          sx={{ gap: 1 }}
        >
          <OpenInNewIcon fontSize="small" />
          Open in new tab
        </MenuItem>
      </Menu>
    </>
  );
}

export type { FilterOption, FilterConfig };
