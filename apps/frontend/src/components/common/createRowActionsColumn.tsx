'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import type { GridColDef, GridRowId } from '@mui/x-data-grid';
import { gridClasses } from '@mui/x-data-grid';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import type { SvgIconComponent } from '@mui/icons-material';
import { EditIcon, DeleteIcon } from '@/components/icons';

export const ROW_ACTIONS_CLASS = 'row-actions';

interface RowActionsHoverContextValue {
  hoveredRowId: GridRowId | null;
  setHoveredRowId: React.Dispatch<React.SetStateAction<GridRowId | null>>;
}

const RowActionsHoverContext =
  createContext<RowActionsHoverContextValue | null>(null);

/** Wrap a DataGrid that uses `createRowActionsColumn` (done automatically in BaseDataGrid). */
export function RowActionsHoverProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [hoveredRowId, setHoveredRowId] = useState<GridRowId | null>(null);
  const value = useMemo(
    () => ({ hoveredRowId, setHoveredRowId }),
    [hoveredRowId]
  );
  return (
    <RowActionsHoverContext.Provider value={value}>
      {children}
    </RowActionsHoverContext.Provider>
  );
}

function useRowActionsHovered(rowId: GridRowId): boolean {
  const ctx = useContext(RowActionsHoverContext);
  // Outside a provider (unit-test mocks, legacy grids): keep actions visible.
  if (!ctx) return true;
  return String(ctx.hoveredRowId) === String(rowId);
}

/** Pointer handlers for the DataGrid root — tracks which row is hovered. */
export function useRowActionsGridRootProps(): {
  onMouseMove: (event: React.MouseEvent) => void;
  onMouseLeave: () => void;
} {
  const ctx = useContext(RowActionsHoverContext);
  const setHoveredRowId = ctx?.setHoveredRowId;

  const onMouseMove = useCallback(
    (event: React.MouseEvent) => {
      if (!setHoveredRowId) return;
      const rowEl = (event.target as HTMLElement).closest(
        `.${gridClasses.row}`
      );
      const nextId = rowEl?.getAttribute('data-id') ?? null;
      setHoveredRowId(prev => (String(prev) === nextId ? prev : nextId));
    },
    [setHoveredRowId]
  );

  const onMouseLeave = useCallback(() => {
    setHoveredRowId?.(null);
  }, [setHoveredRowId]);

  return useMemo(
    () => ({ onMouseMove, onMouseLeave }),
    [onMouseMove, onMouseLeave]
  );
}

const rowActionsRevealSelectors = [
  `& .${gridClasses.row}:hover`,
  `& .${gridClasses.row}.Mui-hovered`,
  `& .${gridClasses.row}:focus-within`,
  `& .${gridClasses.cell}[data-field="actions"]:hover`,
].join(', ');

/**
 * CSS fallback for grids that render `ROW_ACTIONS_CLASS` manually. Grids using
 * `createRowActionsColumn` inside BaseDataGrid get JS row-hover tracking
 * automatically and do not need to pass this sx.
 */
export const rowActionsHoverSx: SxProps<Theme> = {
  [`& .${ROW_ACTIONS_CLASS}`]: {
    opacity: 0,
    pointerEvents: 'none',
    transition: 'opacity 0.15s ease',
  },
  [`${rowActionsRevealSelectors} .${ROW_ACTIONS_CLASS}`]: {
    opacity: 1,
    pointerEvents: 'auto',
  },
};

interface RowActionsCellProps {
  rowId: GridRowId;
  children: React.ReactNode;
}

function RowActionsCell({ rowId, children }: RowActionsCellProps) {
  const visible = useRowActionsHovered(rowId);
  return (
    <Box
      className={ROW_ACTIONS_CLASS}
      style={{
        opacity: visible ? 1 : 0,
        pointerEvents: visible ? 'auto' : 'none',
      }}
      sx={{
        display: 'flex',
        gap: '4px',
        justifyContent: 'center',
        alignItems: 'center',
        width: '100%',
        transition: 'opacity 0.15s ease',
      }}
    >
      {children}
    </Box>
  );
}

interface RowActionsColumnOptions {
  onEdit?: (id: string, row: Record<string, unknown>) => void;
  onDelete?: (id: string, row: Record<string, unknown>) => void;
  onCancel?: (id: string, row: Record<string, unknown>) => void;
  /** Return false to hide the edit button for this row. Defaults to always visible. */
  canEdit?: (row: Record<string, unknown>) => boolean;
  canCancel?: (row: Record<string, unknown>) => boolean;
  canDelete?: (row: Record<string, unknown>) => boolean;
  width?: number;
  editTooltip?: string;
  deleteTooltip?: string;
  cancelTooltip?: string;
  deleteIcon?: SvgIconComponent;
}

/**
 * Creates a header-less trailing column showing edit / delete / cancel icons
 * revealed on row hover. Pass handlers as needed; `onCancel` is only rendered
 * when `canCancel(row)` returns true (defaults to always-true if omitted).
 */
export function createRowActionsColumn({
  onEdit,
  onDelete,
  onCancel,
  canEdit,
  canCancel,
  canDelete,
  width = 88,
  editTooltip = 'Edit',
  deleteTooltip = 'Delete',
  cancelTooltip = 'Cancel',
  deleteIcon: DeleteIconComponent = DeleteIcon,
}: RowActionsColumnOptions): GridColDef {
  return {
    field: 'actions',
    headerName: '',
    width,
    sortable: false,
    hideable: false,
    disableColumnMenu: true,
    align: 'center',
    headerAlign: 'center',
    renderCell: params => {
      const id = String(params.id);
      const row = params.row as Record<string, unknown>;
      const cancelFn = onCancel;
      const showEdit = onEdit && (!canEdit || canEdit(row));
      const showCancel = cancelFn && (!canCancel || canCancel(row));
      const showDelete = onDelete && (!canDelete || canDelete(row));

      return (
        <RowActionsCell rowId={params.id}>
          {showEdit && (
            <Tooltip title={editTooltip}>
              <IconButton
                size="small"
                onClick={e => {
                  e.stopPropagation();
                  onEdit!(id, row);
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
          {showCancel && cancelFn && (
            <Tooltip title={cancelTooltip}>
              <IconButton
                size="small"
                onClick={e => {
                  e.stopPropagation();
                  cancelFn(id, row);
                }}
                sx={{
                  p: 0.5,
                  color: 'text.secondary',
                  '&:hover': {
                    color: 'warning.main',
                    bgcolor: 'action.hover',
                  },
                }}
              >
                <StopCircleOutlinedIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          )}
          {showDelete && (
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
                <DeleteIconComponent sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          )}
        </RowActionsCell>
      );
    },
  };
}
