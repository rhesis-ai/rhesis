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
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import TuneIcon from '@mui/icons-material/Tune';
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
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
  GridToolbarFilterButton,
  useGridApiContext,
  useGridApiRef,
  GridFilterModel,
  GridSortModel,
  GridInitialState,
  GridRowParams,
  GridCellParams,
} from '@mui/x-data-grid';
import type { SxProps, Theme } from '@mui/material/styles';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { useGridStateStorage } from '@/hooks/useGridStateStorage';

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
  // Filter related props
  filters?: FilterConfig[];
  filterHandler?: (filteredRows: GridRowModel[]) => void;
  customToolbarContent?: ReactNode;
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
  // Server-side pagination props
  serverSidePagination?: boolean;
  totalRows?: number;
  // Pagination props
  paginationModel?: GridPaginationModel;
  onPaginationModelChange?: (model: GridPaginationModel) => void;
  pageSizeOptions?: number[];
  // Quick filter props
  enableQuickFilter?: boolean;
  // Styling props
  disablePaperWrapper?: boolean;
  // Initial state props
  initialState?: GridInitialState;
  // State persistence props
  persistState?: boolean;
  storageKey?: string;
}

// Create a styled version of DataGrid with bold headers
const StyledDataGrid = styled(DataGrid)(({ theme }) => ({
  '& .MuiDataGrid-columnHeaders': {
    backgroundColor: 'rgba(0, 0, 0, 0.04)',
    fontWeight: 'bold',
  },
  '& .MuiDataGrid-columnHeaderTitle': {
    fontWeight: 800,
  },
  '& .MuiDataGrid-columnHeader': {
    fontWeight: 'bold',
  },
  '& .MuiDataGrid-cell:focus': {
    outline: 'none',
  },
  '& .MuiDataGrid-row:hover': {
    cursor: 'pointer',
    backgroundColor: 'rgba(0, 0, 0, 0.04)',
  },
  '& .MuiDataGrid-cell': {
    display: 'flex',
    alignItems: 'center',
    overflow: 'hidden',
  },
  border: 'none',

  '& .MuiDataGrid-footerContainer': {
    borderTop: 'none',
    padding: '12px 20px',
  },
  '& .MuiTablePagination-root': {
    overflow: 'visible',
  },
  '& .MuiTablePagination-toolbar': {
    padding: 0,
    minHeight: 'auto',
  },
  '& .MuiTablePagination-selectLabel': {
    fontSize: 12,
    fontWeight: 600,
    color: theme.palette.text.secondary,
    margin: 0,
  },
  '& .MuiTablePagination-select': {
    fontSize: 14,
    fontWeight: 700,
    color: theme.palette.text.secondary,
    paddingRight: 24,
  },
  '& .MuiTablePagination-displayedRows': {
    fontSize: 12,
    fontWeight: 600,
    color: theme.palette.text.secondary,
    margin: 0,
  },
  '& .MuiTablePagination-actions': {
    marginLeft: 30,
    display: 'flex',
    gap: 30,
    '& .MuiIconButton-root': {
      border: '2px solid',
      borderColor: theme.palette.grey[300],
      borderRadius: 8,
      padding: 9,
      width: 38,
      height: 38,
      '&:hover': {
        borderColor: theme.palette.primary.main,
        backgroundColor: 'transparent',
      },
      '&.Mui-disabled': {
        borderColor: theme.palette.grey[300],
        opacity: 0.5,
      },
      '& .MuiSvgIcon-root': {
        fontSize: 20,
      },
    },
    '& .MuiIconButton-root:last-of-type': {
      borderColor: theme.palette.primary.main,
    },
  },
}));

function QuickFilterToolbar() {
  return (
    <Box sx={{ p: 1, display: 'flex', justifyContent: 'flex-end' }}>
      <GridToolbarQuickFilter debounceMs={300} />
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
  filters,
  filterHandler,
  customToolbarContent,
  serverSideFiltering = false,
  filterModel,
  onFilterModelChange,
  sortingMode = 'client',
  sortModel,
  onSortModelChange,
  linkPath,
  linkField = 'id',
  serverSidePagination = false,
  totalRows,
  paginationModel,
  onPaginationModelChange,
  pageSizeOptions = [10, 25, 50],
  enableQuickFilter = false,
  disablePaperWrapper = false,
  initialState,
  persistState = false,
  storageKey,
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
        // Deep merge orderedFields only if persisted (user reordered columns)
        ...(persistedState.columns?.orderedFields && {
          orderedFields: persistedState.columns.orderedFields,
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
  }, [persistState, persistedState, initialState]);

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

  const handleRowClickWithLink = (params: GridRowParams) => {
    if (onRowClick) {
      onRowClick(params);
      return;
    }

    if (linkPath) {
      const fieldValue = params.row[linkField];
      if (fieldValue) {
        router.push(`${linkPath}/${fieldValue}`);
      }
    }
  };

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

  // Keep callback refs up to date without causing re-renders
  useEffect(() => {
    onFilterModelChangeRef.current = onFilterModelChange;
    filterModelRef.current = filterModel;
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
  const CustomToolbarWithFiltersRef = useRef<React.ComponentType | null>(null);
  if (!CustomToolbarWithFiltersRef.current) {
    CustomToolbarWithFiltersRef.current = function CustomToolbar() {
      const apiRef = useGridApiContext();
      return (
        <Box
          sx={{
            px: 2.5,
            py: 1.5,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          {/* Left: filter button + pill search */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
            <IconButton
              onClick={() => apiRef.current.showFilterPanel()}
              sx={{
                width: 38,
                height: 38,
                bgcolor: 'primary.main',
                color: '#fff',
                borderRadius: 1,
                '&:hover': { bgcolor: 'primary.dark' },
              }}
            >
              <TuneIcon sx={{ fontSize: 20 }} />
            </IconButton>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                bgcolor: 'grey.100',
                borderRadius: '30px',
                height: 38,
                width: 288,
                pl: 2,
                pr: 0.5,
              }}
            >
              <TextField
                inputRef={quickFilterInputRef}
                variant="standard"
                placeholder="Search..."
                defaultValue=""
                onChange={handleQuickFilterChange}
                sx={{ flex: 1 }}
                InputProps={{
                  disableUnderline: true,
                  sx: {
                    fontSize: 14,
                    '& input::placeholder': {
                      color: 'grey.400',
                      opacity: 1,
                    },
                  },
                  endAdornment: quickFilterInputRef.current?.value ? (
                    <InputAdornment position="end">
                      <IconButton
                        size="small"
                        onClick={handleQuickFilterClear}
                        aria-label="Clear search"
                      >
                        <ClearIcon sx={{ fontSize: 16 }} />
                      </IconButton>
                    </InputAdornment>
                  ) : null,
                }}
              />
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: 'primary.main',
                  borderRadius: '50%',
                  width: 30,
                  height: 30,
                  flexShrink: 0,
                  cursor: 'pointer',
                }}
              >
                <SearchIcon sx={{ fontSize: 18, color: '#fff' }} />
              </Box>
            </Box>
          </Box>

          {/* Right: Columns, Density, Export */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              '& .MuiButton-root': {
                color: 'primary.main',
                fontSize: 14,
                fontWeight: 400,
                textTransform: 'none',
                px: 2,
                py: 1,
                borderRadius: 1,
                '& .MuiButton-startIcon': {
                  '& .MuiSvgIcon-root': { fontSize: 20 },
                },
              },
            }}
          >
            <GridToolbarColumnsButton />
            <GridToolbarDensitySelector />
            <GridToolbarExport />
          </Box>
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

  return (
    <>
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
                                      handleMenuItemClick(option.onClick, index)
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

      {disablePaperWrapper ? (
        <StyledDataGrid
          apiRef={apiRef}
          rows={serverSidePagination ? rows : filteredRows}
          columns={columns}
          getRowId={getRowId}
          autoHeight
          pagination
          paginationMode={serverSidePagination ? 'server' : 'client'}
          rowCount={serverSidePagination ? totalRows : undefined}
          paginationModel={paginationModel}
          onPaginationModelChange={onPaginationModelChange}
          pageSizeOptions={pageSizeOptions}
          checkboxSelection={checkboxSelection}
          disableVirtualization={false}
          loading={loading}
          onRowClick={
            enableEditing
              ? undefined
              : linkPath || onRowClick
                ? handleRowClickWithLink
                : undefined
          }
          disableMultipleRowSelection={disableMultipleRowSelection}
          {...(density && { density })}
          {...(mergedInitialState && { initialState: mergedInitialState })}
          {...(serverSideFiltering && {
            filterMode: 'server',
            filterModel,
            onFilterModelChange,
            slots: { toolbar: CustomToolbarWithFilters },
          })}
          {...(sortingMode === 'server' && {
            sortingMode: 'server',
            sortModel,
            onSortModelChange,
          })}
          {...(enableQuickFilter &&
            !serverSideFiltering && {
              slots: { toolbar: QuickFilterToolbar },
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
      ) : (
        <Paper
          elevation={1}
          sx={{
            width: '100%',
            borderRadius: theme => theme.shape.borderRadius * 0.5,
            overflow: 'hidden',
          }}
        >
          <StyledDataGrid
            apiRef={apiRef}
            rows={serverSidePagination ? rows : filteredRows}
            columns={columns}
            getRowId={getRowId}
            autoHeight
            pagination
            paginationMode={serverSidePagination ? 'server' : 'client'}
            rowCount={serverSidePagination ? totalRows : undefined}
            paginationModel={paginationModel}
            onPaginationModelChange={onPaginationModelChange}
            pageSizeOptions={pageSizeOptions}
            checkboxSelection={checkboxSelection}
            disableVirtualization={false}
            loading={loading}
            onRowClick={
              enableEditing
                ? undefined
                : linkPath || onRowClick
                  ? handleRowClickWithLink
                  : undefined
            }
            disableMultipleRowSelection={disableMultipleRowSelection}
            {...(density && { density })}
            {...(mergedInitialState && { initialState: mergedInitialState })}
            {...(serverSideFiltering && {
              filterMode: 'server',
              filterModel,
              onFilterModelChange,
              slots: { toolbar: CustomToolbarWithFilters },
            })}
            {...(sortingMode === 'server' && {
              sortingMode: 'server',
              sortModel,
              onSortModelChange,
            })}
            {...(enableQuickFilter &&
              !serverSideFiltering && {
                slots: { toolbar: QuickFilterToolbar },
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
        </Paper>
      )}
    </>
  );
}

export type { FilterOption, FilterConfig };
