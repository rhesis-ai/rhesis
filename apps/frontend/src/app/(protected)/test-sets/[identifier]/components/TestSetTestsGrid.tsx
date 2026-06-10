'use client';

import React, {
  useEffect,
  useState,
  useCallback,
  useRef,
  useContext,
  useMemo,
} from 'react';
import {
  GridColDef,
  GridFilterModel,
  GridRowParams,
  GridPaginationModel,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Alert } from '@mui/material';
import GridToolbar from '@/components/common/GridToolbar';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter } from 'next/navigation';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { combineTestFiltersToOData } from '@/utils/odata-filter';
import { getTestSetTestColumns } from './testSetTestColumns';
import TestFilterDrawer, {
  type TestFilters,
  EMPTY_TEST_FILTERS,
  hasActiveTestFilters,
} from '@/app/(protected)/tests/components/TestFilterDrawer';
import { applyTestDrawerFiltersToModel } from '@/app/(protected)/tests/components/test-filter-model';

interface LinkedTestsToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
}

const LinkedTestsToolbarContext = React.createContext<LinkedTestsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
});

function LinkedTestsUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    openFilterDrawer,
    hasActiveDrawerFilters,
  } = useContext(LinkedTestsToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search tests…"
      searchWidth={288}
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      sx={{ px: '30px', pt: 0, pb: '30px', minHeight: 'auto' }}
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

interface TestSetTestsGridProps {
  sessionToken: string;
  testSetId: string;
  testSetType?: string;
  /** When true, grid is rendered inside embedding atlas (spacing only). */
  embedded?: boolean;
  onRefresh?: () => void;
  onTotalCountChange?: (count: number) => void;
}

export default function TestSetTestsGrid({
  sessionToken,
  testSetId,
  testSetType,
  onTotalCountChange,
}: TestSetTestsGridProps) {
  const isMounted = useRef(true);
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });
  const [drawerFilters, setDrawerFilters] =
    useState<TestFilters>(EMPTY_TEST_FILTERS);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [tests, setTests] = useState<TestDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 10,
  });

  const fetchTests = useCallback(async () => {
    if (!sessionToken || !testSetId) return;

    try {
      if (isMounted.current) {
        setLoading(true);
      }

      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();
      const filterString = combineTestFiltersToOData(filterModel);

      const response = await testSetsClient.getTestSetTests(testSetId, {
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: 'topic',
        sort_order: 'asc',
        ...(filterString && { $filter: filterString }),
      });

      if (isMounted.current) {
        setTests(response.data);
        const count = response.pagination.totalCount;
        setTotalCount(count);
        if (!filterString) {
          onTotalCountChange?.(count);
        }
        setError(null);
      }
    } catch (_error) {
      if (isMounted.current) {
        setError('Failed to load tests');
        setTests([]);
      }
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
    }
  }, [
    sessionToken,
    testSetId,
    paginationModel.page,
    paginationModel.pageSize,
    filterModel,
    onTotalCountChange,
  ]);

  useEffect(() => {
    isMounted.current = true;
    fetchTests();
    return () => {
      isMounted.current = false;
    };
  }, [fetchTests]);

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

  useEffect(() => {
    setFilterModel(prev => applyTestDrawerFiltersToModel(prev, drawerFilters));
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [drawerFilters]);

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const columns: GridColDef[] = React.useMemo(
    () => getTestSetTestColumns(testSetType),
    [testSetType]
  );

  const handleRowClick = useCallback(
    (params: GridRowParams) => {
      const testId = params.id;
      router.push(`/tests/${testId}`);
    },
    [router]
  );

  const toolbarContextValue = useMemo(
    () => ({
      searchQuery,
      setSearchQuery,
      openFilterDrawer: () => setFilterDrawerOpen(true),
      hasActiveDrawerFilters: hasActiveTestFilters(drawerFilters),
    }),
    [searchQuery, drawerFilters]
  );

  return (
    <LinkedTestsToolbarContext.Provider value={toolbarContextValue}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <BaseDataGrid
        rows={tests}
        columns={columns}
        loading={loading}
        getRowId={row => row.id}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        onRowClick={handleRowClick}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        disablePaperWrapper={true}
        toolbarSlot={LinkedTestsUnifiedToolbar}
      />

      <TestFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        sessionToken={sessionToken}
        onApply={setDrawerFilters}
      />
    </LinkedTestsToolbarContext.Provider>
  );
}
