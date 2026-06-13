'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Box, Button, Paper } from '@mui/material';
import NorthEastIcon from '@mui/icons-material/NorthEast';
import type { SxProps, Theme } from '@mui/material/styles';
import {
  GridColDef,
  GridPaginationModel,
  GridRowModel,
  GridRowSelectionModel,
} from '@mui/x-data-grid';
import BaseDrawer from '@/components/common/BaseDrawer';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import {
  GridToolbar,
  PrimarySegmentedPills,
  type ToolbarPillTab,
} from '@/components/common/GridToolbar';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';

export interface AssignEntityDrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  rows: GridRowModel[];
  columns: GridColDef[];
  loading?: boolean;
  getRowId: (row: GridRowModel) => string;
  onAssign: (selectedIds: string[]) => Promise<void>;
  saveButtonText?: string;
  searchPlaceholder?: string;
  /** Parent-supplied predicate for pill/drawer filtering (search is handled internally). */
  rowFilter?: (row: GridRowModel) => boolean;
  onFilterClick?: () => void;
  hasActiveFilters?: boolean;
  activeFilterCount?: number;
  pillTabs?: ToolbarPillTab[];
  activePill?: string;
  onPillChange?: (value: string) => void;
  onCreateNew?: () => void;
  createNewLabel?: string;
  /** Controlled search — parent owns query (e.g. server-side test search). */
  searchQuery?: string;
  onSearchQueryChange?: (query: string) => void;
  serverSidePagination?: boolean;
  totalRows?: number;
  paginationModel?: GridPaginationModel;
  onPaginationModelChange?: (model: GridPaginationModel) => void;
}

export default function AssignEntityDrawer({
  open,
  onClose,
  title,
  rows,
  columns,
  loading = false,
  getRowId,
  onAssign,
  saveButtonText = 'Assign',
  searchPlaceholder = 'Search…',
  rowFilter,
  onFilterClick,
  hasActiveFilters,
  activeFilterCount,
  pillTabs,
  activePill,
  onPillChange,
  onCreateNew,
  createNewLabel = 'Create new',
  searchQuery: controlledSearchQuery,
  onSearchQueryChange,
  serverSidePagination = false,
  totalRows,
  paginationModel,
  onPaginationModelChange,
}: AssignEntityDrawerProps) {
  const [internalSearchQuery, setInternalSearchQuery] = useState('');
  const [selected, setSelected] = useState<GridRowSelectionModel>([]);
  const [saving, setSaving] = useState(false);

  const isControlledSearch = controlledSearchQuery !== undefined;
  const searchQuery = isControlledSearch
    ? controlledSearchQuery
    : internalSearchQuery;

  useEffect(() => {
    if (open) {
      if (!isControlledSearch) {
        setInternalSearchQuery('');
      }
      setSelected([]);
    }
  }, [open, isControlledSearch]);

  const handleSearchInputChange = (query: string) => {
    if (isControlledSearch) {
      onSearchQueryChange?.(query);
    } else {
      setInternalSearchQuery(query);
    }
  };

  const filteredRows = useMemo(() => {
    let result = rowFilter ? rows.filter(rowFilter) : rows;
    if (!isControlledSearch && searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(row => {
        const name = typeof row.name === 'string' ? row.name : '';
        const description =
          typeof row.description === 'string' ? row.description : '';
        return (
          name.toLowerCase().includes(q) ||
          description.toLowerCase().includes(q)
        );
      });
    }
    return result;
  }, [rows, rowFilter, searchQuery, isControlledSearch]);

  const handleAssign = async () => {
    setSaving(true);
    try {
      await onAssign(selected as string[]);
    } finally {
      setSaving(false);
    }
  };

  const hasSelection = Array.isArray(selected) && selected.length > 0;

  const gridContainerSx: SxProps<Theme> = serverSidePagination
    ? {
        flex: 1,
        minHeight: 480,
        display: 'flex',
        flexDirection: 'column',
      }
    : {
        flex: 1,
        minHeight: 400,
      };

  const gridSx: SxProps<Theme> = serverSidePagination
    ? { flex: 1, minHeight: 400, height: '100%' }
    : { flex: 1, minHeight: 400 };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={title}
      loading={saving}
      onSave={handleAssign}
      saveDisabled={!hasSelection}
      saveButtonText={saveButtonText}
      width="min(1186px, 95vw)"
    >
      <Paper
        elevation={0}
        sx={{
          width: '100%',
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          borderRadius: BORDER_RADIUS.md,
          border: (theme: Theme) =>
            `1px solid ${theme.palette.greyscale.border}`,
          boxShadow: ELEVATION.xs,
          overflow: serverSidePagination ? 'visible' : 'hidden',
        }}
      >
        <Box sx={{ px: '30px', pt: '30px', pb: '30px', flexShrink: 0 }}>
          <GridToolbar
            searchQuery={searchQuery}
            onSearchChange={handleSearchInputChange}
            searchPlaceholder={searchPlaceholder}
            searchWidth={288}
            onFilterClick={onFilterClick ? () => onFilterClick() : undefined}
            hasActiveFilters={hasActiveFilters}
            activeFilterCount={activeFilterCount}
            sx={{ px: 0, py: 0, gap: '20px', minHeight: 'auto' }}
            middleContent={
              pillTabs && pillTabs.length > 0 ? (
                <PrimarySegmentedPills
                  tabs={pillTabs}
                  mode="single"
                  activeValue={activePill ?? pillTabs[0]?.value ?? ''}
                  onSingleChange={value => onPillChange?.(value)}
                />
              ) : undefined
            }
            rightContent={
              onCreateNew ? (
                <Button
                  variant="text"
                  startIcon={<NorthEastIcon />}
                  onClick={onCreateNew}
                  sx={{
                    fontWeight: 400,
                    fontSize: 14,
                    lineHeight: '22px',
                    color: 'primary.main',
                    px: '16px',
                    py: '8px',
                    whiteSpace: 'nowrap',
                    '& .MuiButton-startIcon': {
                      marginRight: '4px',
                      marginLeft: 0,
                    },
                    '& .MuiButton-startIcon > *:nth-of-type(1)': {
                      fontSize: 20,
                    },
                  }}
                >
                  {createNewLabel}
                </Button>
              ) : undefined
            }
          />
        </Box>
        <Box sx={gridContainerSx}>
          <BaseDataGrid
            rows={filteredRows}
            columns={columns}
            loading={loading}
            getRowId={getRowId}
            checkboxSelection
            disableRowSelectionOnClick
            disableColumnResize
            autoHeight={!serverSidePagination}
            onRowSelectionModelChange={setSelected}
            rowSelectionModel={selected}
            disablePaperWrapper
            pageSizeOptions={[10, 25, 50]}
            {...(serverSidePagination &&
            paginationModel &&
            onPaginationModelChange
              ? {
                  serverSidePagination: true,
                  totalRows,
                  paginationModel,
                  onPaginationModelChange,
                }
              : {
                  initialState: {
                    pagination: { paginationModel: { page: 0, pageSize: 10 } },
                  },
                })}
            hideRowsPerPageBelow={serverSidePagination ? 10 : 0}
            sx={gridSx}
          />
        </Box>
      </Paper>
    </BaseDrawer>
  );
}
