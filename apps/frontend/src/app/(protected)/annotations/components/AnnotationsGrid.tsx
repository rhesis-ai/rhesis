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
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { DeleteIcon } from '@/components/icons';
import {
  AnnotationListItem,
  AnnotationSource,
  ANNOTATION_SOURCE_LABELS,
  ANNOTATION_TARGET_LABELS,
} from '@/utils/api-client/interfaces/annotation';
import { annotationsList } from './list';
import { isPassedStatusName } from '@/utils/test-result-status';
import AnnotationFilterDrawer, {
  type AnnotationFilters,
  EMPTY_ANNOTATION_FILTERS,
  countActiveAnnotationFilters,
} from './AnnotationFilterDrawer';

/**
 * Annotations are flattened reviews from test results and traces, not their
 * own entity -- edit/delete route to the review sub-resource on whichever
 * parent the row came from.
 */
function updateAnnotationReview(
  factory: ApiClientFactory,
  row: AnnotationListItem,
  updates: { comments?: string; resolved?: boolean }
) {
  if (row.source === 'test_result' && row.test_result_id) {
    return factory
      .getTestResultsClient()
      .updateReview(row.test_result_id, row.review_id, updates);
  }
  if (row.source === 'trace' && row.trace_db_id) {
    return factory
      .getTelemetryClient()
      .updateReview(row.trace_db_id, row.review_id, updates);
  }
  return Promise.reject(new Error('Annotation is missing its parent id.'));
}

function deleteAnnotationReview(
  factory: ApiClientFactory,
  row: AnnotationListItem
) {
  if (row.source === 'test_result' && row.test_result_id) {
    return factory
      .getTestResultsClient()
      .deleteReview(row.test_result_id, row.review_id);
  }
  if (row.source === 'trace' && row.trace_db_id) {
    return factory
      .getTelemetryClient()
      .deleteReview(row.trace_db_id, row.review_id);
  }
  return Promise.reject(new Error('Annotation is missing its parent id.'));
}

interface AnnotationsGridProps {
  onTotalCountChange?: (count: number) => void;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: AnnotationListItem[];
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
    source: state.drawer.source,
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

function formatTarget(item: AnnotationListItem): string {
  const type = item.target?.type || '';
  const label = ANNOTATION_TARGET_LABELS[type] || type || '—';
  if (item.target?.reference) {
    return `${label}: ${item.target.reference}`;
  }
  return label;
}

// Rows carry a synthesized id: an annotation is a (source, review) pair, not
// an entity with its own id.
function mapRows(annotations: AnnotationListItem[]) {
  return annotations.map(item => ({
    ...item,
    id: `${item.source}-${item.review_id}`,
  }));
}

export default function AnnotationsGrid({
  onTotalCountChange,
  initialData,
  initialTotalCount,
}: AnnotationsGridProps) {
  const theme = useTheme();
  const notifications = useNotifications();

  const canUpdateTestResult = useCan(Capability.TestResult.UPDATE);
  const canDeleteTestResult = useCan(Capability.TestResult.DELETE);
  const canUpdateTrace = useCan(Capability.Telemetry.UPDATE);
  const canDeleteTrace = useCan(Capability.Telemetry.DELETE);

  const canEditRow = useCallback(
    (row: AnnotationListItem) =>
      row.source === 'test_result' ? canUpdateTestResult : canUpdateTrace,
    [canUpdateTestResult, canUpdateTrace]
  );
  const canDeleteRow = useCallback(
    (row: AnnotationListItem) =>
      row.source === 'test_result' ? canDeleteTestResult : canDeleteTrace,
    [canDeleteTestResult, canDeleteTrace]
  );

  const [editTarget, setEditTarget] = useState<AnnotationListItem | null>(null);
  const [editComments, setEditComments] = useState('');
  const [editResolved, setEditResolved] = useState(false);
  const [editSaving, setEditSaving] = useState(false);

  const handleEditClick = useCallback((row: AnnotationListItem) => {
    setEditTarget(row);
    setEditComments(row.comments);
    setEditResolved(Boolean(row.resolved));
  }, []);

  const handleCancelEdit = useCallback(() => setEditTarget(null), []);

  const makeConfirmEdit = useCallback(
    (refresh: () => void) => async () => {
      if (!editTarget) return;
      try {
        setEditSaving(true);
        const factory = new ApiClientFactory();
        await updateAnnotationReview(factory, editTarget, {
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

  const [deleteTarget, setDeleteTarget] = useState<AnnotationListItem | null>(
    null
  );
  const [deleting, setDeleting] = useState(false);

  const handleDeleteClick = useCallback((row: AnnotationListItem) => {
    setDeleteTarget(row);
  }, []);

  const handleCancelDelete = useCallback(() => setDeleteTarget(null), []);

  const makeConfirmDelete = useCallback(
    (refresh: () => void) => async () => {
      if (!deleteTarget) return;
      try {
        setDeleting(true);
        const factory = new ApiClientFactory();
        await deleteAnnotationReview(factory, deleteTarget);
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
          handleDeleteClick(row as unknown as AnnotationListItem),
        can: (row: Record<string, unknown>) =>
          canDeleteRow(row as unknown as AnnotationListItem),
        hoverColor: 'error.main' as const,
      },
    ],
    [handleDeleteClick, canDeleteRow]
  );

  const onTotalCountChangeRef = useRef(onTotalCountChange);
  onTotalCountChangeRef.current = onTotalCountChange;
  const handleDataChange = useCallback(
    (
      _data: AnnotationListItem[],
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
        field: 'source',
        headerName: 'Type',
        flex: 1.4,
        sortable: false,
        valueGetter: (_value, row) =>
          ANNOTATION_SOURCE_LABELS[row.source as AnnotationSource] ||
          row.source,
      },
      {
        field: 'target',
        headerName: 'Target',
        flex: 1,
        minWidth: 160,
        sortable: false,
        valueGetter: (_value, row) => formatTarget(row as AnnotationListItem),
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
          (row as AnnotationListItem).requirement_name || '',
        renderCell: params => {
          const name = (params.row as AnnotationListItem).requirement_name;
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

  // Annotations live on other entities — a click opens the review where it
  // was made, in a new tab so the annotations list isn't lost.
  const handleRowClick = useCallback((params: GridRowParams) => {
    const row = params.row as AnnotationListItem;
    let url: string | null = null;
    if (row.source === 'test_result' && row.test_run_id && row.test_result_id) {
      url =
        `/test-runs/${encodeURIComponent(row.test_run_id)}` +
        `?selectedresult=${encodeURIComponent(row.test_result_id)}` +
        `&detailTab=reviews`;
    } else if (row.source === 'trace' && row.trace_id && row.project_id) {
      url =
        `/traces?open_trace=${encodeURIComponent(row.trace_id)}` +
        `&project_id=${encodeURIComponent(row.project_id)}`;
    }
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  }, []);

  return (
    <EntityGrid<
      AnnotationListItem,
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
      mapRows={mapRows}
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
