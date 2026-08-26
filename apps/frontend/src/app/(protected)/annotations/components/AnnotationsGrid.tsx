'use client';

import React, { useCallback, useMemo, useRef } from 'react';
import { GridColDef, GridRowParams } from '@mui/x-data-grid';
import { Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import { MentionText } from '@/components/common/MentionTextInput';
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
        width: 140,
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
        width: 120,
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
        width: 160,
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
        width: 120,
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
      editAction={false}
      persistState={false}
      serverSort={false}
      pageSizeOptions={[10, 25, 50]}
      sx={{ '& .MuiDataGrid-row': { cursor: 'pointer' } }}
    />
  );
}
