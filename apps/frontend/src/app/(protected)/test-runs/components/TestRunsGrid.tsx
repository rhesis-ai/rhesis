'use client';

import React, { useState, useCallback, useContext, useMemo } from 'react';
import { useSession } from 'next-auth/react';
import { useQueryClient } from '@tanstack/react-query';
import { testRunKeys } from '@/constants/query-keys';
import { useBulkDelete } from '@/hooks/useBulkDelete';
import { useGridState } from '@/hooks/useGridState';
import { useGridQuery } from '@/hooks/useGridQuery';
import ListIcon from '@mui/icons-material/List';
import DeleteIcon from '@mui/icons-material/DeleteOutlined';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import GridBadge from '@/components/common/GridBadge';
import TagLabel from '@/components/common/Tag';
import {
  GridColDef,
  GridPaginationModel,
  GridFilterModel,
  GridRowParams,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid, { GRID_PAPER_SX } from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import {
  Typography,
  Box,
  Alert,
  Avatar,
  Chip,
  Button,
  ButtonGroup,
  Tooltip,
  Paper,
} from '@mui/material';
import {
  ChatIcon,
  DescriptionIcon,
  ScienceIcon,
  BiotechIcon,
  PlayArrowIcon,
} from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import PersonIcon from '@mui/icons-material/Person';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import { useNotifications } from '@/components/common/NotificationContext';
// Renamed on import: distinct from the toast system's useNotifications above --
// this one tracks the persistent "a background job finished" badge/highlight.
import { useNotifications as useJobNotifications } from '@/contexts/NotificationsContext';
import {
  HIGHLIGHTED_ROW_CLASS,
  NotificationSection,
} from '@/constants/notifications';
import { TestRun, TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { can } from '@/utils/affordances';
import { Capability } from '@/constants/capabilities';
import { Tag } from '@/utils/api-client/interfaces/tag';
import { DeleteModal } from '@/components/common/DeleteModal';
import { combineTestRunFiltersToOData } from '@/utils/odata-filter';
import {
  appendPresenceFilterItems,
  stripPresenceFilterItems,
} from '@/components/common/presence-filter';
import { gridSortToApiParams } from '@/utils/grid-sort';
import TestRunFilterDrawer, {
  type TestRunFilters,
  EMPTY_TEST_RUN_FILTERS,
  hasActiveTestRunFilters,
  countActiveTestRunFilters,
} from './TestRunFilterDrawer';
import {
  createRowActionsColumn,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import GridStateGate from '@/components/common/GridStateGate';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';

type RunKindFilter = 'all' | 'tests' | 'experiments';

interface TestRunsGridProps {
  canCreate?: boolean;
  onCreateClick?: () => void;
}

function formatReviewTooltip(reviewed: number, corrected: number): string {
  const reviewedLabel = `${reviewed} test${reviewed === 1 ? '' : 's'} reviewed`;
  if (corrected > 0) {
    return `${reviewedLabel} · ${corrected} corrected`;
  }
  return reviewedLabel;
}

// ── Status pill tabs ─────────────────────────────────────────────────────────

const STATUS_TABS = [
  { label: 'All', value: 'all' },
  { label: 'In Progress', value: 'Progress' },
  { label: 'Completed', value: 'Completed' },
  { label: 'Partial', value: 'Partial' },
  { label: 'Failed', value: 'Failed' },
];

// ── Toolbar context ──────────────────────────────────────────────────────────

interface TestRunsToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  statusFilter: string;
  setStatusFilter: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
  activeFilterCount: number;
}

const TestRunsToolbarContext = React.createContext<TestRunsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  statusFilter: 'all',
  setStatusFilter: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
});

function TestRunsUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
  } = useContext(TestRunsToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search test runs…"
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      activeFilterCount={activeFilterCount}
      middleContent={
        <ToolbarPillTabs
          tabs={STATUS_TABS}
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

// ── Grid component ────────────────────────────────────────────────────────────

function TestRunsGrid({ canCreate, onCreateClick }: TestRunsGridProps) {
  const { status } = useSession();
  const queryClient = useQueryClient();
  const router = useRouter();
  const notifications = useNotifications();
  const { highlightedIds, clearHighlight } = useJobNotifications();
  const testRunHighlights = highlightedIds(NotificationSection.TEST_RUNS);

  // ── Search + status filter ─────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  // ── Filter drawer state ────────────────────────────────────────────────────
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] = useState<TestRunFilters>(
    EMPTY_TEST_RUN_FILTERS
  );

  // ── Other UI state ─────────────────────────────────────────────────────────
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [pendingCancelId, setPendingCancelId] = useState<string | null>(null);
  const [runKindFilter, setRunKindFilter] = useState<RunKindFilter>('all');

  // ── Bulk selection + delete ──────────────────────────────────────────────────
  const {
    selectedRows,
    handleSelectionChange,
    pendingDeleteId,
    deleteModalOpen,
    isDeleting,
    requestDelete,
    confirmDelete,
    cancelDelete,
  } = useBulkDelete({
    bulkDeleteFn: (ids: string[]) =>
      new ApiClientFactory().getTestRunsClient().bulkDeleteTestRuns(ids),
    queryKey: testRunKeys.all(),
    itemLabelSingular: 'test run',
    itemLabelPlural: 'test runs',
    getSkippedCount: response => response.forbidden_ids.length,
    skippedReason: 'not yours to delete',
  });

  // ── Grid state (pagination, filter, sort) ─────────────────────────────────

  const applyDrawerFilters = useCallback(
    (prev: GridFilterModel): GridFilterModel => {
      const DRAWER_FIELDS = [
        'test_configuration.test_set.name',
        'user.name',
        'tags',
      ];
      const otherItems = stripPresenceFilterItems(
        prev.items.filter(item => !DRAWER_FIELDS.includes(item.field ?? ''))
      );
      const drawerItems: typeof prev.items = [];
      if (drawerFilters.testSet) {
        drawerItems.push({
          id: 'test_configuration.test_set.name',
          field: 'test_configuration.test_set.name',
          operator: 'contains',
          value: drawerFilters.testSet,
        });
      }
      if (drawerFilters.executor) {
        drawerItems.push({
          id: 'user.name',
          field: 'user.name',
          operator: 'contains',
          value: drawerFilters.executor,
        });
      }
      if (drawerFilters.tag) {
        drawerItems.push({
          id: 'tags',
          field: 'tags',
          operator: 'contains',
          value: drawerFilters.tag,
        });
      }
      const newItems = appendPresenceFilterItems(
        [...otherItems, ...drawerItems],
        {
          tags: drawerFilters.tags,
          comments: drawerFilters.comments,
          tasks: drawerFilters.tasks,
        }
      );
      return { ...prev, items: newItems };
    },
    [drawerFilters]
  );

  const {
    filterModel,
    gridFilterModel,
    paginationModel,
    sortModel,
    setPaginationModel,
    handlePaginationModelChange,
    handleFilterModelChange,
    handleSortModelChange,
  } = useGridState({
    searchQuery,
    typeFilter: statusFilter,
    typeFilterField: 'status.name',
    applyDrawerFilters,
    initialPageSize: 50,
  });

  // ── Data fetching ─────────────────────────────────────────────────────────

  const filterString = combineTestRunFiltersToOData(filterModel);
  const { sort_by, sort_order } = gridSortToApiParams(sortModel);

  const {
    data: testRunsData,
    isLoading: loading,
    errorMessage: error,
    dismissError,
  } = useGridQuery({
    queryKey: [
      ...testRunKeys.list(
        filterString,
        paginationModel.page,
        paginationModel.pageSize,
        sort_by,
        sort_order
      ),
      runKindFilter,
      drawerFilters.reviews,
    ],
    errorFallbackMessage: 'Failed to load test runs',
    queryFn: () => {
      const client = new ApiClientFactory().getTestRunsClient();
      return client.getTestRuns({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by,
        sort_order,
        ...(filterString && { filter: filterString }),
        ...(runKindFilter === 'experiments' && { has_experiment: true }),
        ...(runKindFilter === 'tests' && { has_experiment: false }),
        ...(drawerFilters.reviews === 'with' && { has_reviews: true }),
        ...(drawerFilters.reviews === 'without' && { has_reviews: false }),
      });
    },
    enabled: isAuthenticated(status),
    // Always refetch when the list is opened -- a run appears here as soon as
    // it's started, so cached-but-not-yet-stale data hides it. See the same
    // note in TestSetsGrid.
    staleTime: 0,
  });

  const testRuns = testRunsData?.data ?? [];
  const totalCount = testRunsData?.pagination.totalCount ?? 0;

  // ── Row action handlers ────────────────────────────────────────────────────

  const handleRowEditAction = useCallback(
    (id: string) => {
      router.push(`/test-runs/${id}`);
    },
    [router]
  );

  const handleRowCancelAction = useCallback((id: string) => {
    setPendingCancelId(id);
    setCancelModalOpen(true);
  }, []);

  const isCancellableRun = useCallback((row: Record<string, unknown>) => {
    const statusName = (
      (row.status as { name?: string } | undefined)?.name ?? ''
    ).toLowerCase();
    return statusName === 'queued' || statusName === 'progress';
  }, []);

  // ── Column definitions ────────────────────────────────────────────────────

  const columns: GridColDef[] = useMemo(() => {
    const actionsCol = createRowActionsColumn({
      onEdit: id => handleRowEditAction(id),
      canEdit: row => can(row as unknown as TestRun, Capability.TestRun.UPDATE),
      onCancel: id => handleRowCancelAction(id),
      canCancel: isCancellableRun,
      onDelete: id => requestDelete(id),
      canDelete: row =>
        can(row as unknown as TestRun, Capability.TestRun.DELETE),
      width: 112,
    });
    return [
      {
        field: 'name',
        headerName: 'Name',
        width: 180,
        minWidth: 120,
        resizable: true,
        filterable: true,
        valueGetter: (_, row) => row.name || '',
      },
      {
        field: 'test_configuration.test_set.name',
        headerName: 'Test Sets',
        width: 160,
        minWidth: 100,
        resizable: true,
        filterable: true,
        valueGetter: (_, row) => {
          const testSet = row.test_configuration?.test_set;
          return testSet?.name || '';
        },
      },
      {
        field: 'total_tests',
        headerName: 'Total Tests',
        width: 110,
        minWidth: 80,
        resizable: true,
        align: 'right',
        headerAlign: 'right',
        valueGetter: (_, row) => {
          const attributes = row?.attributes;
          return attributes?.total_tests || 0;
        },
      },
      {
        field: 'pass_rate',
        headerName: 'Pass Rate',
        width: 110,
        minWidth: 90,
        resizable: true,
        align: 'right',
        headerAlign: 'right',
        sortable: false,
        filterable: false,
        valueGetter: (_, row) => {
          const stats = row.stats;
          if (!stats || !stats.total) return null;
          return (stats.passed / stats.total) * 100;
        },
        renderCell: params => {
          const value = params.value as number | null;
          if (value === null || value === undefined) {
            return (
              <Typography variant="body2" color="text.secondary">
                —
              </Typography>
            );
          }
          return <Typography variant="body2">{value.toFixed(1)}%</Typography>;
        },
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        minWidth: 90,
        resizable: true,
        renderCell: params => {
          const status = params.row.status?.name;
          if (!status) return null;

          return <GridBadge label={status} />;
        },
      },
      {
        field: 'test_set_type',
        headerName: 'Type',
        width: 120,
        minWidth: 90,
        resizable: true,
        filterable: true,
        valueGetter: (_, row) => {
          return (
            row.test_configuration?.test_set?.test_set_type?.type_value || ''
          );
        },
        renderCell: params => {
          const testSetType =
            params.row.test_configuration?.test_set?.test_set_type?.type_value;

          if (!testSetType) return null;

          return <GridBadge label={testSetType} />;
        },
      },
      {
        field: 'experiment',
        headerName: 'Experiment',
        flex: 1,
        sortable: false,
        filterable: false,
        valueGetter: (_, row) => {
          if (!row.experiment_id) return '';
          const name =
            (row.attributes?.parameter_experiment_name as string) || '';
          const ver = (row.attributes?.parameter_version as string) || '';
          return `${name} ${ver}`.trim();
        },
        renderCell: params => {
          if (!params.row.experiment_id) return null;
          const name =
            (params.row.attributes?.parameter_experiment_name as string) ||
            undefined;
          const version = params.row.attributes?.parameter_version as
            | string
            | undefined;

          if (!name && !version) return null;

          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
              }}
            >
              {name && (
                <Typography
                  variant="body2"
                  sx={{ fontSize: theme => theme.typography.body2.fontSize }}
                  noWrap
                >
                  {name}
                </Typography>
              )}
              {version && (
                <Chip
                  label={version}
                  size="small"
                  variant="outlined"
                  sx={{ height: 20, '& .MuiChip-label': { px: 0.75 } }}
                />
              )}
            </Box>
          );
        },
      },
      {
        field: 'user.name',
        headerName: 'Executor',
        width: 160,
        minWidth: 120,
        resizable: true,
        filterable: true,
        valueGetter: (_, row) => {
          const executor = row.user;
          if (!executor) return '';
          return (
            executor.name ||
            `${executor.given_name || ''} ${executor.family_name || ''}`.trim() ||
            executor.email
          );
        },
        renderCell: params => {
          const executor = params.row.user;
          if (!executor) return null;

          const displayName =
            executor.name ||
            `${executor.given_name || ''} ${executor.family_name || ''}`.trim() ||
            executor.email;

          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Avatar src={executor.picture} sx={{ width: 24, height: 24 }}>
                <PersonIcon />
              </Avatar>
              <Typography variant="body2">{displayName}</Typography>
            </Box>
          );
        },
      },
      {
        field: 'counts.reviewed_tests',
        headerName: 'Reviews',
        width: 100,
        minWidth: 80,
        resizable: true,
        sortable: false,
        filterable: false,
        valueGetter: (_, row) => row.counts?.reviewed_tests ?? 0,
        renderCell: params => {
          const reviewed = params.row.counts?.reviewed_tests || 0;
          if (reviewed === 0) return null;

          const corrected = params.row.counts?.corrected_tests || 0;
          const iconColor = corrected > 0 ? 'primary.dark' : 'text.secondary';

          return (
            <Tooltip title={formatReviewTooltip(reviewed, corrected)}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  width: '100%',
                }}
              >
                <RateReviewOutlinedIcon
                  sx={{ fontSize: 16, color: iconColor }}
                />
                <Typography variant="body2">{reviewed}</Typography>
              </Box>
            </Tooltip>
          );
        },
      },
      {
        field: 'counts.comments',
        headerName: 'Comments',
        width: 100,
        minWidth: 80,
        resizable: true,
        sortable: true,
        filterable: false,
        valueGetter: (_, row) => row.counts?.comments ?? 0,
        renderCell: params => {
          const count = params.row.counts?.comments || 0;
          if (count === 0) return null;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <ChatIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
              <Typography variant="body2">{count}</Typography>
            </Box>
          );
        },
      },
      {
        field: 'counts.tasks',
        headerName: 'Tasks',
        width: 100,
        minWidth: 80,
        resizable: true,
        sortable: true,
        filterable: false,
        valueGetter: (_, row) => row.counts?.tasks ?? 0,
        renderCell: params => {
          const count = params.row.counts?.tasks || 0;
          if (count === 0) return null;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <DescriptionIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
              <Typography variant="body2">{count}</Typography>
            </Box>
          );
        },
      },
      {
        field: 'tags',
        headerName: 'Tags',
        width: 180,
        minWidth: 140,
        resizable: true,
        sortable: true,
        filterable: true,
        valueGetter: (_, row) =>
          row.tags?.filter((tag: Tag) => tag && tag.id && tag.name).length ?? 0,
        renderCell: params => {
          const testRun = params.row as TestRunDetail;
          if (!testRun.tags || testRun.tags.length === 0) {
            return null;
          }

          return (
            <Box
              sx={{
                display: 'flex',
                gap: 0.5,
                flexWrap: 'nowrap',
                overflow: 'hidden',
              }}
            >
              {testRun.tags
                .filter((tag: Tag) => tag && tag.id && tag.name)
                .slice(0, 2)
                .map((tag: Tag) => (
                  <TagLabel key={tag.id} label={tag.name} />
                ))}
              {testRun.tags.filter((tag: Tag) => tag && tag.id && tag.name)
                .length > 2 && (
                <TagLabel
                  label={`+${testRun.tags.filter((tag: Tag) => tag && tag.id && tag.name).length - 2}`}
                />
              )}
            </Box>
          );
        },
      },
      actionsCol,
    ];
  }, [
    handleRowEditAction,
    handleRowCancelAction,
    isCancellableRun,
    requestDelete,
  ]);

  // ── Row handlers ──────────────────────────────────────────────────────────

  const handleRowClick = useCallback(
    (params: { id: string | number }) => {
      clearHighlight(NotificationSection.TEST_RUNS, String(params.id));
      router.push(`/test-runs/${params.id}`);
    },
    [router, clearHighlight]
  );

  // ── Cancel handlers ───────────────────────────────────────────────────────

  const handleCancelConfirm = useCallback(async () => {
    if (!pendingCancelId) {
      setCancelModalOpen(false);
      return;
    }

    try {
      setIsCancelling(true);
      const clientFactory = new ApiClientFactory();
      const testRunsClient = clientFactory.getTestRunsClient();
      await testRunsClient.cancelTestRun(pendingCancelId);
      notifications.show('Successfully cancelled test run', {
        severity: 'success',
      });
      setPendingCancelId(null);
      queryClient.invalidateQueries({ queryKey: testRunKeys.all() });
    } catch (_error) {
      notifications.show('Failed to cancel test run', { severity: 'error' });
    } finally {
      setIsCancelling(false);
      setCancelModalOpen(false);
    }
  }, [pendingCancelId, notifications, queryClient]);

  const handleCancelClose = useCallback(() => {
    setCancelModalOpen(false);
    setPendingCancelId(null);
  }, []);

  const handleRunKindFilterChange = useCallback(
    (value: RunKindFilter) => {
      setRunKindFilter(value);
      setPaginationModel(prev => ({ ...prev, page: 0 }));
    },
    [setPaginationModel]
  );

  const getActionButtons = useCallback(() => {
    if (selectedRows.length === 0) return [];

    return [
      {
        label: 'Delete',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: () => requestDelete(),
      },
    ];
  }, [selectedRows.length, requestDelete]);

  const runKindToolbar = useMemo(
    () => (
      <ButtonGroup size="small" variant="outlined">
        <Button
          onClick={() => handleRunKindFilterChange('all')}
          variant={runKindFilter === 'all' ? 'contained' : 'outlined'}
          startIcon={<ListIcon fontSize="small" />}
        >
          All
        </Button>
        <Button
          onClick={() => handleRunKindFilterChange('tests')}
          variant={runKindFilter === 'tests' ? 'contained' : 'outlined'}
          startIcon={<ScienceIcon fontSize="small" />}
        >
          Tests
        </Button>
        <Button
          onClick={() => handleRunKindFilterChange('experiments')}
          variant={runKindFilter === 'experiments' ? 'contained' : 'outlined'}
          startIcon={<BiotechIcon fontSize="small" />}
        >
          Experiments
        </Button>
      </ButtonGroup>
    ),
    [runKindFilter, handleRunKindFilterChange]
  );

  const filtersActive =
    filterModel.items.length > 0 ||
    !!searchQuery ||
    hasActiveTestRunFilters(drawerFilters);

  return (
    <GridStateGate
      data={testRunsData}
      error={error}
      isEmpty={totalCount === 0 && !filtersActive}
      emptyState={
        <EntityEmptyState
          card
          icon={PlayArrowIcon}
          title="No test runs yet"
          description="Execute a test set against an AI endpoint to start your first test run. Test runs measure quality, safety, and reliability of your AI endpoints."
          actionLabel={canCreate ? 'Create test run' : undefined}
          onAction={canCreate ? onCreateClick : undefined}
          enrichment={getEntityEmptyStateEnrichment('test-runs')}
        />
      }
    >
      <Paper sx={GRID_PAPER_SX}>
        <TestRunsToolbarContext.Provider
          value={{
            searchQuery,
            setSearchQuery,
            statusFilter,
            setStatusFilter,
            openFilterDrawer: () => setFilterDrawerOpen(true),
            hasActiveDrawerFilters: hasActiveTestRunFilters(drawerFilters),
            activeFilterCount: countActiveTestRunFilters(drawerFilters),
          }}
        >
          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={dismissError}>
              {error}
            </Alert>
          )}

          <BaseDataGrid
            rows={testRuns}
            columns={columns}
            loading={loading}
            getRowId={row => row.id}
            paginationModel={paginationModel}
            onPaginationModelChange={handlePaginationModelChange}
            filterModel={gridFilterModel}
            onFilterModelChange={handleFilterModelChange}
            sortingMode="server"
            sortModel={sortModel}
            onSortModelChange={handleSortModelChange}
            serverSideFiltering={true}
            onRowClick={handleRowClick}
            getRowClassName={params =>
              testRunHighlights.includes(String(params.id))
                ? HIGHLIGHTED_ROW_CLASS
                : ''
            }
            getRowUrl={row => `/test-runs/${row.id}`}
            serverSidePagination={true}
            totalRows={totalCount}
            pageSizeOptions={[10, 25, 50]}
            gridToolbarExtra={runKindToolbar}
            actionButtons={getActionButtons()}
            disablePaperWrapper={true}
            showToolbar={true}
            toolbarSlot={TestRunsUnifiedToolbar}
            persistState
            storageKey="test-runs-grid-v2"
            sx={rowActionsHoverSx}
            checkboxSelection
            disableRowSelectionOnClick
            isRowSelectable={(params: GridRowParams) =>
              can(params.row as unknown as TestRun, Capability.TestRun.DELETE)
            }
            rowSelectionModel={selectedRows}
            onRowSelectionModelChange={handleSelectionChange}
          />

          <DeleteModal
            open={deleteModalOpen}
            onClose={cancelDelete}
            onConfirm={confirmDelete}
            isLoading={isDeleting}
            title={pendingDeleteId ? 'Delete Test Run' : 'Delete Test Runs'}
            message={
              pendingDeleteId
                ? 'Are you sure you want to delete this test run? Related data will not be deleted.'
                : `Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'test run' : 'test runs'}? Related data will not be deleted.`
            }
            itemType="test runs"
          />

          <DeleteModal
            open={cancelModalOpen}
            onClose={handleCancelClose}
            onConfirm={handleCancelConfirm}
            isLoading={isCancelling}
            title="Cancel Test Run"
            message="Are you sure you want to cancel this test run? It will be stopped and marked as Cancelled."
            itemType="test run"
            confirmButtonText={isCancelling ? 'Cancelling...' : 'Cancel Run'}
            cancelButtonText="Keep Running"
          />

          {/* Filter drawer */}
          <TestRunFilterDrawer
            open={filterDrawerOpen}
            onClose={() => setFilterDrawerOpen(false)}
            filters={drawerFilters}
            onApply={f => {
              setDrawerFilters(f);
            }}
          />
        </TestRunsToolbarContext.Provider>
      </Paper>
    </GridStateGate>
  );
}

export default React.memo(TestRunsGrid);
