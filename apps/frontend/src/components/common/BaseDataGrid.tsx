import React, { useState, useEffect, ReactNode, useRef } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  styled,
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
  CircularProgress
} from '@mui/material';
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
  GridFilterModel
} from '@mui/x-data-grid';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';

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
    color?: 'inherit' | 'primary' | 'secondary' | 'success' | 'error' | 'info' | 'warning';
    splitButton?: {
      options: {
        label: string;
        onClick: () => void;
        disabled?: boolean;
      }[];
    };
  }[];
  // CRUD related props
  enableEditing?: boolean;
  editMode?: GridEditMode;
  processRowUpdate?: (newRow: GridRowModel, oldRow: GridRowModel) => Promise<GridRowModel> | GridRowModel;
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
  onFilterModelChange?: (model: GridFilterModel) => void;
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
  onFilterModelChange,
  linkPath,
  linkField = 'id',
  serverSidePagination = false,
  totalRows,
  paginationModel,
  onPaginationModelChange,
  pageSizeOptions = [10, 25, 50],
  enableQuickFilter = false
}: BaseDataGridProps) {
  const router = useRouter();
  const apiRef = useGridApiRef();
  
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
  
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});
  const [filteredRows, setFilteredRows] = useState<any[]>(rows);
  
  // Create refs and state for action buttons
  const buttonRefs = React.useRef<Array<React.RefObject<HTMLDivElement>>>(
    Array(actionButtons?.length || 0).fill(null).map(() => React.createRef())
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

  const handleFilterChange = (filterName: string) => (event: SelectChangeEvent<string>) => {
    setFilterValues(prev => ({
      ...prev,
      [filterName]: event.target.value
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

  const handleMenuItemClick = (
    onClick: () => void,
    index: number,
  ) => {
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

  if (!isInitialized) {
    return (
      <Box sx={{ width: '100%', display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'center', mb: 2, gap: 2 }}>
        {title && (
          <Typography variant="h6" component="h1">
            {title}
          </Typography>
        )}
        
        {filters && filters.length > 0 && (
          <Box sx={{ display: 'flex', gap: 2 }}>
            {filters.map((filter, index) => (
              <FormControl key={index} variant="outlined" size="small" sx={{ minWidth: 150 }}>
                <InputLabel id={`${filter.name}-label`}>{filter.label}</InputLabel>
                <Select
                  labelId={`${filter.name}-label`}
                  id={filter.name}
                  value={filterValues[filter.name] || filter.defaultValue}
                  onChange={handleFilterChange(filter.name)}
                  label={filter.label}
                >
                  {filter.options.map((option, idx) => (
                    <MenuItem key={idx} value={option.value}>{option.label}</MenuItem>
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
                const options = button.splitButton.options;  // Extract options to satisfy TypeScript
                return (
                  <React.Fragment key={index}>
                    <ButtonGroup
                      variant={button.variant || 'contained'}
                      color={button.color || 'primary'}
                      ref={buttonRefs.current[index]}
                      aria-label="split button"
                    >
                      <Button
                        onClick={button.onClick}
                        startIcon={button.icon}
                      >
                        {button.label}
                      </Button>
                      <Button
                        size="small"
                        aria-controls={openStates[index] ? 'split-button-menu' : undefined}
                        aria-expanded={openStates[index] ? 'true' : undefined}
                        aria-label="select option"
                        aria-haspopup="menu"
                        onClick={() => handleToggle(index)}
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
                              placement === 'bottom' ? 'center top' : 'center bottom',
                          }}
                        >
                          <Paper>
                            <ClickAwayListener onClickAway={(event) => handleClose(event, index)}>
                              <MenuList id="split-button-menu" autoFocusItem>
                                {options.map((option, optionIndex) => (
                                  <MenuItem
                                    key={optionIndex}
                                    disabled={option.disabled}
                                    onClick={() => handleMenuItemClick(option.onClick, index)}
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
                <Link key={index} href={button.href} style={{ textDecoration: 'none' }}>
                  <Button
                    variant={button.variant || 'contained'}
                    color={button.color || 'primary'}
                    startIcon={button.icon}
                  >
                    {button.label}
                  </Button>
                </Link>
              ) : (
                <Button
                  key={index}
                  variant={button.variant || 'contained'}
                  color={button.color || 'primary'}
                  onClick={button.onClick}
                  startIcon={button.icon}
                >
                  {button.label}
                </Button>
              );
            })}
          </Box>
        )}
        {customToolbarContent}
      </Box>

      <Paper sx={{ width: '100%', boxShadow: 0, borderRadius: 2, overflow: 'hidden' }}>
        <StyledDataGrid
          apiRef={apiRef}
          rows={serverSidePagination ? rows : filteredRows}
          columns={columns}
          getRowId={getRowId}
          autoHeight
          pagination
          paginationMode={serverSidePagination ? "server" : "client"}
          rowCount={serverSidePagination ? totalRows : undefined}
          paginationModel={paginationModel}
          onPaginationModelChange={onPaginationModelChange}
          pageSizeOptions={pageSizeOptions}
          checkboxSelection={checkboxSelection}
          disableVirtualization={false}
          loading={loading}
          onRowClick={enableEditing ? undefined : (linkPath || onRowClick) ? handleRowClickWithLink : undefined}
          disableMultipleRowSelection={disableMultipleRowSelection}
          {...(density && { density })}
          {...(enableQuickFilter && {
            slots: { toolbar: CustomToolbar }
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
          {...(serverSideFiltering && {
            filterMode: "server",
            onFilterModelChange,
          })}
        />
      </Paper>
    </>
  );
} 

export type { FilterOption, FilterConfig }; 