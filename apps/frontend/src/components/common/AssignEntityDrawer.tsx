'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Box, Button, Paper } from '@mui/material';
import NorthEastIcon from '@mui/icons-material/NorthEast';
import type { SxProps, Theme } from '@mui/material/styles';
import {
  GridColDef,
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
  // Filter (tune) button
  onFilterClick?: () => void;
  hasActiveFilters?: boolean;
  activeFilterCount?: number;
  // Centered segmented quick-filter pills
  pillTabs?: ToolbarPillTab[];
  activePill?: string;
  onPillChange?: (value: string) => void;
  // Jump-off action (top-right) to create a brand-new entity elsewhere
  onCreateNew?: () => void;
  createNewLabel?: string;
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
}: AssignEntityDrawerProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selected, setSelected] = useState<GridRowSelectionModel>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setSearchQuery('');
      setSelected([]);
    }
  }, [open]);

  const filteredRows = useMemo(() => {
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

  const handleAssign = async () => {
    setSaving(true);
    try {
      await onAssign(selected as string[]);
    } finally {
      setSaving(false);
    }
  };

  const hasSelection = Array.isArray(selected) && selected.length > 0;

  // Inset the first/last column content to 30px so it lines up with the
  // toolbar and footer (which already use 30px horizontal padding).
  const gridSx = {
    '& .MuiDataGrid-columnHeader:first-of-type, & .MuiDataGrid-cell:first-of-type':
      { paddingLeft: '30px' },
    '& .MuiDataGrid-columnHeader:last-of-type, & .MuiDataGrid-cell:last-of-type':
      { paddingRight: '30px' },
  } as SxProps<Theme>;

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
          borderRadius: BORDER_RADIUS.md,
          border: (theme: Theme) =>
            `1px solid ${theme.palette.greyscale.border}`,
          boxShadow: ELEVATION.xs,
          overflow: 'hidden',
        }}
      >
        <Box sx={{ px: '30px', pt: '30px', pb: '30px' }}>
          <GridToolbar
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
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
        <BaseDataGrid
          rows={filteredRows}
          columns={columns}
          loading={loading}
          getRowId={getRowId}
          checkboxSelection
          disableRowSelectionOnClick
          disableColumnResize
          onRowSelectionModelChange={setSelected}
          rowSelectionModel={selected}
          disablePaperWrapper
          pageSizeOptions={[10, 25, 50]}
          initialState={{
            pagination: { paginationModel: { page: 0, pageSize: 10 } },
          }}
          hideRowsPerPageBelow={0}
          sx={gridSx}
        />
      </Paper>
    </BaseDrawer>
  );
}
