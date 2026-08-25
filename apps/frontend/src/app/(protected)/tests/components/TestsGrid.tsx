'use client';

import React, {
  useEffect,
  useRef,
  useState,
  useContext,
  useCallback,
  useMemo,
} from 'react';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import {
  GridColDef,
  GridRowParams,
  GridRowSelectionModel,
  GridRenderCellParams,
  GridSortModel,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid, { GRID_PAPER_SX } from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { Tag } from '@/utils/api-client/interfaces/tag';
import {
  Typography,
  Box,
  Alert,
  Chip,
  FormControlLabel,
  Switch,
  Paper,
} from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import {
  AttachFileIcon,
  ChatIcon,
  DescriptionIcon,
  ScienceIcon,
} from '@/components/icons';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useSession } from 'next-auth/react';
import TestDrawer from './TestDrawer';
import TestSetSelectionDrawer from './TestSetSelectionDrawer';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { TestSetsClient } from '@/utils/api-client/test-sets-client';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { directoryListParams } from '@/utils/directory';
import { DEFAULT_GRID_SORT } from '@/utils/grid-sort';
import { testsDirectory } from './directory';
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
import { TEST_TYPE_PILL_TABS } from '@/constants/test-types';
import { buildTestIdsODataFilter } from './test-filter-model';
import {
  formatInsightsFailedTestsBanner,
  type InsightsFailedTestsFilter,
} from '@/app/(protected)/insights/utils/insights-failed-tests';
import { useInsightsFailedTestIds } from '@/hooks/useInsightsFailedTestIds';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import GridStateGate from '@/components/common/GridStateGate';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';

interface TestsTableProps {
  onNewTest?: () => void;
  disableAddButton?: boolean;
  canCreate?: boolean;
  insightsFailedFilter?: InsightsFailedTestsFilter | null;
  insightsEndpointName?: string;
  onBulkActionsChange?: (actions: TestsBulkActionsState) => void;
}

export interface TestsBulkActionsState {
  visible: boolean;
  assignDisabled: boolean;
  onAssign: () => void;
  onDelete: () => void;
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
  checkboxSelectionMode: boolean;
  setCheckboxSelectionMode: (v: boolean) => void;
}

const TestsToolbarContext = React.createContext<TestsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  typeFilter: 'all',
  setTypeFilter: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
  checkboxSelectionMode: false,
  setCheckboxSelectionMode: () => {},
});

const PILL_TABS = TEST_TYPE_PILL_TABS;

function TestsUnifiedToolbar() {
  const canExport = useCan(Capability.TestSet.EXPORT);
  const {
    searchQuery,
    setSearchQuery,
    typeFilter,
    setTypeFilter,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
    checkboxSelectionMode,
    setCheckboxSelectionMode,
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
          <FormControlLabel
            control={
              <Switch
                checked={checkboxSelectionMode}
                onChange={event =>
                  setCheckboxSelectionMode(event.target.checked)
                }
                size="small"
                color="primary"
              />
            }
            label={
              <Typography variant="button" color="primary">
                Select tests
              </Typography>
            }
            sx={{ m: 0, whiteSpace: 'nowrap' }}
          />
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          {canExport && <GridToolbarExport />}
        </>
      }
    />
  );
}

export default function TestsTable({
  onNewTest,
  disableAddButton = false,
  canCreate,
  insightsFailedFilter = null,
  insightsEndpointName,
  onBulkActionsChange,
}: TestsTableProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const isMounted = useRef(true);
  const canEditTest = useCan(Capability.Test.UPDATE);
  const canDeleteTest = useCan(Capability.Test.DELETE);
  const { status } = useSession();

  // Search + tab filter — managed here, shared to toolbar via context
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [drawerFilters, setDrawerFilters] =
    useState<TestFilters>(EMPTY_TEST_FILTERS);
  const [sortModel, setSortModel] = useState<GridSortModel>(DEFAULT_GRID_SORT);
  const [errorDismissed, setErrorDismissed] = useState(false);

  // Component state
  const [checkboxSelectionMode, setCheckboxSelectionMode] = useState(false);
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTest, setSelectedTest] = useState<TestDetail | undefined>();
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [testSetDrawerOpen, setTestSetDrawerOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const {
    data: insightsFailedTestIds,
    isLoading: insightsFilterLoading,
    isError: insightsFilterIsError,
    isSuccess: insightsFilterSuccess,
  } = useInsightsFailedTestIds(
    insightsFailedFilter,
    !!insightsFailedFilter && isAuthenticated(status)
  );

  const insightsFilterError = insightsFilterIsError
    ? 'Failed to load test cases from Insights.'
    : null;

  // Ready once IDs resolve (success or error with empty fallback for the grid).
  const insightsFilterReady =
    !insightsFailedFilter || insightsFilterSuccess || insightsFilterIsError;

  const resolvedInsightsFailedTestIds = insightsFilterIsError
    ? []
    : (insightsFailedTestIds ?? null);

  const insightsIdFilter =
    insightsFailedFilter && resolvedInsightsFailedTestIds !== null
      ? buildTestIdsODataFilter(resolvedInsightsFailedTestIds)
      : '';

  // A pill click wins over the drawer's own testType value, matching the old
  // useGridState behavior (pill applied after drawer filters).
  const effectiveTestType =
    typeFilter !== 'all' ? typeFilter : drawerFilters.testType;

  const filters = useMemo(
    () => ({
      search: searchQuery,
      testType: effectiveTestType,
      requirement: drawerFilters.requirement,
      category: drawerFilters.category,
      topic: drawerFilters.topic,
      tagsPresence: drawerFilters.tags,
      commentsPresence: drawerFilters.comments,
      tasksPresence: drawerFilters.tasks,
    }),
    [searchQuery, effectiveTestType, drawerFilters]
  );

  const sort = useMemo(
    () => ({
      by: sortModel[0]?.field || 'created_at',
      order: (sortModel[0]?.sort || 'desc') as 'asc' | 'desc',
    }),
    [sortModel]
  );

  const {
    data: tests,
    totalCount,
    isLoading: loading,
    error: rawError,
    page,
    rowsPerPage: pageSize,
    onPageChange,
    onRowsPerPageChange,
    refresh,
  } = usePaginatedList<TestDetail>({
    fetchPage: ({ skip, limit }) =>
      testsDirectory.list(
        new ApiClientFactory(),
        directoryListParams(
          testsDirectory,
          {
            page: skip / limit + 1,
            pageSize: limit,
            sort,
            filters,
          },
          insightsIdFilter ? [insightsIdFilter] : []
        )
      ),
    filterFingerprint: JSON.stringify({ filters, sort, insightsIdFilter }),
    defaultPageSize: testsDirectory.defaultPageSize,
    enabled: isAuthenticated(status) && insightsFilterReady,
    onError: () => setErrorDismissed(false),
  });

  useEffect(() => {
    setErrorDismissed(false);
  }, [rawError]);

  const error = rawError && !errorDismissed ? rawError : null;
  const dismissError = useCallback(() => setErrorDismissed(true), []);

  const paginationModel = useMemo(() => ({ page, pageSize }), [page, pageSize]);
  const handlePaginationModelChange = useCallback(
    (model: { page: number; pageSize: number }) => {
      if (model.pageSize !== pageSize) {
        onRowsPerPageChange(model.pageSize);
      } else {
        onPageChange(model.page);
      }
    },
    [pageSize, onPageChange, onRowsPerPageChange]
  );
  const handleSortModelChange = useCallback((model: GridSortModel) => {
    setSortModel(model);
  }, []);

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
        flex: 2,
        minWidth: 200,
        resizable: true,
        filterable: true,
        valueGetter: getTestContentValue,
        renderCell: renderTestContentCell,
      },
      {
        field: 'requirement.name',
        headerName: 'Requirement',
        width: 140,
        minWidth: 100,
        resizable: true,
        filterable: true,
        valueGetter: (_value: unknown, row: TestDetail) =>
          row.requirement?.name || '',
        renderCell: (params: GridRenderCellParams<TestDetail>) => {
          const requirementName = params.row.requirement?.name;
          if (!requirementName) return null;

          return <GridBadge label={requirementName} />;
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
      setTestSetDrawerOpen(true);
    }
  }, [selectedRows]);

  const handleTestSetsAssign = useCallback(
    async (testSets: TestSet[]) => {
      if (!isAuthenticated(status) || testSets.length === 0) return;

      const testIds = selectedRows as string[];
      const testSetsClient = new TestSetsClient();
      let successCount = 0;
      let alreadyAssociatedCount = 0;
      let failureCount = 0;

      for (const testSet of testSets) {
        try {
          await testSetsClient.associateTestsWithTestSet(testSet.id, testIds);
          successCount++;
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : '';
          if (errorMessage.toLowerCase().includes('already associated')) {
            alreadyAssociatedCount++;
          } else {
            failureCount++;
          }
        }
      }

      if (failureCount > 0) {
        notifications.show('Failed to associate tests with some test sets', {
          severity: 'error',
          autoHideDuration: 6000,
        });
        return;
      }

      if (successCount > 0) {
        const destinationLabel =
          testSets.length === 1
            ? `test set "${testSets[0].name}"`
            : `${testSets.length} test sets`;

        notifications.show(
          `Successfully associated ${testIds.length} ${testIds.length === 1 ? 'test' : 'tests'} with ${destinationLabel}`,
          {
            severity: 'success',
            autoHideDuration: 6000,
          }
        );
        setTestSetDrawerOpen(false);
        return;
      }

      if (alreadyAssociatedCount > 0) {
        notifications.show(
          'Selected tests are already in the chosen test set(s)',
          {
            severity: 'warning',
            autoHideDuration: 6000,
          }
        );
        setTestSetDrawerOpen(false);
      }
    },
    [selectedRows, notifications, status]
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
      const clientFactory = new ApiClientFactory();
      const testsClient = clientFactory.getTestsClient();

      await testsClient.bulkDeleteTests(idsToDelete);

      notifications.show(
        `Successfully deleted ${idsToDelete.length} ${idsToDelete.length === 1 ? 'test' : 'tests'}`,
        { severity: 'success', autoHideDuration: 4000 }
      );

      setPendingDeleteId(null);
      setSelectedRows([]);
      refresh();
    } catch (_error) {
      notifications.show('Failed to delete tests', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  }, [pendingDeleteId, selectedRows, notifications, refresh]);

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

  const handleCheckboxSelectionModeChange = useCallback((enabled: boolean) => {
    setCheckboxSelectionMode(enabled);
    if (!enabled) {
      setSelectedRows([]);
    }
  }, []);

  const handleTestSaved = useCallback(() => {
    if (page > 0) {
      onPageChange(0);
    } else {
      refresh();
    }
  }, [page, onPageChange, refresh]);

  const filtersActive =
    !!searchQuery ||
    hasActiveTestFilters(drawerFilters) ||
    !!insightsFailedFilter;

  const showSelectionActions = checkboxSelectionMode && selectedRows.length > 0;

  const bulkHandlersRef = useRef({
    onAssign: handleCreateTestSet,
    onDelete: handleDeleteTests,
  });
  bulkHandlersRef.current = {
    onAssign: handleCreateTestSet,
    onDelete: handleDeleteTests,
  };

  useEffect(() => {
    onBulkActionsChange?.({
      visible: showSelectionActions,
      assignDisabled: selectedTestTypes.isMixed,
      onAssign: () => bulkHandlersRef.current.onAssign(),
      onDelete: () => bulkHandlersRef.current.onDelete(),
    });
  }, [showSelectionActions, selectedTestTypes.isMixed, onBulkActionsChange]);

  useEffect(() => {
    return () => {
      onBulkActionsChange?.({
        visible: false,
        assignDisabled: false,
        onAssign: () => {},
        onDelete: () => {},
      });
    };
  }, [onBulkActionsChange]);

  return (
    <GridStateGate
      data={loading ? null : {}}
      error={error}
      isEmpty={totalCount === 0 && !filtersActive}
      emptyState={
        <EntityEmptyState
          card
          icon={ScienceIcon}
          title="No test yet"
          description="Create your first test to start evaluating your AI endpoints. Tests let you measure quality, safety, and reliability across single-turn and multi-turn interactions."
          actionLabel={canCreate ? 'Create test' : undefined}
          onAction={canCreate ? onNewTest : undefined}
          actionDisabled={disableAddButton}
          enrichment={getEntityEmptyStateEnrichment('tests')}
        />
      }
    >
      <Paper sx={GRID_PAPER_SX}>
        <TestsToolbarContext.Provider
          value={{
            searchQuery,
            setSearchQuery,
            typeFilter,
            setTypeFilter,
            openFilterDrawer: () => setFilterDrawerOpen(true),
            hasActiveDrawerFilters: hasActiveTestFilters(drawerFilters),
            activeFilterCount: countActiveTestFilters(drawerFilters),
            checkboxSelectionMode,
            setCheckboxSelectionMode: handleCheckboxSelectionModeChange,
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
                    resolvedInsightsFailedTestIds?.length ?? 0,
                    insightsEndpointName
                  )}
            </Alert>
          )}

          <BaseDataGrid
            rows={tests}
            columns={columns}
            loading={loading}
            getRowId={row => row.id}
            paginationModel={paginationModel}
            onPaginationModelChange={handlePaginationModelChange}
            checkboxSelection={checkboxSelectionMode}
            disableRowSelectionOnClick={checkboxSelectionMode || undefined}
            onRowSelectionModelChange={
              checkboxSelectionMode ? handleSelectionChange : undefined
            }
            rowSelectionModel={checkboxSelectionMode ? selectedRows : []}
            onRowClick={checkboxSelectionMode ? undefined : handleRowClick}
            getRowUrl={
              checkboxSelectionMode ? undefined : row => `/tests/${row.id}`
            }
            serverSidePagination={true}
            totalRows={totalCount}
            pageSizeOptions={[10, 25, 50]}
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

          {isAuthenticated(status) && (
            <>
              <TestDrawer
                open={drawerOpen}
                onClose={handleDrawerClose}
                test={selectedTest}
                onSuccess={handleTestSaved}
              />
              <TestSetSelectionDrawer
                open={testSetDrawerOpen}
                onClose={() => setTestSetDrawerOpen(false)}
                onSelect={handleTestSetsAssign}
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
            onApply={f => {
              setDrawerFilters(f);
              // If drawer sets a test type, sync the pill tab too
              if (f.testType) setTypeFilter(f.testType);
              else if (!drawerFilters.testType) setTypeFilter('all');
            }}
          />
        </TestsToolbarContext.Provider>
      </Paper>
    </GridStateGate>
  );
}
