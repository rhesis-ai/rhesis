'use client';

import React, { createContext, useContext, useMemo, useState } from 'react';
import { Box, Button, Paper, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import {
  GridColDef,
  GridRowModel,
  GridRowParams,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import type { SxProps, Theme } from '@mui/material/styles';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import {
  GridToolbar,
  PrimarySegmentedPills,
  type ToolbarPillTab,
} from '@/components/common/GridToolbar';
import { rowActionsHoverSx } from '@/components/common/createRowActionsColumn';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';

// --- Context for sharing toolbar state with the toolbar slot ---

interface LinkedEntitiesContextValue {
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  searchPlaceholder: string;
  onFilterClick?: () => void;
  hasActiveFilters?: boolean;
  activeFilterCount?: number;
  pillTabs?: ToolbarPillTab[];
  activePill?: string;
  onPillChange?: (value: string) => void;
}

const LinkedEntitiesContext = createContext<LinkedEntitiesContextValue>({
  searchQuery: '',
  setSearchQuery: () => {},
  searchPlaceholder: 'Search…',
});

function LinkedEntitiesToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    searchPlaceholder,
    onFilterClick,
    hasActiveFilters,
    activeFilterCount,
    pillTabs,
    activePill,
    onPillChange,
  } = useContext(LinkedEntitiesContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder={searchPlaceholder}
      onFilterClick={onFilterClick ? () => onFilterClick() : undefined}
      hasActiveFilters={hasActiveFilters}
      activeFilterCount={activeFilterCount}
      sx={{ px: '30px', pt: 0, pb: '30px', minHeight: 'auto' }}
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
        <>
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
    />
  );
}

// --- Component props ---

export interface LinkedEntitiesGridProps {
  title: string;
  rows: GridRowModel[];
  columns: GridColDef[];
  loading?: boolean;
  getRowId: (row: GridRowModel) => string;
  onRowClick?: (params: GridRowParams) => void;
  onAssignClick?: () => void;
  pageSizeOptions?: number[];
  sx?: SxProps<Theme>;
  emptyState?: React.ReactNode;
  searchPlaceholder?: string;
  /** Parent-supplied predicate for pill/drawer filtering (search is handled internally). */
  rowFilter?: (row: GridRowModel) => boolean;
  // Filter (tune) button
  onFilterClick?: () => void;
  hasActiveFilters?: boolean;
  activeFilterCount?: number;
  // Centered segmented pill tabs
  pillTabs?: ToolbarPillTab[];
  activePill?: string;
  onPillChange?: (value: string) => void;
}

export default function LinkedEntitiesGrid({
  title,
  rows,
  columns,
  loading = false,
  getRowId,
  onRowClick,
  onAssignClick,
  pageSizeOptions = [5, 10, 25],
  sx,
  emptyState,
  searchPlaceholder = 'Search…',
  rowFilter,
  onFilterClick,
  hasActiveFilters,
  activeFilterCount,
  pillTabs,
  activePill,
  onPillChange,
}: LinkedEntitiesGridProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const displayedRows = useMemo(() => {
    let result = rowFilter ? rows.filter(rowFilter) : rows;
    if (searchQuery.trim()) {
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
  }, [rows, rowFilter, searchQuery]);

  // Empty state is based on the total linked rows, not the filtered subset.
  const showEmptyState = !loading && rows.length === 0 && !!emptyState;

  // Inset the first/last column content to 30px so it lines up with the
  // header, toolbar and footer (which already use 30px horizontal padding).
  const gridSx = {
    ...(rowActionsHoverSx as Record<string, unknown>),
    '& .MuiDataGrid-columnHeader:first-of-type, & .MuiDataGrid-cell:first-of-type':
      { paddingLeft: '30px' },
    '& .MuiDataGrid-columnHeader:last-of-type, & .MuiDataGrid-cell:last-of-type':
      { paddingRight: '30px' },
  } as SxProps<Theme>;

  const contextValue: LinkedEntitiesContextValue = {
    searchQuery,
    setSearchQuery,
    searchPlaceholder,
    onFilterClick,
    hasActiveFilters,
    activeFilterCount,
    pillTabs,
    activePill,
    onPillChange,
  };

  return (
    <LinkedEntitiesContext.Provider value={contextValue}>
      <Paper
        elevation={0}
        sx={[
          {
            width: '100%',
            borderRadius: BORDER_RADIUS.md,
            border: (theme: Theme) =>
              `1px solid ${theme.palette.greyscale.border}`,
            boxShadow: ELEVATION.xs,
            overflow: 'hidden',
          },
          ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
        ]}
      >
        {/* Card header */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: '30px',
            pt: '30px',
            pb: '30px',
          }}
        >
          <Typography
            sx={{
              fontSize: 20,
              fontWeight: 600,
              lineHeight: '24px',
              color: 'primary.main',
            }}
          >
            {title} ({rows.length})
          </Typography>
          {onAssignClick && (
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={onAssignClick}
              sx={{
                borderWidth: 2,
                fontWeight: 700,
                fontSize: 14,
                lineHeight: '22px',
                borderRadius: BORDER_RADIUS.sm,
                px: '16px',
                py: '8px',
                '& .MuiButton-startIcon': { marginRight: '4px', marginLeft: 0 },
                '& .MuiButton-startIcon > *:nth-of-type(1)': { fontSize: 20 },
                '&:hover': { borderWidth: 2 },
              }}
            >
              Assign
            </Button>
          )}
        </Box>

        {/* Empty state or grid */}
        {showEmptyState ? (
          <Box sx={{ px: '30px', pb: '30px' }}>{emptyState}</Box>
        ) : (
          <BaseDataGrid
            rows={displayedRows}
            columns={columns}
            loading={loading}
            getRowId={getRowId}
            onRowClick={onRowClick}
            toolbarSlot={LinkedEntitiesToolbar}
            disablePaperWrapper
            pageSizeOptions={pageSizeOptions}
            initialState={{
              pagination: {
                paginationModel: {
                  page: 0,
                  pageSize: pageSizeOptions.includes(10)
                    ? 10
                    : (pageSizeOptions[0] ?? 10),
                },
              },
            }}
            disableRowSelectionOnClick
            hideRowsPerPageBelow={0}
            sx={gridSx}
          />
        )}
      </Paper>
    </LinkedEntitiesContext.Provider>
  );
}
