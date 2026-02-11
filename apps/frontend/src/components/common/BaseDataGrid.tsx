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
  Menu,
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
import IconButton from '@mui/material/IconButton';
import {
  DataGrid,
  GridPaginationModel,
  GridRowModel,
  GridRowId,
  GridEditMode,
  GridDensity,
  GridRowSelectionModel,
  GridToolbar,
  GridToolbarQuickFilter,
  useGridApiRef,
  GridFilterModel,
  GridSortModel,
  GridInitialState,
} from '@mui/x-data-grid';
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
  columns: any[];
  rows: any[];
  title?: string;
  loading?: boolean;
  getRowId?: (row: any) => string | number;
  showToolbar?: boolean;
  onRowClick?: (params: any) => void;
  density?: GridDensity;
  sx?: any;
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
  onProcessRowUpdateError?: (error: any) => void;
  isCellEditable?: (params: any) => boolean;
  // Selection related props
  checkboxSelection?: boolean;
  disableRowSelectionOnClick?: boolean;
  onRowSelectionModelChange?: (selectionModel: GridRowSelectionModel) => void;
  rowSelectionModel?: GridRowSelectionModel;
  // Filter related props
  filters?: FilterConfig[];
  filterHandler?: (filteredRows: any[]) => void;
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
const StyledDataGrid = styled(DataGrid)({
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
    alignItems: 'center', // This ensures vertical centering of all cell content
    overflow: 'hidden',
  },
  border: 'none',
});

export default function BaseDataGrid({
  columns,
  rows,
  title,
  loading = false,
  getRowId,
  showToolbar = true,
  onRowClick,
  density,
  sx,
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
  const theme = useTheme();
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
  const [filteredRows, setFilteredRows] = useState<any[]>(rows);

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

        const rowValue = filter.filterField.split('.').reduce((obj, key) => {
          return obj && obj[key] !== undefined ? obj[key] : undefined;
        }, row);

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

  const handleRowClickWithLink = (params: any) => {
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

  const CustomToolbar = () => {
    return (
      <Box sx={{ p: 1, display: 'flex', justifyContent: 'flex-end' }}>
        <GridToolbarQuickFilter debounceMs={300} />
      </Box>
    );
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
      return (
        <Box
          sx={{
            p: 1,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 2,
          }}
        >
          <GridToolbar />
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
              slots: { toolbar: CustomToolbar },
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
                slots: { toolbar: CustomToolbar },
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
