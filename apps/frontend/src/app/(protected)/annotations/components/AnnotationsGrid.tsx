'use client';

import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  GridColDef,
  GridPaginationModel,
  GridRowParams,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import { Alert, Box, Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import GridBadge from '@/components/common/GridBadge';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { MentionText } from '@/components/common/MentionTextInput';
import {
  AnnotationListItem,
  AnnotationSource,
  ANNOTATION_SOURCE_LABELS,
  ANNOTATION_TARGET_LABELS,
} from '@/utils/api-client/interfaces/annotation';
import { annotationKeys } from '@/constants/query-keys';
import { useGridQuery } from '@/hooks/useGridQuery';
import { isPassedStatusName } from '@/utils/test-result-status';
import AnnotationFilterDrawer, {
  type AnnotationFilters,
  EMPTY_ANNOTATION_FILTERS,
  hasActiveAnnotationFilters,
  countActiveAnnotationFilters,
} from './AnnotationFilterDrawer';

interface AnnotationsGridProps {
  sessionToken: string;
  onTotalCountChange?: (count: number) => void;
}

const STATUS_PILL_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Open', value: 'open' },
  { label: 'Resolved', value: 'resolved' },
] as const;

interface AnnotationsToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  statusFilter: string;
  setStatusFilter: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
  activeFilterCount: number;
}

const AnnotationsToolbarContext = React.createContext<AnnotationsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  statusFilter: 'all',
  setStatusFilter: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
});

function AnnotationsUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
  } = useContext(AnnotationsToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search annotations…"
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      activeFilterCount={activeFilterCount}
      middleContent={
        <ToolbarPillTabs
          tabs={[...STATUS_PILL_TABS]}
          activeValue={statusFilter}
          onChange={setStatusFilter}
        />
      }
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

function formatTarget(item: AnnotationListItem): string {
  const type = item.target?.type || '';
  const label = ANNOTATION_TARGET_LABELS[type] || type || '—';
  if (item.target?.reference) {
    return `${label}: ${item.target.reference}`;
  }
  return label;
}

export default function AnnotationsGrid({
  sessionToken,
  onTotalCountChange,
}: AnnotationsGridProps) {
  const theme = useTheme();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] = useState<AnnotationFilters>(
    EMPTY_ANNOTATION_FILTERS
  );
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });

  useEffect(() => {
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [statusFilter, searchQuery, drawerFilters]);

  const searchParam = searchQuery.trim() || undefined;
  const resolvedParam =
    statusFilter === 'resolved'
      ? true
      : statusFilter === 'open'
        ? false
        : undefined;
  const sourceParam = drawerFilters.source || undefined;
  const ratingParam = drawerFilters.rating || undefined;
  const targetTypeParam = drawerFilters.target_type || undefined;

  const filterKey = [
    sourceParam || '',
    searchParam || '',
    resolvedParam === undefined ? '' : String(resolvedParam),
    ratingParam || '',
    targetTypeParam || '',
  ].join('|');

  const {
    data: annotationsData,
    isLoading: loading,
    errorMessage: error,
    dismissError,
  } = useGridQuery({
    queryKey: annotationKeys.list(
      filterKey,
      paginationModel.page,
      paginationModel.pageSize
    ),
    errorFallbackMessage: 'Failed to load annotations',
    queryFn: () => {
      const client = new ApiClientFactory(sessionToken).getAnnotationsClient();
      return client.getAnnotations({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        ...(sourceParam && { source: sourceParam }),
        ...(searchParam && { search: searchParam }),
        ...(resolvedParam !== undefined && { resolved: resolvedParam }),
        ...(ratingParam && { rating: ratingParam }),
        ...(targetTypeParam && { target_type: targetTypeParam }),
      });
    },
    enabled: !!sessionToken,
    staleTime: 0,
  });

  const annotations: AnnotationListItem[] = annotationsData?.data ?? [];
  const totalCount = annotationsData?.totalCount ?? 0;

  useEffect(() => {
    if (!annotationsData) return;
    const filtersActive =
      !!searchParam ||
      statusFilter !== 'all' ||
      hasActiveAnnotationFilters(drawerFilters);
    if (!filtersActive) {
      onTotalCountChange?.(totalCount);
    }
  }, [
    annotationsData,
    onTotalCountChange,
    searchParam,
    statusFilter,
    drawerFilters,
    totalCount,
  ]);

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
        field: 'behavior_name',
        headerName: 'Behavior',
        flex: 1,
        minWidth: 140,
        sortable: false,
        valueGetter: (_value, row) =>
          (row as AnnotationListItem).behavior_name || '',
        renderCell: params => {
          const name = (params.row as AnnotationListItem).behavior_name;
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

  const toolbarState = useMemo(
    () => ({
      searchQuery,
      setSearchQuery,
      statusFilter,
      setStatusFilter,
      openFilterDrawer: () => setFilterDrawerOpen(true),
      hasActiveDrawerFilters: hasActiveAnnotationFilters(drawerFilters),
      activeFilterCount: countActiveAnnotationFilters(drawerFilters),
    }),
    [searchQuery, statusFilter, drawerFilters]
  );

  const rows = useMemo(
    () =>
      annotations.map(item => ({
        ...item,
        id: `${item.source}-${item.review_id}`,
      })),
    [annotations]
  );

  return (
    <AnnotationsToolbarContext.Provider value={toolbarState}>
      <Box>
        {error && (
          <Alert severity="error" onClose={dismissError} sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <BaseDataGrid
          rows={rows}
          columns={columns}
          loading={loading}
          getRowId={row => row.id}
          onRowClick={handleRowClick}
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          serverSidePagination={true}
          totalRows={totalCount}
          pageSizeOptions={[10, 25, 50]}
          showToolbar={true}
          toolbarSlot={AnnotationsUnifiedToolbar}
          disablePaperWrapper={true}
          disableRowSelectionOnClick
          sx={{
            '& .MuiDataGrid-row': {
              cursor: 'pointer',
            },
          }}
        />
        <AnnotationFilterDrawer
          open={filterDrawerOpen}
          onClose={() => setFilterDrawerOpen(false)}
          filters={drawerFilters}
          onApply={setDrawerFilters}
        />
      </Box>
    </AnnotationsToolbarContext.Provider>
  );
}
