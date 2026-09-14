'use client';

import React, { useCallback, useMemo, useRef, useState } from 'react';
import { GridColDef, GridRowParams } from '@mui/x-data-grid';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControlLabel,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import { MentionText } from '@/components/common/MentionTextInput';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';
import { can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { DeleteIcon } from '@/components/icons';
import {
  Annotation,
  ANNOTATION_ENTITY_LABELS,
  ANNOTATION_TARGET_LABELS,
} from '@/utils/api-client/interfaces/annotation';
import { annotationsList } from './list';
import { isPassedStatusName } from '@/utils/test-result-status';
import AnnotationFilterDrawer, {
  type AnnotationFilters,
  EMPTY_ANNOTATION_FILTERS,
  countActiveAnnotationFilters,
} from './AnnotationFilterDrawer';

interface AnnotationsGridProps {
  onTotalCountChange?: (count: number) => void;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: Annotation[];
  initialTotalCount?: number;
}

const STATUS_PILL_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Open', value: 'open' },
  { label: 'Resolved', value: 'resolved' },
];

function toFilters(state: EntityGridFilterState<AnnotationFilters>) {
  return {
    search: state.search,
    status: state.pill,
    entityType: state.drawer.entity_type,
    rating: state.drawer.rating,
    targetType: state.drawer.target_type,
  };
}

const drawerAdapter: EntityGridDrawerAdapter<AnnotationFilters> = {
  empty: EMPTY_ANNOTATION_FILTERS,
  countActive: countActiveAnnotationFilters,
  render: props => (
    <AnnotationFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
};

function formatTarget(item: Annotation): string {
  const label = ANNOTATION_TARGET_LABELS[item.target_type] || item.target_type;
  return item.target_reference ? `${label}: ${item.target_reference}` : label;
}

export default function AnnotationsGrid({
  onTotalCountChange,
  initialData,
  initialTotalCount,
}: AnnotationsGridProps) {
  const theme = useTheme();
  const notifications = useNotifications();

  // Per-row affordances now arrive on the row itself, so no ambient gate and
  // no branching on which parent the annotation hangs off.
  const canEditRow = useCallback(
    (row: Annotation) => can(row, Capability.Annotation.UPDATE),
    []
  );
  const canDeleteRow = useCallback(
    (row: Annotation) => can(row, Capability.Annotation.DELETE),
    []
  );

  const [editTarget, setEditTarget] = useState<Annotation | null>(null);
  const [editComments, setEditComments] = useState('');
  const [editResolved, setEditResolved] = useState(false);
  const [editSaving, setEditSaving] = useState(false);

  const handleEditClick = useCallback((row: Annotation) => {
    setEditTarget(row);
    setEditComments(row.comments ?? '');
    setEditResolved(Boolean(row.resolved));
  }, []);

  const handleCancelEdit = useCallback(() => setEditTarget(null), []);

  const makeConfirmEdit = useCallback(
    (refresh: () => void) => async () => {
      if (!editTarget) return;
      try {
        setEditSaving(true);
        const factory = new ApiClientFactory();
        await factory.getAnnotationsClient().updateAnnotation(editTarget.id, {
          comments: editComments,
          resolved: editResolved,
        });
        notifications.show('Annotation updated.', { severity: 'success' });
        setEditTarget(null);
        refresh();
      } catch (error: unknown) {
        const message =
          error instanceof Error
            ? error.message
            : 'Failed to update annotation. Please try again.';
        notifications.show(message, { severity: 'error' });
      } finally {
        setEditSaving(false);
      }
    },
    [editTarget, editComments, editResolved, notifications]
  );

  const [deleteTarget, setDeleteTarget] = useState<Annotation | null>(
    null
  );
  const [deleting, setDeleting] = useState(false);

  const handleDeleteClick = useCallback((row: Annotation) => {
    setDeleteTarget(row);
  }, []);

  const handleCancelDelete = useCallback(() => setDeleteTarget(null), []);

  const makeConfirmDelete = useCallback(
    (refresh: () => void) => async () => {
      if (!deleteTarget) return;
      try {
        setDeleting(true);
        const factory = new ApiClientFactory();
        await factory
          .getAnnotationsClient()
          .deleteAnnotation(deleteTarget.id);
        notifications.show('Annotation deleted.', { severity: 'success' });
        setDeleteTarget(null);
        refresh();
      } catch (error: unknown) {
        const message =
          error instanceof Error
            ? error.message
            : 'Failed to delete annotation. Please try again.';
        notifications.show(message, { severity: 'error' });
      } finally {
        setDeleting(false);
      }
    },
    [deleteTarget, notifications]
  );

  const extraRowActions = useMemo(
    () => [
      {
        key: 'delete',
        icon: DeleteIcon,
        tooltip: 'Delete annotation',
        onClick: (_id: string, row: Record<string, unknown>) =>
          handleDeleteClick(row as unknown as Annotation),
        can: (row: Record<string, unknown>) =>
          canDeleteRow(row as unknown as Annotation),
        hoverColor: 'error.main' as const,
      },
    ],
    [handleDeleteClick, canDeleteRow]
  );

  const onTotalCountChangeRef = useRef(onTotalCountChange);
  onTotalCountChangeRef.current = onTotalCountChange;
  const handleDataChange = useCallback(
    (
      _data: Annotation[],
      totalCount: number,
      filtersActive: boolean
    ) => {
      // Report the unfiltered total only — the page header shows the overall count.
      if (!filtersActive) {
        onTotalCountChangeRef.current?.(totalCount);
      }
    },
    []
  );

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'entity_type',
        headerName: 'Type',
        flex: 1.4,
        sortable: false,
        valueGetter: (_value, row) =>
          ANNOTATION_ENTITY_LABELS[(row as Annotation).entity_type] ||
          (row as Annotation).entity_type,
      },
      {
        field: 'target',
        headerName: 'Target',
        flex: 1,
        minWidth: 160,
        sortable: false,
        valueGetter: (_value, row) => formatTarget(row as Annotation),
      },
      {
        field: 'rating',
        headerName: 'Rating',
        flex: 1.2,
        sortable: false,
        valueGetter: (_value, row) => row.status?.name || '',
        renderCell: params => {
          const name = params.row.status?.name;
          if (!name) {
            return (
              <Typography variant="body2" color="text.secondary">
                —
              </Typography>
            );
          }
          const passed = isPassedStatusName(name);
          const label =
            name.toLowerCase() === 'pass'
              ? 'Passed'
              : name.toLowerCase() === 'fail'
                ? 'Failed'
                : name;
          return (
            <GridBadge
              label={label}
              sx={{
                bgcolor: passed
                  ? alpha(theme.palette.success.main, 0.12)
                  : alpha(theme.palette.error.main, 0.12),
                color: passed ? 'success.dark' : 'error.dark',
              }}
            />
          );
        },
      },
      {
        field: 'user',
        headerName: 'Annotator',
        flex: 1.6,
        sortable: false,
        valueGetter: (_value, row) => row.user?.name || '—',
      },
      {
        field: 'requirement_name',
        headerName: 'Requirement',
        flex: 1,
        minWidth: 140,
        sortable: false,
        valueGetter: (_value, row) =>
          (row as Annotation).context?.requirement_name || '',
        renderCell: params => {
          const name = (params.row as Annotation).context?.requirement_name;
          return (
            <Typography
              variant="body2"
              noWrap
              title={name || undefined}
              sx={{ color: name ? 'text.primary' : 'text.secondary' }}
            >
              {name || '—'}
            </Typography>
          );
        },
      },
      {
        field: 'resolved',
        headerName: 'Status',
        flex: 1.2,
        sortable: false,
        valueGetter: (_value, row) => (row.resolved ? 'Resolved' : 'Open'),
        renderCell: params => {
          const resolved = Boolean(params.row.resolved);
          return (
            <GridBadge
              label={resolved ? 'Resolved' : 'Open'}
              sx={
                resolved
                  ? {
                      bgcolor: alpha(theme.palette.success.main, 0.12),
                      color: 'success.dark',
                    }
                  : undefined
              }
            />
          );
        },
      },
      {
        field: 'comments',
        headerName: 'Comment',
        flex: 1.5,
        minWidth: 200,
        sortable: false,
        renderCell: params => (
          <Typography
            variant="body2"
            noWrap
            title={params.row.comments}
            sx={{ color: 'text.secondary' }}
          >
            {params.row.comments ? (
              <MentionText text={params.row.comments} />
            ) : (
              '—'
            )}
          </Typography>
        ),
      },
    ],
    [theme]
  );

  // An annotation hangs off another entity — a click opens that entity where
  // the annotation was left, in a new tab so the list isn't lost.
  const handleRowClick = useCallback((params: GridRowParams) => {
    const row = params.row as Annotation;
    const ctx = row.context;
    let url: string | null = null;
    if (row.entity_type === 'TestResult' && ctx?.test_run_id) {
      url =
        `/test-runs/${encodeURIComponent(ctx.test_run_id)}` +
        `?selectedresult=${encodeURIComponent(ctx.test_result_id ?? row.entity_id)}` +
        `&detailTab=annotations`;
    } else if (row.entity_type === 'Trace' && ctx?.trace_id && ctx?.project_id) {
      url =
        `/traces?open_trace=${encodeURIComponent(ctx.trace_id)}` +
        `&project_id=${encodeURIComponent(ctx.project_id)}`;
    }
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  }, []);

  return (
    <EntityGrid<
      Annotation,
      typeof annotationsList.filters,
      AnnotationFilters
    >
      descriptor={annotationsList}
      columns={columns}
      toFilters={toFilters}
      emptyState={null}
      embedded
      initialData={initialData}
      initialTotalCount={initialTotalCount}
      onDataChange={handleDataChange}
      searchPlaceholder="Search annotations…"
      pills={{ tabs: STATUS_PILL_TABS }}
      drawer={drawerAdapter}
      onRowClick={handleRowClick}
      editAction={{
        onClick: (_id, row) => handleEditClick(row),
        can: canEditRow,
      }}
      extraRowActions={extraRowActions}
      persistState={false}
      serverSort={false}
      pageSizeOptions={[10, 25, 50]}
      sx={{ '& .MuiDataGrid-row': { cursor: 'pointer' } }}
      renderSelectionExtras={ctx => (
        <>
          <Dialog
            open={editTarget !== null}
            onClose={handleCancelEdit}
            maxWidth="sm"
            fullWidth
          >
            <DialogTitle>Edit Annotation</DialogTitle>
            <DialogContent>
              <TextField
                autoFocus
                margin="dense"
                label="Comment"
                fullWidth
                multiline
                rows={4}
                value={editComments}
                onChange={e => setEditComments(e.target.value)}
              />
              <FormControlLabel
                sx={{ mt: 1 }}
                control={
                  <Switch
                    checked={editResolved}
                    onChange={e => setEditResolved(e.target.checked)}
                  />
                }
                label="Resolved"
              />
            </DialogContent>
            <DialogActions>
              <Button onClick={handleCancelEdit} disabled={editSaving}>
                Cancel
              </Button>
              <Button
                variant="contained"
                onClick={makeConfirmEdit(ctx.refresh)}
                disabled={editSaving}
              >
                {editSaving ? 'Saving…' : 'Save'}
              </Button>
            </DialogActions>
          </Dialog>
          <DeleteModal
            open={deleteTarget !== null}
            onClose={handleCancelDelete}
            onConfirm={makeConfirmDelete(ctx.refresh)}
            isLoading={deleting}
            title="Delete Annotation"
            itemType="annotation"
            message="Are you sure you want to delete this annotation? This action cannot be undone."
            confirmButtonText={deleting ? 'Deleting…' : 'Delete Annotation'}
          />
        </>
      )}
    />
  );
}
