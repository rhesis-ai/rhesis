'use client';

import React, {
  useEffect,
  useState,
  useContext,
  useCallback,
  useRef,
  useMemo,
} from 'react';
import ListIcon from '@mui/icons-material/ListOutlined';
import DeleteIcon from '@mui/icons-material/DeleteOutlined';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import {
  GridColDef,
  GridRowParams,
  GridRowSelectionModel,
  GridPaginationModel,
  GridFilterModel,
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
} from './TestFilterDrawer';
import {
  getTestContentValue,
  renderTestContentCell,
} from './test-grid-helpers';
import { formatDate } from '@/utils/date';
import { GREYSCALE } from '@/styles/theme';

interface TestsTableProps {
  sessionToken: string;
  onRefresh?: () => void;
  onNewTest?: () => void;
  disableAddButton?: boolean;
}

// ─── Toolbar context (passes search/filter state into the DataGrid slot) ──────

interface TestsToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  typeFilter: string;
  setTypeFilter: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
}

const TestsToolbarContext = React.createContext<TestsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  typeFilter: 'all',
  setTypeFilter: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
});

const PILL_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Single Turn', value: 'single_turn' },
  { label: 'Multi Turn', value: 'multi_turn' },
];

function TestsUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    typeFilter,
    setTypeFilter,
    openFilterDrawer,
    hasActiveDrawerFilters,
  } = useContext(TestsToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search tests…"
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      sx={{
        borderBottom: theme =>
          `1px solid ${
            theme.palette.mode === 'light'
              ? GREYSCALE.light.border
              : GREYSCALE.dark.border
          }`,
        bgcolor: theme =>
          theme.palette.mode === 'light'
            ? GREYSCALE.light.surface1
            : GREYSCALE.dark.surface1,
      }}
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
  onRefresh,
  onNewTest,
  disableAddButton = false,
}: TestsTableProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const isMounted = useRef(true);

  // Search + tab filter — managed here, shared to toolbar via context
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');

  // Component state
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [tests, setTests] = useState<TestDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTest, setSelectedTest] = useState<TestDetail | undefined>();
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] =
    useState<TestFilters>(EMPTY_TEST_FILTERS);
  const [testSetDialogOpen, setTestSetDialogOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

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
    return () => {
      isMounted.current = false;
    };
  }, []);

  // Data fetching function
  const fetchTests = useCallback(async () => {
    if (!sessionToken) return;

    try {
      setLoading(true);

      const clientFactory = new ApiClientFactory(sessionToken);
      const testsClient = clientFactory.getTestsClient();

      // Convert filter model to OData filter string
      const filterString = combineTestFiltersToOData(filterModel);

      const apiParams: Parameters<typeof testsClient.getTests>[0] = {
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc',
        ...(filterString && { filter: filterString }),
      };

      const response = await testsClient.getTests(apiParams);

      setTests(response.data);
      setTotalCount(response.pagination.totalCount);

      setError(null);
    } catch (_error) {
      setError('Failed to load tests');
      setTests([]);
    } finally {
      setLoading(false);
    }
  }, [
    sessionToken,
    paginationModel.page,
    paginationModel.pageSize,
    filterModel,
  ]);

  // Initial data fetch
  useEffect(() => {
    fetchTests();
  }, [fetchTests]);

  // Handle pagination change
  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  // Handle filter change
  const handleFilterModelChange = useCallback((newModel: GridFilterModel) => {
    setFilterModel(newModel);
    // Reset to first page when filters change
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, []);

  // Sync external searchQuery prop into filterModel
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

  // Sync external typeFilter prop into filterModel
  useEffect(() => {
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => item.field !== 'test_type.type_value'
      );
      const items =
        typeFilter && typeFilter !== 'all'
          ? [
              ...otherItems,
              {
                field: 'test_type.type_value',
                operator: 'equals',
                value: typeFilter,
              },
            ]
          : otherItems;
      return { ...prev, items };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [typeFilter]);

  // Sync drawer filters into filterModel
  useEffect(() => {
    setFilterModel(prev => {
      const DRAWER_FIELDS = [
        'test_type.type_value',
        'status.name',
        'behavior.name',
        'category.name',
        'topic.name',
      ];
      const otherItems = prev.items.filter(
        item => !DRAWER_FIELDS.includes(item.field ?? '')
      );
      const drawerItems: typeof prev.items = [];
      if (drawerFilters.testType) {
        drawerItems.push({
          field: 'test_type.type_value',
          operator: 'equals',
          value: drawerFilters.testType,
        });
      }
      if (drawerFilters.status) {
        drawerItems.push({
          field: 'status.name',
          operator: 'contains',
          value: drawerFilters.status,
        });
      }
      if (drawerFilters.behavior) {
        drawerItems.push({
          field: 'behavior.name',
          operator: 'contains',
          value: drawerFilters.behavior,
        });
      }
      if (drawerFilters.category) {
        drawerItems.push({
          field: 'category.name',
          operator: 'contains',
          value: drawerFilters.category,
        });
      }
      if (drawerFilters.topic) {
        drawerItems.push({
          field: 'topic.name',
          operator: 'contains',
          value: drawerFilters.topic,
        });
      }
      return { ...prev, items: [...otherItems, ...drawerItems] };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [drawerFilters]);

  // Column definitions
  const columns: GridColDef[] = React.useMemo(
    () => [
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
        valueGetter: (value, row) => row.behavior?.name || '',
        renderCell: params => {
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
        valueGetter: (value, row) => row.topic?.name || '',
        renderCell: params => {
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
        valueGetter: (value, row) => row.category?.name || '',
        renderCell: params => {
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
        valueGetter: (value, row) => row.test_type?.type_value || '',
        renderCell: params => {
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
        sortable: false,
        filterable: false,
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
        sortable: false,
        filterable: false,
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
        sortable: false,
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
    ],
    []
  );

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

        if (isMounted.current) {
          notifications.show(
            `Successfully associated ${selectedRows.length} ${selectedRows.length === 1 ? 'test' : 'tests'} with test set "${testSet.name}"`,
            {
              severity: 'success',
              autoHideDuration: 6000,
            }
          );

          setTestSetDialogOpen(false);
        }
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
    if (selectedRows.length === 0) return;

    try {
      setIsDeleting(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testsClient = clientFactory.getTestsClient();

      // Delete all selected tests
      await Promise.all(
        selectedRows.map(id => testsClient.deleteTest(id as string))
      );

      // Show success notification
      notifications.show(
        `Successfully deleted ${selectedRows.length} ${selectedRows.length === 1 ? 'test' : 'tests'}`,
        { severity: 'success', autoHideDuration: 4000 }
      );

      // Clear selection and refresh data
      setSelectedRows([]);
      fetchTests();
      onRefresh?.();
    } catch (_error) {
      notifications.show('Failed to delete tests', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  }, [selectedRows, sessionToken, notifications, fetchTests, onRefresh]);

  const handleDeleteCancel = useCallback(() => {
    setDeleteModalOpen(false);
  }, []);

  const _handleNewTest = useCallback(() => {
    setSelectedTest(undefined);
    setDrawerOpen(true);
  }, []);

  const handleDrawerClose = useCallback(() => {
    setDrawerOpen(false);
    setSelectedTest(undefined);
  }, []);

  const handleTestSaved = useCallback(async () => {
    if (sessionToken) {
      try {
        // Fetch the most recent test (the one just created)
        const clientFactory = new ApiClientFactory(sessionToken);
        const testsClient = clientFactory.getTestsClient();

        const response = await testsClient.getTests({
          skip: 0,
          limit: 1,
          sort_by: 'created_at',
          sort_order: 'desc',
        });

        if (response.data.length > 0) {
          const newTest = response.data[0];

          // Add the new test to the top of the current list
          setTests(prevTests => {
            // Check if the test already exists to avoid duplicates
            const existingIndex = prevTests.findIndex(
              test => test.id === newTest.id
            );
            if (existingIndex >= 0) {
              // Update existing test
              const updatedTests = [...prevTests];
              updatedTests[existingIndex] = newTest;
              return updatedTests;
            } else {
              // Add new test to the top
              return [newTest, ...prevTests];
            }
          });

          // Update total count
          setTotalCount(prev => prev + 1);

          // If we're not on the first page, go to first page to show the new test
          if (paginationModel.page > 0) {
            setPaginationModel(prev => ({ ...prev, page: 0 }));
          }
        }

        onRefresh?.();
      } catch (_error) {
        // Fallback to full refresh
        fetchTests();
        onRefresh?.();
      }
    }
  }, [sessionToken, onRefresh, fetchTests, paginationModel.page]);

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
      }}
    >
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
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
              `1px solid ${
                theme.palette.mode === 'light'
                  ? GREYSCALE.light.border
                  : GREYSCALE.dark.border
              }`,
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
        disableRowSelectionOnClick
        onRowSelectionModelChange={handleSelectionChange}
        rowSelectionModel={selectedRows}
        onRowClick={handleRowClick}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        serverSideFiltering={true}
        filterModel={filterModel}
        onFilterModelChange={handleFilterModelChange}
        toolbarSlot={TestsUnifiedToolbar}
        showToolbar={true}
        disablePaperWrapper={true}
        persistState
        initialState={{
          columns: {
            columnVisibilityModel: {
              'test_metadata.sources': false,
            },
          },
        }}
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
            title="Delete Tests"
            message={`Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'test' : 'tests'}? Don't worry, related data will not be deleted, only ${selectedRows.length === 1 ? 'this record' : 'these records'}.`}
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
  );
}
