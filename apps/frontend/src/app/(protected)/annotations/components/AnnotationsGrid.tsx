'use client';

import React, { useCallback, useMemo, useRef, useState } from 'react';
import { GridColDef, GridRowParams } from '@mui/x-data-grid';
import { Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import { MentionText } from '@/components/common/MentionTextInput';
import { can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import {
  Annotation,
  ANNOTATION_ENTITY_LABELS,
  ANNOTATION_ENTITY_TYPES,
  ANNOTATION_TARGET_LABELS,
} from '@/utils/api-client/interfaces/annotation';
import AnnotationDrawer from '@/components/annotations/AnnotationDrawer';
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
    testSetId: state.drawer.test_set_id,
    endpointId: state.drawer.endpoint_id,
    metric: state.drawer.metric,
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

  // Per-row affordances now arrive on the row itself, so no ambient gate and
  // no branching on which parent the annotation hangs off.
  const canEditRow = useCallback(
    (row: Annotation) => can(row, Capability.Annotation.UPDATE),
    []
  );

  const [editTarget, setEditTarget] = useState<Annotation | null>(null);

  const handleEditClick = useCallback(
    (row: Annotation) => setEditTarget(row),
    []
  );

  const handleCancelEdit = useCallback(() => setEditTarget(null), []);

  const onTotalCountChangeRef = useRef(onTotalCountChange);
  onTotalCountChangeRef.current = onTotalCountChange;
  const handleDataChange = useCallback(
    (_data: Annotation[], totalCount: number, filtersActive: boolean) => {
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
    } else if (
      row.entity_type === 'Trace' &&
      ctx?.trace_id &&
      ctx?.project_id
    ) {
      url =
        `/traces?open_trace=${encodeURIComponent(ctx.trace_id)}` +
        `&project_id=${encodeURIComponent(ctx.project_id)}`;
    }
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  }, []);

  return (
    <EntityGrid<Annotation, typeof annotationsList.filters, AnnotationFilters>
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
      persistState={false}
      serverSort={false}
      pageSizeOptions={[10, 25, 50]}
      sx={{ '& .MuiDataGrid-row': { cursor: 'pointer' } }}
      renderSelectionExtras={ctx => (
        <AnnotationDrawer
          open={editTarget !== null}
          onClose={handleCancelEdit}
          entityType={
            editTarget?.entity_type ?? ANNOTATION_ENTITY_TYPES.TEST_RESULT
          }
          entityId={editTarget?.entity_id}
          annotation={editTarget}
          onSaved={() => {
            setEditTarget(null);
            ctx.refresh();
          }}
        />
      )}
    />
  );
}
