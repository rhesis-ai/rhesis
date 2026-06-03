'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Box } from '@mui/material';
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
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
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
        />
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
        />
      </Box>
    </BaseDrawer>
  );
}
