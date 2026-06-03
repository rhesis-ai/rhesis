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
import { GridToolbar } from '@/components/common/GridToolbar';
import { rowActionsHoverSx } from '@/components/common/createRowActionsColumn';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';

// --- Context for sharing search state with the toolbar slot ---

interface LinkedEntitiesContextValue {
  searchQuery: string;
  setSearchQuery: (value: string) => void;
}

const LinkedEntitiesContext = createContext<LinkedEntitiesContextValue>({
  searchQuery: '',
  setSearchQuery: () => {},
});

function LinkedEntitiesToolbar() {
  const { searchQuery, setSearchQuery } = useContext(LinkedEntitiesContext);
  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search…"
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
}: LinkedEntitiesGridProps) {
  const [searchQuery, setSearchQuery] = useState('');

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

  const showEmptyState = !loading && rows.length === 0 && !!emptyState;

  return (
    <LinkedEntitiesContext.Provider value={{ searchQuery, setSearchQuery }}>
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
            px: 2,
            pt: 2.5,
            pb: showEmptyState ? 2.5 : 0,
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
                borderRadius: BORDER_RADIUS.sm,
                px: '16px',
                py: '8px',
                '&:hover': { borderWidth: 2 },
              }}
            >
              Assign
            </Button>
          )}
        </Box>

        {/* Empty state or grid */}
        {showEmptyState ? (
          <Box sx={{ px: 2, pb: 2.5 }}>{emptyState}</Box>
        ) : (
          <BaseDataGrid
            rows={filteredRows}
            columns={columns}
            loading={loading}
            getRowId={getRowId}
            onRowClick={onRowClick}
            toolbarSlot={LinkedEntitiesToolbar}
            disablePaperWrapper
            pageSizeOptions={pageSizeOptions}
            disableRowSelectionOnClick
            sx={rowActionsHoverSx}
          />
        )}
      </Paper>
    </LinkedEntitiesContext.Provider>
  );
}
