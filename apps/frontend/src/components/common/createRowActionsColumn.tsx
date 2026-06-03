'use client';

import React from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import type { GridColDef } from '@mui/x-data-grid';
import { EditIcon, DeleteIcon } from '@/components/icons';

export const ROW_ACTIONS_CLASS = 'row-actions';

/**
 * Merge this sx onto your BaseDataGrid to hide the actions column by default
 * and reveal it on row hover.
 */
export const rowActionsHoverSx: SxProps<Theme> = {
  [`& .${ROW_ACTIONS_CLASS}`]: {
    opacity: 0,
    pointerEvents: 'none',
    transition: 'opacity 0.15s ease',
  },
  [`& .MuiDataGrid-row:hover .${ROW_ACTIONS_CLASS}`]: {
    opacity: 1,
    pointerEvents: 'auto',
  },
};

interface RowActionsColumnOptions {
  onEdit?: (id: string, row: Record<string, unknown>) => void;
  onDelete?: (id: string, row: Record<string, unknown>) => void;
  width?: number;
  editTooltip?: string;
  deleteTooltip?: string;
}

/**
 * Creates a header-less trailing column showing edit + delete icons that are
 * revealed on row hover. Pass `onEdit` and/or `onDelete` as needed.
 */
export function createRowActionsColumn({
  onEdit,
  onDelete,
  width = 88,
  editTooltip = 'Edit',
  deleteTooltip = 'Delete',
}: RowActionsColumnOptions): GridColDef {
  return {
    field: 'actions',
    headerName: '',
    width,
    sortable: false,
    disableColumnMenu: true,
    align: 'center',
    headerAlign: 'center',
    renderCell: params => {
      const id = String(params.id);
      const row = params.row as Record<string, unknown>;

      return (
        <Box
          className={ROW_ACTIONS_CLASS}
          sx={{
            display: 'flex',
            gap: '4px',
            justifyContent: 'center',
            alignItems: 'center',
            width: '100%',
          }}
        >
          {onEdit && (
            <Tooltip title={editTooltip}>
              <IconButton
                size="small"
                onClick={e => {
                  e.stopPropagation();
                  onEdit(id, row);
                }}
                sx={{
                  p: 0.5,
                  color: 'text.secondary',
                  '&:hover': {
                    color: 'primary.main',
                    bgcolor: 'action.hover',
                  },
                }}
              >
                <EditIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          )}
          {onDelete && (
            <Tooltip title={deleteTooltip}>
              <IconButton
                size="small"
                onClick={e => {
                  e.stopPropagation();
                  onDelete(id, row);
                }}
                sx={{
                  p: 0.5,
                  color: 'text.secondary',
                  '&:hover': {
                    color: 'error.main',
                    bgcolor: 'action.hover',
                  },
                }}
              >
                <DeleteIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      );
    },
  };
}
