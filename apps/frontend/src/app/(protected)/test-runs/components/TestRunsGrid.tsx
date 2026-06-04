'use client';

import React, {
  useEffect,
  useState,
  useCallback,
  useContext,
  useRef,
  useMemo,
} from 'react';
import DeleteIcon from '@mui/icons-material/Delete';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import ListIcon from '@mui/icons-material/List';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import GridBadge from '@/components/common/GridBadge';
import TagLabel from '@/components/common/Tag';
import {
  GridColDef,
  GridRowSelectionModel,
  GridPaginationModel,
  GridFilterModel,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import {
  Typography,
  Box,
  Alert,
  Avatar,
  Chip,
  Button,
  ButtonGroup,
} from '@mui/material';
import {
  ChatIcon,
  DescriptionIcon,
  ScienceIcon,
  BiotechIcon,
} from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import PersonIcon from '@mui/icons-material/Person';
import { useNotifications } from '@/components/common/NotificationContext';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { Tag } from '@/utils/api-client/interfaces/tag';
import { DeleteModal } from '@/components/common/DeleteModal';
import { combineTestRunFiltersToOData } from '@/utils/odata-filter';
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

type RunKindFilter = 'all' | 'tests' | 'experiments';

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

interface TestRunsGridProps {
  sessionToken: string;
  onRefresh?: () => void;
  onTotalCountChange?: (count: number) => void;
  refreshKey?: number;
}

function TestRunsGrid({
  sessionToken,
  onRefresh,
  onTotalCountChange,
  refreshKey,
}: TestRunsGridProps) {
  const isMounted = useRef(false);
  const router = useRouter();
  const notifications = useNotifications();

  // ── Search + status filter ─────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  // ── Core grid state ────────────────────────────────────────────────────────
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [testRuns, setTestRuns] = useState<TestRunDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [runKindFilter, setRunKindFilter] = useState<RunKindFilter>('all');
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 50,
  });
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });

  // ── Filter drawer state ────────────────────────────────────────────────────
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] = useState<TestRunFilters>(
    EMPTY_TEST_RUN_FILTERS
  );

  // ── Data fetching ─────────────────────────────────────────────────────────

  const fetchTestRuns = useCallback(
    async (skip: number, limit: number) => {
      if (!sessionToken) return;

      try {
        if (isMounted.current) {
          setLoading(true);
        }

        const clientFactory = new ApiClientFactory(sessionToken);
        const testRunsClient = clientFactory.getTestRunsClient();

        const filterString = combineTestRunFiltersToOData(filterModel);

        const apiParams: Parameters<typeof testRunsClient.getTestRuns>[0] = {
          skip,
          limit,
          sort_by: 'created_at',
          sort_order: 'desc' as const,
          ...(filterString && { filter: filterString }),
          ...(runKindFilter === 'experiments' && { has_experiment: true }),
          ...(runKindFilter === 'tests' && { has_experiment: false }),
        };

        const response = await testRunsClient.getTestRuns(apiParams);

        if (isMounted.current) {
          setTestRuns(response.data);
          setTotalCount(response.pagination.totalCount);
          onTotalCountChange?.(response.pagination.totalCount);
          setError(null);
        }
      } catch (_error) {
        if (isMounted.current) {
          setError('Failed to load test runs');
          setTestRuns([]);
        }
      } finally {
        if (isMounted.current) {
          setLoading(false);
        }
      }
    },
    [sessionToken, filterModel, runKindFilter, onTotalCountChange]
  );

  useEffect(() => {
    isMounted.current = true;
    const skip = paginationModel.page * paginationModel.pageSize;
    fetchTestRuns(skip, paginationModel.pageSize);
    return () => {
      isMounted.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionToken, paginationModel, filterModel, runKindFilter]);

  // Refetch when parent signals a refresh
  useEffect(() => {
    if (refreshKey !== undefined && refreshKey > 0) {
      const skip = paginationModel.page * paginationModel.pageSize;
      fetchTestRuns(skip, paginationModel.pageSize);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  // ── Sync searchQuery into filterModel ────────────────────────────────────

  useEffect(() => {
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => item.field !== 'quickFilter'
      );
      const items = searchQuery
        ? [
            ...otherItems,
            { field: 'quickFilter', operator: 'contains', value: searchQuery },
          ]
        : otherItems;
      return { ...prev, items };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [searchQuery]);

  // ── Sync statusFilter pill tab into filterModel ───────────────────────────

  useEffect(() => {
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => item.field !== 'status.name'
      );
      const items =
        statusFilter && statusFilter !== 'all'
          ? [
              ...otherItems,
              {
                field: 'status.name',
                operator: 'equals',
                value: statusFilter,
              },
            ]
          : otherItems;
      return { ...prev, items };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [statusFilter]);

  // ── Sync drawer filters into filterModel ─────────────────────────────────

  useEffect(() => {
    const DRAWER_FIELDS = [
      'test_configuration.test_set.name',
      'user.name',
      'tags',
    ];
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => !DRAWER_FIELDS.includes(item.field ?? '')
      );
      const drawerItems: typeof prev.items = [];
      if (drawerFilters.testSet) {
        drawerItems.push({
          field: 'test_configuration.test_set.name',
          operator: 'contains',
          value: drawerFilters.testSet,
        });
      }
      if (drawerFilters.executor) {
        drawerItems.push({
          field: 'user.name',
          operator: 'contains',
          value: drawerFilters.executor,
        });
      }
      if (drawerFilters.tag) {
        drawerItems.push({
          field: 'tags',
          operator: 'contains',
          value: drawerFilters.tag,
        });
      }
      return { ...prev, items: [...otherItems, ...drawerItems] };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [drawerFilters]);

  // ── Row action handlers ────────────────────────────────────────────────────

  const handleRowDeleteAction = useCallback((id: string) => {
    setPendingDeleteId(id);
    setDeleteModalOpen(true);
  }, []);

  const handleRowEditAction = useCallback(
    (id: string) => {
      router.push(`/test-runs/${id}`);
    },
    [router]
  );

  // ── Column definitions ────────────────────────────────────────────────────

  const columns: GridColDef[] = useMemo(() => {
    const actionsCol = createRowActionsColumn({
      onEdit: id => handleRowEditAction(id),
      onDelete: id => handleRowDeleteAction(id),
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
        field: 'counts.comments',
        headerName: 'Comments',
        width: 100,
        minWidth: 80,
        resizable: true,
        sortable: false,
        filterable: false,
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
        sortable: false,
        filterable: false,
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
        sortable: false,
        filterable: true,
        valueGetter: (_, row) => {
          if (!row.tags || !Array.isArray(row.tags)) {
            return '';
          }
          return row.tags
            .filter((tag: Tag) => tag && tag.name)
            .map((tag: Tag) => tag.name)
            .join(', ');
        },
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
  }, [handleRowEditAction, handleRowDeleteAction]);

  // ── Row handlers ──────────────────────────────────────────────────────────

  const handleRowClick = useCallback(
    (params: { id: string | number }) => {
      router.push(`/test-runs/${params.id}`);
    },
    [router]
  );

  const handleSelectionChange = useCallback(
    (newSelection: GridRowSelectionModel) => {
      setSelectedRows(newSelection);
    },
    []
  );

  const handlePaginationModelChange = useCallback(
    (model: GridPaginationModel) => {
      setPaginationModel(model);
      const skip = model.page * model.pageSize;
      fetchTestRuns(skip, model.pageSize);
    },
    [fetchTestRuns]
  );

  const handleFilterModelChange = useCallback(
    (newFilterModel: GridFilterModel) => {
      setFilterModel(newFilterModel);
      setPaginationModel(prev => ({ ...prev, page: 0 }));
    },
    []
  );

  // ── Delete handlers ───────────────────────────────────────────────────────

  const handleDeleteSelected = useCallback(() => {
    const validSelectedRows = Array.isArray(selectedRows) ? selectedRows : [];
    if (validSelectedRows.length === 0) return;
    setDeleteModalOpen(true);
  }, [selectedRows]);

  const handleDeleteConfirm = useCallback(async () => {
    const idsToDelete = pendingDeleteId
      ? [pendingDeleteId]
      : Array.isArray(selectedRows)
        ? selectedRows.map(String)
        : [];
    if (idsToDelete.length === 0) return;

    try {
      setIsDeleting(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testRunsClient = clientFactory.getTestRunsClient();

      await Promise.all(
        idsToDelete.map(id => testRunsClient.deleteTestRun(id))
      );

      notifications.show(
        `Successfully deleted ${idsToDelete.length} test run${idsToDelete.length === 1 ? '' : 's'}`,
        { severity: 'success' }
      );

      setPendingDeleteId(null);
      const skip = paginationModel.page * paginationModel.pageSize;
      await fetchTestRuns(skip, paginationModel.pageSize);
      setSelectedRows([]);
    } catch (_error) {
      notifications.show('Failed to delete test runs', { severity: 'error' });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  }, [
    pendingDeleteId,
    selectedRows,
    sessionToken,
    notifications,
    paginationModel,
    fetchTestRuns,
  ]);

  const handleDeleteCancel = useCallback(() => {
    setDeleteModalOpen(false);
    setPendingDeleteId(null);
  }, []);

  // ── Cancel handlers ───────────────────────────────────────────────────────

  const cancellableSelectedRuns = useMemo(() => {
    const validSelectedRows = Array.isArray(selectedRows) ? selectedRows : [];
    return testRuns.filter(run => {
      const status = run.status?.name?.toLowerCase();
      return (
        validSelectedRows.includes(run.id) &&
        (status === 'queued' || status === 'progress')
      );
    });
  }, [selectedRows, testRuns]);

  const handleCancelSelected = useCallback(() => {
    setCancelModalOpen(true);
  }, []);

  const handleCancelConfirm = useCallback(async () => {
    const ids = cancellableSelectedRuns.map(run => run.id.toString());

    if (ids.length === 0) {
      setCancelModalOpen(false);
      return;
    }

    try {
      setIsCancelling(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testRunsClient = clientFactory.getTestRunsClient();
      await Promise.all(ids.map(id => testRunsClient.cancelTestRun(id)));
      notifications.show(
        `Successfully cancelled ${ids.length} test run${ids.length === 1 ? '' : 's'}`,
        { severity: 'success' }
      );
      const skip = paginationModel.page * paginationModel.pageSize;
      await fetchTestRuns(skip, paginationModel.pageSize);
      setSelectedRows([]);
      onRefresh?.();
    } catch (_error) {
      notifications.show('Failed to cancel test runs', { severity: 'error' });
    } finally {
      setIsCancelling(false);
      setCancelModalOpen(false);
    }
  }, [
    cancellableSelectedRuns,
    sessionToken,
    notifications,
    paginationModel,
    fetchTestRuns,
    onRefresh,
  ]);

  const handleCancelClose = useCallback(() => {
    setCancelModalOpen(false);
  }, []);

  const handleRunKindFilterChange = useCallback((value: RunKindFilter) => {
    setRunKindFilter(value);
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, []);

  const actionButtons = useMemo(() => {
    const buttons = [];
    const validSelectedRows = Array.isArray(selectedRows) ? selectedRows : [];

    if (cancellableSelectedRuns.length > 0) {
      buttons.push({
        label: `Cancel Test Run${cancellableSelectedRuns.length === 1 ? '' : 's'}`,
        icon: <StopCircleOutlinedIcon />,
        variant: 'outlined' as const,
        color: 'warning' as const,
        onClick: handleCancelSelected,
      });
    }

    if (validSelectedRows.length > 0) {
      buttons.push({
        label: 'Delete Test Runs',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteSelected,
      });
    }

    return buttons;
  }, [
    selectedRows,
    cancellableSelectedRuns,
    handleCancelSelected,
    handleDeleteSelected,
  ]);

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

  return (
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
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {Array.isArray(selectedRows) && selectedRows.length > 0 && (
        <Box
          sx={{
            px: 2,
            py: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 2,
            borderBottom: theme =>
              `1px solid ${theme.palette.greyscale.border}`,
          }}
        >
          <Typography variant="subtitle1" color="primary">
            {selectedRows.length} selected
          </Typography>
        </Box>
      )}

      <BaseDataGrid
        rows={testRuns}
        columns={columns}
        loading={loading}
        getRowId={row => row.id}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        filterModel={filterModel}
        onFilterModelChange={handleFilterModelChange}
        serverSideFiltering={true}
        onRowSelectionModelChange={handleSelectionChange}
        rowSelectionModel={Array.isArray(selectedRows) ? selectedRows : []}
        onRowClick={handleRowClick}
        getRowUrl={row => `/test-runs/${row.id}`}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        checkboxSelection
        disableRowSelectionOnClick
        actionButtons={actionButtons}
        gridToolbarExtra={runKindToolbar}
        disablePaperWrapper={true}
        showToolbar={true}
        toolbarSlot={TestRunsUnifiedToolbar}
        persistState
        sx={rowActionsHoverSx}
      />

      <DeleteModal
        open={deleteModalOpen}
        onClose={handleDeleteCancel}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        title={pendingDeleteId ? 'Delete Test Run' : 'Delete Test Runs'}
        message={
          pendingDeleteId
            ? 'Are you sure you want to delete this test run? Related data will not be deleted.'
            : `Are you sure you want to delete ${Array.isArray(selectedRows) ? selectedRows.length : 0} test run${Array.isArray(selectedRows) && selectedRows.length === 1 ? '' : 's'}? Don't worry, related data will not be deleted, only ${Array.isArray(selectedRows) && selectedRows.length === 1 ? 'this record' : 'these records'}.`
        }
        itemType="test runs"
      />

      <DeleteModal
        open={cancelModalOpen}
        onClose={handleCancelClose}
        onConfirm={handleCancelConfirm}
        isLoading={isCancelling}
        title={`Cancel Test Run${cancellableSelectedRuns.length === 1 ? '' : 's'}`}
        message={`Are you sure you want to cancel ${cancellableSelectedRuns.length} test run${cancellableSelectedRuns.length === 1 ? '' : 's'}? ${cancellableSelectedRuns.length === 1 ? 'It' : 'They'} will be stopped and marked as Cancelled.`}
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
  );
}

export default React.memo(TestRunsGrid);
