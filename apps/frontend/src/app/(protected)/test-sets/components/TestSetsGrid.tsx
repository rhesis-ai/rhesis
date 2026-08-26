'use client';

import React, {
  useState,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from 'react';
import {
  GridColDef,
  GridRowParams,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid, { GRID_PAPER_SX } from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { useList } from '@/hooks/useList';
import { testSetsList } from './list';
import type { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Tag } from '@/utils/api-client/interfaces/tag';
import {
  Box,
  Tooltip,
  Typography,
  Avatar,
  Alert,
  Chip,
  Paper,
} from '@mui/material';
import {
  ChatIcon,
  DescriptionIcon,
  HorizontalSplitIcon,
} from '@/components/icons';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import PersonIcon from '@mui/icons-material/Person';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import SelectionModeToggle from '@/components/common/SelectionModeToggle';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useSession } from 'next-auth/react';
import RunDrawer from '@/components/common/RunDrawer';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications as useJobNotifications } from '@/contexts/NotificationsContext';
import {
  HIGHLIGHTED_ROW_CLASS,
  NotificationSection,
} from '@/constants/notifications';
import { formatDate } from '@/utils/date';
import TestSetFilterDrawer, {
  type TestSetFilters,
  EMPTY_TEST_SET_FILTERS,
  hasActiveTestSetFilters,
  countActiveTestSetFilters,
} from './TestSetFilterDrawer';
import {
  createRowActionsColumn,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { TEST_TYPE_PILL_TABS } from '@/constants/test-types';
import GridBadge from '@/components/common/GridBadge';
import { useBulkDelete } from '@/hooks/useBulkDelete';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import GridStateGate from '@/components/common/GridStateGate';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';

interface TestSetsGridProps {
  canCreate?: boolean;
  onCreateClick?: () => void;
  onBulkActionsChange?: (actions: TestSetsBulkActionsState) => void;
  /** Bumped by the page after a create/import/generate succeeds, to trigger a re-fetch. */
  refreshTrigger?: number;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: TestSet[];
  initialTotalCount?: number;
}

export interface TestSetsBulkActionsState {
  visible: boolean;
  onRun: () => void;
  onDelete: () => void;
}

// ─── Toolbar context ────────────────────────────────────────────────────────────

interface TestSetsToolbarState {
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

const TestSetsToolbarContext = React.createContext<TestSetsToolbarState>({
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

function TestSetsUnifiedToolbar() {
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
  } = useContext(TestSetsToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search test sets…"
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
          <SelectionModeToggle
            checked={checkboxSelectionMode}
            onChange={setCheckboxSelectionMode}
            label="Select test sets"
          />
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
    />
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
        <GridBadge key={item} label={item} />
      ))}
      {remainingCount > 0 && (
        <Tooltip title={items.slice(maxVisible).join(', ')} arrow>
          <GridBadge label={`+${remainingCount}`} />
        </Tooltip>
      )}
    </Box>
  );
};

export default function TestSetsGrid({
  canCreate,
  onCreateClick,
  onBulkActionsChange,
  refreshTrigger,
  initialData,
  initialTotalCount,
}: TestSetsGridProps) {
  const router = useRouter();
  const { status } = useSession();
  const { highlightedIds, clearHighlight } = useJobNotifications();
  const testSetHighlights = highlightedIds(NotificationSection.TEST_SETS);
  const canEditTestSet = useCan(Capability.TestSet.UPDATE);
  const canDeleteTestSet = useCan(Capability.TestSet.DELETE);

  // ── Search + type filter ────────────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');

  // ── Drawer / dialog state ───────────────────────────────────────────────────
  const [drawerFilters, setDrawerFilters] = useState<TestSetFilters>(
    EMPTY_TEST_SET_FILTERS
  );
  const [testRunDrawerOpen, setTestRunDrawerOpen] = useState(false);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [errorDismissed, setErrorDismissed] = useState(false);

  // A pill click wins over the drawer's own testSetType value, matching the
  // old useGridState behavior (pill applied after drawer filters).
  const effectiveTestSetType =
    typeFilter !== 'all' ? typeFilter : drawerFilters.testSetType;

  // ── Data fetching ────────────────────────────────────────────────────────

  const filters = useMemo(
    () => ({
      search: searchQuery,
      testSetType: effectiveTestSetType,
      status: drawerFilters.status,
      creator: drawerFilters.creator,
      tag: drawerFilters.tag,
      tagsPresence: drawerFilters.tags,
      commentsPresence: drawerFilters.comments,
      tasksPresence: drawerFilters.tasks,
    }),
    [searchQuery, effectiveTestSetType, drawerFilters]
  );

  const {
    data: testSets,
    totalCount,
    isLoading: loading,
    error: rawError,
    refresh,
    paginationModel,
    onPaginationModelChange: handlePaginationModelChange,
    sortModel,
    onSortModelChange: handleSortModelChange,
  } = useList(testSetsList, {
    filters,
    initialData,
    initialTotalCount,
    onError: () => setErrorDismissed(false),
  });

  useEffect(() => {
    setErrorDismissed(false);
  }, [rawError]);

  const error = rawError && !errorDismissed ? rawError : null;
  const dismissError = useCallback(() => setErrorDismissed(true), []);

  const isFirstRefreshTrigger = useRef(true);
  useEffect(() => {
    if (isFirstRefreshTrigger.current) {
      isFirstRefreshTrigger.current = false;
      return;
    }
    refresh();
    // Only refreshTrigger (bumped by the page after a create/import/generate) should re-run this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

  // ── Bulk selection + delete ──────────────────────────────────────────────────
  // TestSets has a second bulk action (Run), so it bridges to the page's
  // FabGroup itself below instead of using useBulkDelete's built-in
  // onBulkActionsChange, which only knows about delete.
  const {
    checkboxSelectionMode,
    setCheckboxSelectionMode,
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
      new ApiClientFactory().getTestSetsClient().bulkDeleteTestSets(ids),
    onSuccess: refresh,
    itemLabelSingular: 'test set',
    itemLabelPlural: 'test sets',
  });

  // ── Row + selection handlers ─────────────────────────────────────────────────

  const handleRowClick = useCallback(
    (params: GridRowParams) => {
      clearHighlight(NotificationSection.TEST_SETS, String(params.id));
      router.push(`/test-sets/${params.id}`);
    },
    [router, clearHighlight]
  );

  const handleRowEditAction = useCallback(
    (id: string) => {
      router.push(`/test-sets/${id}`);
    },
    [router]
  );

  // ── Bulk actions bridge (Run + Delete) to the page's FabGroup ───────────────

  const showBulkActions = checkboxSelectionMode && selectedRows.length > 0;
  const bulkHandlersRef = useRef({
    onRun: () => setTestRunDrawerOpen(true),
    onDelete: () => requestDelete(),
  });
  bulkHandlersRef.current = {
    onRun: () => setTestRunDrawerOpen(true),
    onDelete: () => requestDelete(),
  };

  useEffect(() => {
    onBulkActionsChange?.({
      visible: showBulkActions,
      onRun: () => bulkHandlersRef.current.onRun(),
      onDelete: () => bulkHandlersRef.current.onDelete(),
    });
  }, [showBulkActions, onBulkActionsChange]);

  useEffect(() => {
    return () => {
      onBulkActionsChange?.({
        visible: false,
        onRun: () => {},
        onDelete: () => {},
      });
    };
  }, [onBulkActionsChange]);

  // ── Column definitions ───────────────────────────────────────────────────────

  const processedTestSets = useMemo(
    () =>
      testSets.map(testSet => ({
        id: testSet.id,
        name: testSet.name,
        testSetType: testSet.test_set_type?.type_value || '',
        requirements: testSet.attributes?.metadata?.requirements || [],
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

  const columns: GridColDef[] = useMemo(() => {
    const actionsCol = createRowActionsColumn({
      onEdit: id => handleRowEditAction(id),
      onDelete: id => requestDelete(id),
      canEdit: () => canEditTestSet,
      canDelete: () => canDeleteTestSet,
    });
    return [
      {
        field: 'name',
        headerName: 'Name',
        width: 200,
        minWidth: 120,
        resizable: true,
        filterable: true,
      },
      {
        field: 'requirements',
        headerName: 'Requirements',
        width: 160,
        minWidth: 100,
        resizable: true,
        renderCell: params => (
          <ChipContainer items={params.row.requirements || []} />
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
          params.value ? <GridBadge label={params.value} /> : null,
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
        sortable: true,
        filterable: true,
        valueGetter: (_, row) =>
          row.tags?.filter((tag: Tag) => tag?.id && tag?.name).length ?? 0,
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
      actionsCol,
    ];
  }, [handleRowEditAction, requestDelete]);

  const filtersActive = !!searchQuery || hasActiveTestSetFilters(drawerFilters);

  return (
    <GridStateGate
      data={loading ? null : {}}
      error={error}
      isEmpty={totalCount === 0 && !filtersActive}
      emptyState={
        <EntityEmptyState
          card
          icon={HorizontalSplitIcon}
          title="No test sets yet"
          description="Group related tests into a test set to version, share, and run them together."
          actionLabel={canCreate ? 'Create test set' : undefined}
          onAction={canCreate ? onCreateClick : undefined}
          enrichment={getEntityEmptyStateEnrichment('test-sets')}
        />
      }
    >
      <Paper sx={GRID_PAPER_SX}>
        <TestSetsToolbarContext.Provider
          value={{
            searchQuery,
            setSearchQuery,
            typeFilter,
            setTypeFilter,
            openFilterDrawer: () => setFilterDrawerOpen(true),
            hasActiveDrawerFilters: hasActiveTestSetFilters(drawerFilters),
            activeFilterCount: countActiveTestSetFilters(drawerFilters),
            checkboxSelectionMode,
            setCheckboxSelectionMode,
          }}
        >
          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={dismissError}>
              {error}
            </Alert>
          )}

          <BaseDataGrid
            columns={columns}
            rows={processedTestSets}
            loading={loading}
            getRowId={row => row.id}
            showToolbar={true}
            checkboxSelection={checkboxSelectionMode}
            disableRowSelectionOnClick={checkboxSelectionMode || undefined}
            onRowSelectionModelChange={
              checkboxSelectionMode ? handleSelectionChange : undefined
            }
            rowSelectionModel={checkboxSelectionMode ? selectedRows : []}
            onRowClick={checkboxSelectionMode ? undefined : handleRowClick}
            getRowClassName={params =>
              testSetHighlights.includes(String(params.id))
                ? HIGHLIGHTED_ROW_CLASS
                : ''
            }
            getRowUrl={
              checkboxSelectionMode ? undefined : row => `/test-sets/${row.id}`
            }
            paginationModel={paginationModel}
            onPaginationModelChange={handlePaginationModelChange}
            serverSidePagination={true}
            totalRows={totalCount}
            pageSizeOptions={[10, 25, 50]}
            sortingMode="server"
            sortModel={sortModel}
            onSortModelChange={handleSortModelChange}
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
            sx={rowActionsHoverSx}
          />

          {/* Test Run Drawer */}
          {isAuthenticated(status) && (
            <>
              <RunDrawer
                mode="createFromGrid"
                open={testRunDrawerOpen}
                onClose={() => setTestRunDrawerOpen(false)}
                data={{ selectedTestSetIds: selectedRows as string[] }}
                onSuccess={() => setTestRunDrawerOpen(false)}
              />
              <DeleteModal
                open={deleteModalOpen}
                onClose={cancelDelete}
                onConfirm={confirmDelete}
                isLoading={isDeleting}
                title={pendingDeleteId ? 'Delete Test Set' : 'Delete Test Sets'}
                message={
                  pendingDeleteId
                    ? 'Are you sure you want to delete this test set? Related data will not be deleted.'
                    : `Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'test set' : 'test sets'}? Don't worry, related data will not be deleted, only ${selectedRows.length === 1 ? 'this record' : 'these records'}.`
                }
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
      </Paper>
    </GridStateGate>
  );
}
