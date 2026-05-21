'use client';

import React, {
  useEffect,
  useState,
  useCallback,
  useContext,
  useMemo,
} from 'react';
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
import { combineTestSetFiltersToOData } from '@/utils/odata-filter';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Tag } from '@/utils/api-client/interfaces/tag';
import {
  Box,
  Chip,
  Tooltip,
  Typography,
  Avatar,
  Alert,
  Button,
  ButtonGroup,
} from '@mui/material';
import { ChatIcon, DescriptionIcon } from '@/components/icons';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DeleteIcon from '@mui/icons-material/DeleteOutlined';
import PersonIcon from '@mui/icons-material/Person';
import { FilterButton } from '@/components/common/FilterButton';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useSession } from 'next-auth/react';
import { SearchPill } from '@/components/common/SearchPill';
import TestRunDrawer from './TestRunDrawer';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';
import { formatDate } from '@/utils/date';
import { GREYSCALE, BORDER_RADIUS } from '@/styles/theme';
import TestSetFilterDrawer, {
  type TestSetFilters,
  EMPTY_TEST_SET_FILTERS,
  hasActiveTestSetFilters,
} from './TestSetFilterDrawer';
import { TEST_TYPES } from '@/constants/test-types';
import BadgeChip from '@/components/common/BadgeChip';

interface TestSetsGridProps {
  sessionToken?: string;
  refreshKey?: number;
  onRefresh?: () => void;
}

// ─── Toolbar context ────────────────────────────────────────────────────────────

interface TestSetsToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  typeFilter: string;
  setTypeFilter: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
}

const TestSetsToolbarContext = React.createContext<TestSetsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  typeFilter: 'all',
  setTypeFilter: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
});

const PILL_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Single Turn', value: TEST_TYPES.SINGLE_TURN },
  { label: 'Multi Turn', value: TEST_TYPES.MULTI_TURN },
];

function TestSetsUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    typeFilter,
    setTypeFilter,
    openFilterDrawer,
    hasActiveDrawerFilters,
  } = useContext(TestSetsToolbarContext);

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        px: 2,
        py: 1,
        borderBottom: theme =>
          `1px solid ${
            theme.palette.mode === 'light'
              ? GREYSCALE.light.border
              : GREYSCALE.dark.border
          }`,
        minHeight: 52,
      }}
    >
      <FilterButton
        onClick={openFilterDrawer}
        hasActiveFilters={hasActiveDrawerFilters}
      />

      <SearchPill
        value={searchQuery}
        onChange={setSearchQuery}
        placeholder="Search test sets…"
        width={240}
      />

      {/* Center: type pill tabs */}
      <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        <ButtonGroup
          variant="outlined"
          size="small"
          sx={{
            '& .MuiButtonGroup-grouped': {
              borderRadius: 0,
              '&:first-of-type': {
                borderTopLeftRadius: BORDER_RADIUS.pill,
                borderBottomLeftRadius: BORDER_RADIUS.pill,
              },
              '&:last-of-type': {
                borderTopRightRadius: BORDER_RADIUS.pill,
                borderBottomRightRadius: BORDER_RADIUS.pill,
              },
              borderColor: theme =>
                theme.palette.mode === 'light'
                  ? GREYSCALE.light.border
                  : GREYSCALE.dark.border,
            },
          }}
        >
          {PILL_TABS.map(tab => (
            <Button
              key={tab.value}
              onClick={() => setTypeFilter(tab.value)}
              sx={{
                px: 2,
                py: 0.5,
                fontWeight: typeFilter === tab.value ? 600 : 400,
                bgcolor:
                  typeFilter === tab.value ? 'primary.dark' : 'transparent',
                color:
                  typeFilter === tab.value
                    ? '#fff'
                    : theme =>
                        theme.palette.mode === 'light'
                          ? GREYSCALE.light.body
                          : GREYSCALE.dark.body,
                '&:hover': {
                  bgcolor:
                    typeFilter === tab.value
                      ? 'primary.dark'
                      : theme =>
                          theme.palette.mode === 'light'
                            ? GREYSCALE.light.surface1
                            : GREYSCALE.dark.surface1,
                },
              }}
            >
              {tab.label}
            </Button>
          ))}
        </ButtonGroup>
      </Box>

      {/* Right: DataGrid toolbar buttons */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <GridToolbarColumnsButton />
        <GridToolbarDensitySelector />
        <GridToolbarExport />
      </Box>
    </Box>
  );
}

// ─── Helper: chip container for multi-value fields ──────────────────────────────

const ChipContainer = ({ items }: { items: string[] }) => {
  if (items.length === 0) return '-';

  const maxVisible = 3;
  const visibleItems = items.slice(0, maxVisible);
  const remainingCount = items.length - maxVisible;

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 0.5,
        alignItems: 'center',
        width: '100%',
        overflow: 'hidden',
      }}
    >
      {visibleItems.map((item: string) => (
        <BadgeChip key={item} label={item} />
      ))}
      {remainingCount > 0 && (
        <Tooltip title={items.slice(maxVisible).join(', ')} arrow>
          <Chip label={`+${remainingCount}`} size="small" variant="outlined" />
        </Tooltip>
      )}
    </Box>
  );
};

export default function TestSetsGrid({
  sessionToken: sessionTokenProp,
  refreshKey,
  onRefresh,
}: TestSetsGridProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const notifications = useNotifications();

  const sessionToken = sessionTokenProp || session?.session_token || '';

  // ── Search + type filter ────────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');

  // ── Core grid state ─────────────────────────────────────────────────────────
  const [testSets, setTestSets] = useState<TestSet[]>([]);
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
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);

  // ── Drawer / dialog state (only what stays in the grid) ─────────────────────
  const [testRunDrawerOpen, setTestRunDrawerOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] = useState<TestSetFilters>(
    EMPTY_TEST_SET_FILTERS
  );

  // ── Data fetching ────────────────────────────────────────────────────────────

  const fetchTestSets = useCallback(async () => {
    if (!sessionToken) return;

    try {
      setLoading(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();

      const filterString = combineTestSetFiltersToOData(filterModel);

      const apiParams = {
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc' as const,
        ...(filterString && { $filter: filterString }),
      };

      const response = await testSetsClient.getTestSets(apiParams);
      setTestSets(response.data);
      setTotalCount(response.pagination.totalCount);
      setError(null);
    } catch {
      setError('Failed to load test sets');
      setTestSets([]);
    } finally {
      setLoading(false);
    }
  }, [sessionToken, paginationModel, filterModel]);

  useEffect(() => {
    fetchTestSets();
  }, [fetchTestSets]);

  // Refetch when parent signals a refresh (after create/import)
  useEffect(() => {
    if (refreshKey !== undefined && refreshKey > 0) {
      fetchTestSets();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  // ── Sync searchQuery into filterModel ────────────────────────────────────────

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

  // ── Sync typeFilter pill tab into filterModel ────────────────────────────────

  useEffect(() => {
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => item.field !== 'testSetType'
      );
      const items =
        typeFilter && typeFilter !== 'all'
          ? [
              ...otherItems,
              {
                field: 'testSetType',
                operator: 'equals',
                value: typeFilter,
              },
            ]
          : otherItems;
      return { ...prev, items };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [typeFilter]);

  // ── Sync drawer filters into filterModel ─────────────────────────────────────

  useEffect(() => {
    const DRAWER_FIELDS = ['testSetType', 'status.name', 'creator', 'tags'];
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => !DRAWER_FIELDS.includes(item.field ?? '')
      );
      const drawerItems: typeof prev.items = [];
      if (drawerFilters.testSetType) {
        drawerItems.push({
          field: 'testSetType',
          operator: 'equals',
          value: drawerFilters.testSetType,
        });
      }
      if (drawerFilters.status) {
        drawerItems.push({
          field: 'status.name',
          operator: 'contains',
          value: drawerFilters.status,
        });
      }
      if (drawerFilters.creator) {
        drawerItems.push({
          field: 'creator',
          operator: 'contains',
          value: drawerFilters.creator,
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

  // ── Pagination / filter handlers ─────────────────────────────────────────────

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const handleFilterModelChange = useCallback((newModel: GridFilterModel) => {
    setFilterModel(newModel);
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, []);

  // ── Row + selection handlers ─────────────────────────────────────────────────

  const handleRowClick = useCallback(
    (params: GridRowParams) => {
      router.push(`/test-sets/${params.id}`);
    },
    [router]
  );

  const handleSelectionChange = useCallback(
    (newSelection: GridRowSelectionModel) => {
      setSelectedRows(newSelection);
    },
    []
  );

  // ── Delete ───────────────────────────────────────────────────────────────────

  const handleDeleteTestSets = useCallback(() => {
    setDeleteModalOpen(true);
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (selectedRows.length === 0) return;

    try {
      setIsDeleting(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();

      await Promise.all(
        selectedRows.map(id => testSetsClient.deleteTestSet(id as string))
      );

      notifications.show(
        `Successfully deleted ${selectedRows.length} ${selectedRows.length === 1 ? 'test set' : 'test sets'}`,
        { severity: 'success', autoHideDuration: 4000 }
      );

      setSelectedRows([]);
      fetchTestSets();
      onRefresh?.();
    } catch {
      notifications.show('Failed to delete test sets', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  }, [selectedRows, sessionToken, notifications, fetchTestSets, onRefresh]);

  const handleDeleteCancel = useCallback(() => {
    setDeleteModalOpen(false);
  }, []);

  // ── Action buttons (selection-only) ─────────────────────────────────────────

  const getActionButtons = useCallback(() => {
    if (selectedRows.length === 0) return [];

    return [
      {
        label: selectedRows.length > 1 ? 'Run Test Sets' : 'Run Test Set',
        icon: <PlayArrowIcon />,
        variant: 'contained' as const,
        onClick: () => setTestRunDrawerOpen(true),
      },
      {
        label: 'Delete Test Sets',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteTestSets,
      },
    ];
  }, [selectedRows.length, handleDeleteTestSets]);

  // ── Column definitions ───────────────────────────────────────────────────────

  const processedTestSets = useMemo(
    () =>
      testSets.map(testSet => ({
        id: testSet.id,
        name: testSet.name,
        testSetType: testSet.test_set_type?.type_value || '',
        behaviors: testSet.attributes?.metadata?.behaviors || [],
        categories: testSet.attributes?.metadata?.categories || [],
        totalTests: testSet.attributes?.metadata?.total_tests || 0,
        creator: testSet.user,
        counts: testSet.counts,
        sources: testSet.attributes?.metadata?.sources || [],
        tags: testSet.tags || [],
        created_at: testSet.created_at,
      })),
    [testSets]
  );

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        width: 200,
        minWidth: 120,
        resizable: true,
        filterable: true,
      },
      {
        field: 'behaviors',
        headerName: 'Behaviors',
        width: 160,
        minWidth: 100,
        resizable: true,
        renderCell: params => (
          <ChipContainer items={params.row.behaviors || []} />
        ),
      },
      {
        field: 'categories',
        headerName: 'Categories',
        width: 160,
        minWidth: 100,
        resizable: true,
        renderCell: params => (
          <ChipContainer items={params.row.categories || []} />
        ),
      },
      {
        field: 'testSetType',
        headerName: 'Type',
        width: 120,
        minWidth: 90,
        resizable: true,
        filterable: true,
        valueGetter: (_, row) => row.testSetType || '',
        renderCell: params =>
          params.value ? <BadgeChip label={params.value} /> : null,
      },
      {
        field: 'created_at',
        headerName: 'Created',
        width: 120,
        minWidth: 100,
        resizable: true,
        filterable: false,
        renderCell: params => (
          <Typography variant="body2" color="text.secondary">
            {formatDate(params.row.created_at)}
          </Typography>
        ),
      },
      {
        field: 'totalTests',
        headerName: 'Tests',
        width: 80,
        minWidth: 60,
        resizable: true,
        valueGetter: (_, row) => row.totalTests,
      },
      {
        field: 'creator',
        headerName: 'Creator',
        width: 160,
        minWidth: 120,
        resizable: true,
        sortable: true,
        filterable: true,
        valueGetter: (_, row) =>
          row.creator?.name ||
          `${row.creator?.given_name || ''} ${row.creator?.family_name || ''}`.trim() ||
          row.creator?.email ||
          '',
        renderCell: params => {
          const creator = params.row.creator;
          if (!creator) return '-';

          const displayName =
            creator.name ||
            `${creator.given_name || ''} ${creator.family_name || ''}`.trim() ||
            creator.email;

          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Avatar src={creator.picture} sx={{ width: 24, height: 24 }}>
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
        field: 'sources',
        headerName: 'Sources',
        width: 80,
        minWidth: 60,
        resizable: true,
        sortable: false,
        filterable: false,
        align: 'center',
        headerAlign: 'center',
        renderCell: params => {
          const sources = params.row.sources;
          const count = sources?.length || 0;
          if (count === 0) return null;
          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 0.5,
              }}
            >
              <InsertDriveFileOutlined
                sx={{ fontSize: 16, color: 'text.secondary' }}
              />
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
        valueGetter: (_, row) =>
          row.tags
            ?.filter((tag: Tag) => tag?.name)
            .map((tag: Tag) => tag.name)
            .join(', ') ?? '',
        renderCell: params => {
          const testSet = params.row;
          if (!testSet.tags || testSet.tags.length === 0) return null;

          return (
            <Box
              sx={{
                display: 'flex',
                gap: 0.5,
                flexWrap: 'nowrap',
                overflow: 'hidden',
              }}
            >
              {testSet.tags
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
              {testSet.tags.filter((tag: Tag) => tag && tag.id && tag.name)
                .length > 2 && (
                <Chip
                  label={`+${testSet.tags.filter((tag: Tag) => tag && tag.id && tag.name).length - 2}`}
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

  return (
    <TestSetsToolbarContext.Provider
      value={{
        searchQuery,
        setSearchQuery,
        typeFilter,
        setTypeFilter,
        openFilterDrawer: () => setFilterDrawerOpen(true),
        hasActiveDrawerFilters: hasActiveTestSetFilters(drawerFilters),
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
        </Box>
      )}

      <BaseDataGrid
        columns={columns}
        rows={processedTestSets}
        loading={loading}
        getRowId={row => row.id}
        showToolbar={true}
        onRowClick={handleRowClick}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        actionButtons={getActionButtons()}
        checkboxSelection
        disableRowSelectionOnClick
        onRowSelectionModelChange={handleSelectionChange}
        rowSelectionModel={selectedRows}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        serverSideFiltering={true}
        filterModel={filterModel}
        onFilterModelChange={handleFilterModelChange}
        toolbarSlot={TestSetsUnifiedToolbar}
        disablePaperWrapper={true}
        persistState
        initialState={{
          columns: {
            columnVisibilityModel: {
              sources: false,
            },
          },
        }}
      />

      {/* Test Run Drawer */}
      {sessionToken && (
        <>
          <TestRunDrawer
            open={testRunDrawerOpen}
            onClose={() => setTestRunDrawerOpen(false)}
            sessionToken={sessionToken}
            selectedTestSetIds={selectedRows as string[]}
            onSuccess={() => setTestRunDrawerOpen(false)}
          />
          <DeleteModal
            open={deleteModalOpen}
            onClose={handleDeleteCancel}
            onConfirm={handleDeleteConfirm}
            isLoading={isDeleting}
            title="Delete Test Sets"
            message={`Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'test set' : 'test sets'}? Don't worry, related data will not be deleted, only ${selectedRows.length === 1 ? 'this record' : 'these records'}.`}
            itemType="test sets"
          />
        </>
      )}

      {/* Filter drawer */}
      <TestSetFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        onApply={f => {
          setDrawerFilters(f);
          if (f.testSetType) setTypeFilter(f.testSetType);
          else if (!drawerFilters.testSetType) setTypeFilter('all');
        }}
      />
    </TestSetsToolbarContext.Provider>
  );
}
