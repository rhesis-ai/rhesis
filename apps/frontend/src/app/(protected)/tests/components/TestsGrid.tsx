'use client';

import React, {
  useEffect,
  useRef,
  useState,
  useContext,
  useCallback,
  useMemo,
} from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { testKeys } from '@/constants/query-keys';
import { useGridState } from '@/hooks/useGridState';
import { useGridQuery } from '@/hooks/useGridQuery';
import ListIcon from '@mui/icons-material/ListOutlined';
import DeleteIcon from '@mui/icons-material/DeleteOutlined';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import {
  GridColDef,
  GridRowParams,
  GridRowSelectionModel,
  GridPaginationModel,
  GridFilterModel,
  GridRenderCellParams,
  GridSortModel,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { Tag } from '@/utils/api-client/interfaces/tag';
import { Typography, Box, Alert, Chip } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import { AttachFileIcon, ChatIcon, DescriptionIcon } from '@/components/icons';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import TestDrawer from './TestDrawer';
import TestSetSelectionDialog from './TestSetSelectionDialog';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { TestSetsClient } from '@/utils/api-client/test-sets-client';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import { combineTestFiltersToOData } from '@/utils/odata-filter';
import TestFilterDrawer, {
  type TestFilters,
  EMPTY_TEST_FILTERS,
  hasActiveTestFilters,
  countActiveTestFilters,
} from './TestFilterDrawer';
import {
  createRowActionsColumn,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import {
  getTestContentValue,
  renderTestContentCell,
} from './test-grid-helpers';
import { formatDate } from '@/utils/date';
import { TEST_TYPES } from '@/constants/test-types';
import {
  applyTestDrawerFiltersToModel,
  buildTestIdsODataFilter,
  combineODataFilterExpressions,
} from './test-filter-model';
import { gridSortToApiParams } from '@/utils/grid-sort';
import {
  fetchFailedTestIdsForInsights,
  formatInsightsFailedTestsBanner,
  type InsightsFailedTestsFilter,
} from '@/app/(protected)/insights/utils/insights-failed-tests';

interface TestsTableProps {
  sessionToken: string;
  onNewTest?: () => void;
  disableAddButton?: boolean;
  insightsFailedFilter?: InsightsFailedTestsFilter | null;
  insightsEndpointName?: string;
  onTotalCountChange?: (count: number) => void;
}

// ─── Toolbar context (passes search/filter state into the DataGrid slot) ──────

interface TestsToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  typeFilter: string;
  setTypeFilter: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
  activeFilterCount: number;
}

const TestsToolbarContext = React.createContext<TestsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  typeFilter: 'all',
  setTypeFilter: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
});

const PILL_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Single Turn', value: TEST_TYPES.SINGLE_TURN },
  { label: 'Multi Turn', value: TEST_TYPES.MULTI_TURN },
];

function TestsUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    typeFilter,
    setTypeFilter,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
  } = useContext(TestsToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search tests…"
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      activeFilterCount={activeFilterCount}
      middleContent={
        <ToolbarPillTabs
          tabs={PILL_TABS}
          activeValue={typeFilter}
          onChange={setTypeFilter}
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

export default function TestsTable({
  sessionToken,
  onNewTest: _onNewTest,
  disableAddButton: _disableAddButton = false,
  insightsFailedFilter = null,
  insightsEndpointName,
  onTotalCountChange,
}: TestsTableProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const isMounted = useRef(true);
  const canEditTest = useCan(Capability.Test.UPDATE);
  const canDeleteTest = useCan(Capability.Test.DELETE);
  const queryClient = useQueryClient();

  // Search + tab filter — managed here, shared to toolbar via context
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [drawerFilters, setDrawerFilters] =
    useState<TestFilters>(EMPTY_TEST_FILTERS);

  const {
    filterModel,
    paginationModel,
    sortModel,
    setPaginationModel,
    handlePaginationModelChange,
    handleFilterModelChange,
    handleSortModelChange,
  } = useGridState({
    searchQuery,
    typeFilter,
    typeFilterField: 'test_type.type_value',
    applyDrawerFilters: useCallback(
      (prev: GridFilterModel) =>
        applyTestDrawerFiltersToModel(prev, drawerFilters),
      [drawerFilters]
    ),
  });

  // Component state
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTest, setSelectedTest] = useState<TestDetail | undefined>();
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [testSetDialogOpen, setTestSetDialogOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [insightsFailedTestIds, setInsightsFailedTestIds] = useState<
    string[] | null
  >(null);
  const [insightsFilterLoading, setInsightsFilterLoading] = useState(false);
  const [insightsFilterError, setInsightsFilterError] = useState<string | null>(
    null
  );
  const [isDeleting, setIsDeleting] = useState(false);

  const insightsFilterReady =
    !insightsFailedFilter || insightsFailedTestIds !== null;

  const gridFilterString = combineTestFiltersToOData(filterModel);
  const insightsIdFilter =
    insightsFailedFilter && insightsFailedTestIds !== null
      ? buildTestIdsODataFilter(insightsFailedTestIds)
      : '';
  const filterString = combineODataFilterExpressions(
    gridFilterString,
    insightsIdFilter
  );
  const { sort_by, sort_order } = gridSortToApiParams(sortModel);

  const {
    data: testsData,
    isLoading: loading,
    errorMessage: error,
    dismissError,
  } = useGridQuery({
    queryKey: testKeys.list(
      filterString,
      paginationModel.page,
      paginationModel.pageSize,
      sort_by,
      sort_order
    ),
    errorFallbackMessage: 'Failed to load tests',
    queryFn: () => {
      const testsClient = new ApiClientFactory(sessionToken).getTestsClient();
      return testsClient.getTests({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by,
        sort_order,
        ...(filterString && { filter: filterString }),
      });
    },
    enabled: !!sessionToken && insightsFilterReady,
  });

  const tests = testsData?.data ?? [];
  const totalCount = testsData?.pagination.totalCount ?? 0;

  // Compute whether selected tests have mixed types
  const selectedTestTypes = useMemo(() => {
    const selectedTests = tests.filter(t =>
      selectedRows.includes(t.id as string)
    );
    const typeValues = new Set(
      selectedTests.map(t => t.test_type?.type_value ?? null)
    );
    return {
      isMixed: typeValues.size > 1,
      commonTypeValue:
        typeValues.size === 1 ? ([...typeValues][0] ?? undefined) : undefined,
    };
  }, [selectedRows, tests]);

  useEffect(() => {
    if (!testsData) return;
    const filtersActive =
      filterModel.items.length > 0 ||
      !!searchQuery ||
      hasActiveTestFilters(drawerFilters);
    if (!filtersActive) onTotalCountChange?.(testsData.pagination.totalCount);
  }, [
    testsData,
    filterModel.items.length,
    searchQuery,
    drawerFilters,
    onTotalCountChange,
  ]);

  // Apply Insights failed-test filter from URL params
  useEffect(() => {
    if (!insightsFailedFilter || !sessionToken) {
      setInsightsFailedTestIds(null);
      setInsightsFilterError(null);
      setInsightsFilterLoading(false);
      return;
    }

    let cancelled = false;

    const loadFailedTestIds = async () => {
      setInsightsFailedTestIds(null);
      setInsightsFilterLoading(true);
      setInsightsFilterError(null);
      try {
        const ids = await fetchFailedTestIdsForInsights(sessionToken, {
          endpointId: insightsFailedFilter.endpointId,
          timeRange: insightsFailedFilter.timeRange,
          behaviorId: insightsFailedFilter.behaviorId,
          behaviorName: insightsFailedFilter.behaviorName,
          metricName: insightsFailedFilter.metricName,
          topicName: insightsFailedFilter.topicName,
          outcome: insightsFailedFilter.outcome,
        });
        if (!cancelled) {
          setInsightsFailedTestIds(ids);
        }
      } catch {
        if (!cancelled) {
          setInsightsFilterError('Failed to load test cases from Insights.');
          setInsightsFailedTestIds([]);
        }
      } finally {
        if (!cancelled) {
          setInsightsFilterLoading(false);
        }
      }
    };

    void loadFailedTestIds();
    return () => {
      cancelled = true;
    };
  }, [
    insightsFailedFilter?.endpointId,
    insightsFailedFilter?.timeRange,
    sessionToken,
    insightsFailedFilter,
  ]);

  // Row action handlers
  const handleRowDeleteAction = useCallback((id: string) => {
    setPendingDeleteId(id);
    setDeleteModalOpen(true);
  }, []);

  const handleRowEditAction = useCallback(
    (id: string) => {
      const test = tests.find(t => t.id === id);
      if (test) {
        setSelectedTest(test);
        setDrawerOpen(true);
      }
    },
    [tests]
  );

  // Column definitions
  const columns: GridColDef[] = React.useMemo(() => {
    const actionsCol = createRowActionsColumn({
      onEdit: id => handleRowEditAction(id),
      onDelete: id => handleRowDeleteAction(id),
      canEdit: () => canEditTest,
      canDelete: () => canDeleteTest,
    });
    return [
      {
        field: 'prompt.content',
        headerName: 'Content',
        width: 360,
        minWidth: 200,
        resizable: true,
        filterable: true,
        valueGetter: getTestContentValue,
        renderCell: renderTestContentCell,
      },
      {
        field: 'behavior.name',
        headerName: 'Behavior',
        width: 140,
        minWidth: 100,
        resizable: true,
        filterable: true,
        valueGetter: (_value: unknown, row: TestDetail) =>
          row.behavior?.name || '',
        renderCell: (params: GridRenderCellParams<TestDetail>) => {
          const behaviorName = params.row.behavior?.name;
          if (!behaviorName) return null;

          return <GridBadge label={behaviorName} />;
        },
      },
      {
        field: 'topic.name',
        headerName: 'Topic',
        width: 140,
        minWidth: 100,
        resizable: true,
        filterable: true,
        valueGetter: (_value: unknown, row: TestDetail) =>
          row.topic?.name || '',
        renderCell: (params: GridRenderCellParams<TestDetail>) => {
          const topicName = params.row.topic?.name;
          if (!topicName) return null;

          return <GridBadge label={topicName} />;
        },
      },
      {
        field: 'category.name',
        headerName: 'Category',
        width: 140,
        minWidth: 100,
        resizable: true,
        filterable: true,
        valueGetter: (_value: unknown, row: TestDetail) =>
          row.category?.name || '',
        renderCell: (params: GridRenderCellParams<TestDetail>) => {
          const categoryName = params.row.category?.name;
          if (!categoryName) return null;

          return <GridBadge label={categoryName} />;
        },
      },
      {
        field: 'test_type.type_value',
        headerName: 'Test Type',
        width: 120,
        minWidth: 90,
        resizable: true,
        filterable: true,
        valueGetter: (_value: unknown, row: TestDetail) =>
          row.test_type?.type_value || '',
        renderCell: (params: GridRenderCellParams<TestDetail>) => {
          const testType = params.row.test_type?.type_value;
          if (!testType) return null;

          return <GridBadge label={testType} />;
        },
      },
      {
        field: 'created_at',
        headerName: 'Created',
        width: 120,
        minWidth: 100,
        resizable: true,
        filterable: false,
        renderCell: params => {
          return (
            <Typography variant="body2" color="text.secondary">
              {formatDate(params.row.created_at)}
            </Typography>
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
              <ChatIcon sx={{ fontSize: 'small', color: 'text.secondary' }} />
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
              <DescriptionIcon
                sx={{ fontSize: 'small', color: 'text.secondary' }}
              />
              <Typography variant="body2">{count}</Typography>
            </Box>
          );
        },
      },
      {
        field: 'counts.files',
        headerName: 'Attachments',
        width: 100,
        minWidth: 80,
        resizable: true,
        sortable: false,
        filterable: false,
        renderCell: params => {
          const count = params.row.counts?.files || 0;
          if (count === 0) return null;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <AttachFileIcon
                sx={{ fontSize: 'small', color: 'text.secondary' }}
              />
              <Typography variant="body2">{count}</Typography>
            </Box>
          );
        },
      },
      {
        field: 'test_metadata.sources',
        headerName: 'Sources',
        width: 80,
        minWidth: 60,
        resizable: true,
        sortable: false,
        filterable: false,
        align: 'center',
        headerAlign: 'center',
        renderCell: params => {
          const sources = params.row.test_metadata?.sources;
          if (!sources || sources.length === 0) return null;
          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <InsertDriveFileOutlined
                sx={{ fontSize: 'small', color: 'text.secondary' }}
              />
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
        valueGetter: (_, row) =>
          row.tags?.filter((tag: Tag) => tag && tag.id && tag.name).length ?? 0,
        renderCell: params => {
          const test = params.row;
          if (!test.tags || test.tags.length === 0) {
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
              {test.tags
                .filter((tag: Tag) => tag && tag.id && tag.name)
                .slice(0, 2)
                .map((tag: Tag) => (
                  <Chip
                    key={tag.id}
                    label={tag.name}
                    size="small"
                    variant="filled"
                    color="primary"
                  />
                ))}
              {test.tags.filter((tag: Tag) => tag && tag.id && tag.name)
                .length > 2 && (
                <Chip
                  label={`+${test.tags.filter((tag: Tag) => tag && tag.id && tag.name).length - 2}`}
                  size="small"
                  variant="outlined"
                />
              )}
            </Box>
          );
        },
      },
      actionsCol,
    ];
  }, [handleRowEditAction, handleRowDeleteAction]);

  // Event handlers
  const handleRowClick = useCallback(
    (params: GridRowParams) => {
      const testId = params.id;
      router.push(`/tests/${testId}`);
    },
    [router]
  );

  const handleSelectionChange = useCallback(
    (newSelection: GridRowSelectionModel) => {
      setSelectedRows(newSelection);
    },
    []
  );

  const handleCreateTestSet = useCallback(() => {
    if (selectedRows.length > 0) {
      setTestSetDialogOpen(true);
    }
  }, [selectedRows]);

  const handleTestSetSelect = useCallback(
    async (testSet: TestSet) => {
      if (!sessionToken) return;

      try {
        const testSetsClient = new TestSetsClient(sessionToken);
        await testSetsClient.associateTestsWithTestSet(
          testSet.id,
          selectedRows as string[]
        );

        notifications.show(
          `Successfully associated ${selectedRows.length} ${selectedRows.length === 1 ? 'test' : 'tests'} with test set "${testSet.name}"`,
          {
            severity: 'success',
            autoHideDuration: 6000,
          }
        );
        setTestSetDialogOpen(false);
      } catch (_error) {
        notifications.show('Failed to associate tests with test set', {
          severity: 'error',
          autoHideDuration: 6000,
        });
      }
    },
    [sessionToken, selectedRows, notifications]
  );

  const handleDeleteTests = useCallback(() => {
    if (selectedRows.length > 0) {
      setDeleteModalOpen(true);
    }
  }, [selectedRows]);

  const handleDeleteConfirm = useCallback(async () => {
    const idsToDelete = pendingDeleteId
      ? [pendingDeleteId]
      : (selectedRows as string[]);
    if (idsToDelete.length === 0) return;

    try {
      setIsDeleting(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testsClient = clientFactory.getTestsClient();

      await Promise.all(idsToDelete.map(id => testsClient.deleteTest(id)));

      notifications.show(
        `Successfully deleted ${idsToDelete.length} ${idsToDelete.length === 1 ? 'test' : 'tests'}`,
        { severity: 'success', autoHideDuration: 4000 }
      );

      setPendingDeleteId(null);
      setSelectedRows([]);
      queryClient.invalidateQueries({ queryKey: testKeys.all() });
    } catch (_error) {
      notifications.show('Failed to delete tests', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  }, [pendingDeleteId, selectedRows, sessionToken, notifications, queryClient]);

  const handleDeleteCancel = useCallback(() => {
    setDeleteModalOpen(false);
    setPendingDeleteId(null);
  }, []);

  const _handleNewTest = useCallback(() => {
    setSelectedTest(undefined);
    setDrawerOpen(true);
  }, []);

  const handleDrawerClose = useCallback(() => {
    setDrawerOpen(false);
    setSelectedTest(undefined);
  }, []);

  const handleTestSaved = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: testKeys.all() });
    if (paginationModel.page > 0) {
      setPaginationModel(prev => ({ ...prev, page: 0 }));
    }
  }, [queryClient, paginationModel.page]);

  // Get action buttons based on selection (Add Tests removed — FAB in page header handles it)
  const getActionButtons = useCallback(() => {
    if (selectedRows.length === 0) return [];

    return [
      {
        label: 'Assign to Test Set',
        icon: <ListIcon />,
        variant: 'contained' as const,
        onClick: handleCreateTestSet,
        disabled: selectedTestTypes.isMixed,
      },
      {
        label: 'Delete Tests',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteTests,
      },
    ];
  }, [
    selectedRows.length,
    handleCreateTestSet,
    handleDeleteTests,
    selectedTestTypes.isMixed,
  ]);

  return (
    <TestsToolbarContext.Provider
      value={{
        searchQuery,
        setSearchQuery,
        typeFilter,
        setTypeFilter,
        openFilterDrawer: () => setFilterDrawerOpen(true),
        hasActiveDrawerFilters: hasActiveTestFilters(drawerFilters),
        activeFilterCount: countActiveTestFilters(drawerFilters),
      }}
    >
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={dismissError}>
          {error}
        </Alert>
      )}

      {insightsFailedFilter && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {insightsFilterLoading
            ? 'Loading test cases from Insights…'
            : insightsFilterError ||
              formatInsightsFailedTestsBanner(
                insightsFailedFilter,
                insightsFailedTestIds?.length ?? 0,
                insightsEndpointName
              )}
        </Alert>
      )}

      {selectedRows.length > 0 && (
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
          {selectedTestTypes.isMixed && (
            <Alert severity="warning" sx={{ py: 0 }}>
              Select tests with the same test type
            </Alert>
          )}
        </Box>
      )}

      <BaseDataGrid
        rows={tests}
        columns={columns}
        loading={loading}
        getRowId={row => row.id}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        actionButtons={getActionButtons()}
        checkboxSelection
        disableRowSelectionOnClick
        onRowSelectionModelChange={handleSelectionChange}
        rowSelectionModel={selectedRows}
        onRowClick={handleRowClick}
        getRowUrl={row => `/tests/${row.id}`}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        serverSideFiltering={true}
        filterModel={filterModel}
        onFilterModelChange={handleFilterModelChange}
        sortingMode="server"
        sortModel={sortModel}
        onSortModelChange={handleSortModelChange}
        toolbarSlot={TestsUnifiedToolbar}
        showToolbar={true}
        disablePaperWrapper={true}
        persistState={!insightsFailedFilter}
        initialState={{
          columns: {
            columnVisibilityModel: {
              'test_metadata.sources': false,
            },
          },
        }}
        sx={rowActionsHoverSx}
      />

      {sessionToken && (
        <>
          <TestDrawer
            open={drawerOpen}
            onClose={handleDrawerClose}
            sessionToken={sessionToken}
            test={selectedTest}
            onSuccess={handleTestSaved}
          />
          <TestSetSelectionDialog
            open={testSetDialogOpen}
            onClose={() => setTestSetDialogOpen(false)}
            onSelect={handleTestSetSelect}
            sessionToken={sessionToken}
            testTypeValue={selectedTestTypes.commonTypeValue}
          />
          <DeleteModal
            open={deleteModalOpen}
            onClose={handleDeleteCancel}
            onConfirm={handleDeleteConfirm}
            isLoading={isDeleting}
            title={pendingDeleteId ? 'Delete Test' : 'Delete Tests'}
            message={
              pendingDeleteId
                ? 'Are you sure you want to delete this test? Related data will not be deleted.'
                : `Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'test' : 'tests'}? Don't worry, related data will not be deleted, only ${selectedRows.length === 1 ? 'this record' : 'these records'}.`
            }
            itemType="tests"
          />
        </>
      )}

      {/* Filter drawer */}
      <TestFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        sessionToken={sessionToken}
        onApply={f => {
          setDrawerFilters(f);
          // If drawer sets a test type, sync the pill tab too
          if (f.testType) setTypeFilter(f.testType);
          else if (!drawerFilters.testType) setTypeFilter('all');
        }}
      />
    </TestsToolbarContext.Provider>
  );
}
