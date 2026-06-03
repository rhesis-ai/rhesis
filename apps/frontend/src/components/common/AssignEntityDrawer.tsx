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
import { SearchPill } from '@/components/common/SearchPill';

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
    if (!searchQuery.trim()) return rows;
    const q = searchQuery.toLowerCase();
    return rows.filter(row => {
      const name = typeof row.name === 'string' ? row.name : '';
      const description =
        typeof row.description === 'string' ? row.description : '';
      return (
        name.toLowerCase().includes(q) || description.toLowerCase().includes(q)
      );
    });
  }, [rows, searchQuery]);

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
      width={960}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <SearchPill
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Search…"
          width="100%"
        />
        <BaseDataGrid
          rows={filteredRows}
          columns={columns}
          loading={loading}
          getRowId={getRowId}
          checkboxSelection
          disableRowSelectionOnClick
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
