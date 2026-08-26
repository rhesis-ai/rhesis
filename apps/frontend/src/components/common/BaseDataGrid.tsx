import React, {
  useState,
  useEffect,
  useLayoutEffect,
  useCallback,
  useRef,
} from 'react';
import {
  Box,
  Typography,
  Paper,
  styled,
  useTheme,
  Select,
  MenuItem,
  CircularProgress,
  Menu,
  alpha,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import IconButton from '@mui/material/IconButton';
import {
  DataGrid,
  GridColDef,
  GridPaginationModel,
  GridRowModel,
  GridDensity,
  GridRowSelectionModel,
  useGridApiRef,
  useGridApiContext,
  useGridSelector,
  gridPaginationModelSelector,
  gridRowCountSelector,
  GridSortModel,
  GridInitialState,
  GridRowParams,
  GridColumnMenu,
  type GridColumnGroupingModel,
  type GridColumnMenuProps,
} from '@mui/x-data-grid';
import type { SxProps, Theme } from '@mui/material/styles';
import { useRouter } from 'next/navigation';
import ArrowBackIosNewIcon from '@mui/icons-material/ArrowBackIosNew';
import ArrowForwardIosIcon from '@mui/icons-material/ArrowForwardIos';
import { useGridStateStorage } from '@/hooks/useGridStateStorage';
import {
  RowActionsHoverProvider,
  useRowActionsGridRootProps,
} from '@/components/common/createRowActionsColumn';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { HIGHLIGHTED_ROW_CLASS } from '@/constants/notifications';

/**
 * Shared "grid card" look — the bordered, rounded, shadowed Paper every grid
 * page wraps its toolbar + DataGrid (+ alerts, selection banners, etc.) in.
 * Exported so grid components that need more inside the card than just the
 * DataGrid (and so pass `disablePaperWrapper`) can reuse the exact same sx
 * instead of re-declaring it.
 */
export const GRID_PAPER_SX = {
  width: '100%',
  borderRadius: BORDER_RADIUS.md,
  boxShadow: ELEVATION.xs,
  border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
  overflow: 'hidden',
} as const;

interface BaseDataGridProps {
  columns: GridColDef[];
  /** Header groups spanning several columns, e.g. to separate a case from a run. */
  columnGroupingModel?: GridColumnGroupingModel;
  rows: GridRowModel[];
  loading?: boolean;
  getRowId?: (row: GridRowModel) => string | number;
  onRowClick?: (params: GridRowParams) => void;
  /** Per-row extra CSS class, e.g. to gently highlight a row with an unseen notification. */
  getRowClassName?: (params: GridRowParams) => string;
  density?: GridDensity;
  sx?: SxProps<Theme>;
  disableMultipleRowSelection?: boolean;
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
  // Custom toolbar slot rendered inside the DataGrid (receives no props — read context)
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
  const columnFieldSet = new Set(columnFields);
  const present = new Set(
    persistedOrder.filter(field => columnFieldSet.has(field))
  );
  let result = persistedOrder.filter(field => columnFieldSet.has(field));

  // Insert columns that are not in the persisted order yet.
  columnFields.forEach((field, idx) => {
    if (present.has(field)) return;

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
      const firstPresentColField = columnFields.find(f => present.has(f));
      insertIndex = firstPresentColField
        ? result.indexOf(firstPresentColField)
        : result.length;
    }

    result.splice(insertIndex, 0, field);
    present.add(field);
  });

  // Actions must stay trailing — hover styles and column virtualization assume it.
  if (columnFields.includes('actions')) {
    result = result.filter(field => field !== 'actions');
    result.push('actions');
  }

  return result;
}

function RowActionsHoverGrid({
  enabled,
  children,
}: {
  enabled: boolean;
  children: (rowActionsRootProps?: {
    onMouseMove: (event: React.MouseEvent) => void;
    onMouseLeave: () => void;
  }) => React.ReactNode;
}) {
  if (!enabled) {
    return <>{children(undefined)}</>;
  }

  return (
    <RowActionsHoverProvider>
      <RowActionsHoverGridInner>{children}</RowActionsHoverGridInner>
    </RowActionsHoverProvider>
  );
}

function RowActionsHoverGridInner({
  children,
}: {
  children: (rowActionsRootProps: {
    onMouseMove: (event: React.MouseEvent) => void;
    onMouseLeave: () => void;
  }) => React.ReactNode;
}) {
  const rowActionsRootProps = useRowActionsGridRootProps();
  return <>{children(rowActionsRootProps)}</>;
}

/** Fields that stay at a fixed width while other columns grow to fill the grid. */
const FIXED_WIDTH_COLUMN_FIELDS = new Set(['actions']);

function isFixedWidthColumn(col: GridColDef): boolean {
  const field = String(col.field);
  return (
    FIXED_WIDTH_COLUMN_FIELDS.has(field) ||
    field.startsWith('__') ||
    col.flex === 0
  );
}

/**
 * Normalize column sizing for BaseDataGrid.
 * - Explicit `flex` columns grow proportionally.
 * - `width` without `flex` is treated as a fixed cap (`maxWidth`).
 * - Unsized columns receive `flex: 1` to absorb remaining grid width.
 */
export function applyFlexColumnSizing(columns: GridColDef[]): GridColDef[] {
  return columns.map(col => {
    const field = String(col.field);
    const normalized =
      field === 'actions' ? { ...col, hideable: false } : { ...col };

    if (isFixedWidthColumn(normalized) || normalized.flex != null) {
      return normalized;
    }

    if (normalized.maxWidth != null) {
      return normalized;
    }

    if (normalized.width != null) {
      return {
        ...normalized,
        maxWidth: normalized.width,
      };
    }

    return {
      ...normalized,
      flex: 1,
      minWidth: normalized.minWidth ?? 50,
    };
  });
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
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  '& .MuiDataGrid-columnHeader': {
    fontWeight: 'bold',
  },
  // Right-align header titles for numeric columns to match cell alignment
  '& .MuiDataGrid-columnHeader--alignRight .MuiDataGrid-columnHeaderTitle': {
    textAlign: 'right',
    width: '100%',
  },
  '& .MuiDataGrid-cell': {
    display: 'flex',
    alignItems: 'center',
    overflow: 'hidden',
    borderColor: theme.palette.greyscale.border,
  },
  // Clip typography in cells — avoids breaking chip/stack renderers (I1)
  '& .MuiDataGrid-cell .MuiTypography-root': {
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    maxWidth: '100%',
  },
  // Numeric cells right-align by default (MUI sets align="right" on type:"number")
  '& .MuiDataGrid-cell--textRight': {
    justifyContent: 'flex-end',
  },
  // Figma: 30px horizontal inset for first/last column, aligned with the
  // toolbar and pagination footer (both use px: '30px').
  // Use MUI's own --first/--last classes for headers (reliable, avoids the
  // scrollbar-filler div that breaks :first/:last-of-type selectors).
  // Use :first-child for cells (no element precedes the first cell in a row).
  // The trailing empty filler cell gets paddingRight via :last-of-type which
  // creates the visual 30px right gap at the grid edge.
  '&& .MuiDataGrid-columnHeader--first': {
    paddingLeft: theme.spacing(3.75),
  },
  '&& .MuiDataGrid-columnHeader--last': {
    paddingRight: theme.spacing(3.75),
  },
  '&& .MuiDataGrid-cell:first-child': {
    paddingLeft: theme.spacing(3.75),
  },
  '&& .MuiDataGrid-cell:last-of-type': {
    paddingRight: theme.spacing(3.75),
  },
  // Hide the trailing filler column once flex columns consume the full width.
  '& .MuiDataGrid-filler': {
    maxWidth: 0,
    minWidth: 0,
    padding: 0,
    border: 'none',
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
  '& .MuiDataGrid-checkboxInput': {
    color: theme.palette.primary.main,
    '&.Mui-checked, &.MuiCheckbox-indeterminate': {
      color: theme.palette.primary.main,
    },
  },
}));

// Column menu that only shows sort actions (no Filter, no Hide/Manage columns).
function SortOnlyColumnMenu(props: GridColumnMenuProps) {
  if (props.colDef?.sortable === false) {
    return null;
  }

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
  columnGroupingModel,
  rows,
  loading = false,
  getRowId,
  onRowClick,
  getRowClassName,
  density,
  sx: _sx,
  disableMultipleRowSelection,
  checkboxSelection = false,
  disableRowSelectionOnClick,
  onRowSelectionModelChange,
  rowSelectionModel,
  isRowSelectable,
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
  const theme = useTheme();
  const router = useRouter();
  const apiRef = useGridApiRef();

  const gridColumns = React.useMemo(
    () => applyFlexColumnSizing(columns),
    [columns]
  );

  const hasActionsColumn = gridColumns.some(col => col.field === 'actions');

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
          ...(hasActionsColumn && { actions: true }),
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
  }, [persistState, persistedState, initialState, columns, hasActionsColumn]);

  // Save state callback - memoized to avoid unnecessary re-subscriptions
  const handleStateChange = useCallback(() => {
    if (persistState && apiRef.current) {
      saveGridState(apiRef);
    }
  }, [persistState, apiRef, saveGridState]);

  // Safe mounting implementation internal to the component
  const isMountedRef = useRef(false);
  const [isInitialized, setIsInitialized] = useState(false);

  // Initialization effect — runs before paint (useLayoutEffect) so the
  // ready-gate below never actually reaches the screen on a normal mount;
  // a setTimeout(0)-delayed useEffect would let the browser paint the
  // fallback spinner first, then swap to the grid, causing a visible flash.
  useLayoutEffect(() => {
    isMountedRef.current = true;
    setIsInitialized(true);

    return () => {
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
    event?: React.MouseEvent
  ) => {
    const url = resolveRowUrl(params);

    if (url && event && (event.metaKey || event.ctrlKey)) {
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
  }

  const dataGridSx: SxProps<Theme> = [
    disableColumnResize && {
      '& .MuiDataGrid-columnSeparator': {
        display: 'none',
      },
    },
    {
      [`& .${HIGHLIGHTED_ROW_CLASS}`]: {
        backgroundColor: alpha(theme.palette.primary.main, 0.08),
        transition: 'background-color 0.3s ease',
      },
      [`& .${HIGHLIGHTED_ROW_CLASS}:hover`]: {
        backgroundColor: alpha(theme.palette.primary.main, 0.14),
      },
    },
    ...(Array.isArray(_sx) ? _sx : _sx ? [_sx] : []),
  ].filter(Boolean) as SxProps<Theme>;

  const hasRowUrl = !!(getRowUrl || linkPath);

  return (
    <>
      <RowActionsHoverGrid enabled={hasActionsColumn}>
        {rowActionsRootProps => {
          const grid = (
            <HideRowsPerPageBelowContext.Provider value={hideRowsPerPageBelow}>
              <PaginationSizeContext.Provider value={pageSizeOptions}>
                <StyledDataGrid
                  apiRef={apiRef}
                  rows={rows}
                  columns={gridColumns}
                  {...(columnGroupingModel && { columnGroupingModel })}
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
                  {...(checkboxSelection && {
                    slotProps: {
                      baseCheckbox: { color: 'primary' as const },
                    },
                  })}
                  disableVirtualization={false}
                  {...(hasActionsColumn && { columnBufferPx: 500 })}
                  loading={loading}
                  slots={resolvedSlots}
                  sx={dataGridSx}
                  onRowClick={
                    hasRowUrl || onRowClick ? handleRowClickWithLink : undefined
                  }
                  disableMultipleRowSelection={disableMultipleRowSelection}
                  {...(density && { density })}
                  {...(mergedInitialState && {
                    initialState: mergedInitialState,
                  })}
                  {...(sortingMode === 'server' && {
                    sortingMode: 'server',
                    sortModel,
                    onSortModelChange,
                  })}
                  {...(onRowSelectionModelChange && {
                    onRowSelectionModelChange,
                  })}
                  {...(rowSelectionModel !== undefined && {
                    rowSelectionModel,
                  })}
                  {...(isRowSelectable && { isRowSelectable })}
                  {...(getRowClassName && { getRowClassName })}
                  {...(disableRowSelectionOnClick && {
                    disableRowSelectionOnClick,
                  })}
                />
              </PaginationSizeContext.Provider>
            </HideRowsPerPageBelowContext.Provider>
          );

          return (
            <Box
              onContextMenu={hasRowUrl ? handleContainerContextMenu : undefined}
              onAuxClick={hasRowUrl ? handleContainerAuxClick : undefined}
              {...rowActionsRootProps}
            >
              {disablePaperWrapper ? (
                grid
              ) : (
                <Paper elevation={0} sx={GRID_PAPER_SX}>
                  {grid}
                </Paper>
              )}
            </Box>
          );
        }}
      </RowActionsHoverGrid>

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
