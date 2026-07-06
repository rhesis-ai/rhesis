'use client';

import React, { useCallback, useContext, useMemo, useState } from 'react';
import {
  GridColDef,
  GridFilterModel,
  GridRowParams,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Alert } from '@mui/material';
import GridToolbar from '@/components/common/GridToolbar';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter } from 'next/navigation';
import { combineTestFiltersToOData } from '@/utils/odata-filter';
import { getTestSetTestColumns } from './testSetTestColumns';
import TestFilterDrawer, {
  type TestFilters,
  EMPTY_TEST_FILTERS,
  hasActiveTestFilters,
} from '@/app/(protected)/tests/components/TestFilterDrawer';
import { applyTestDrawerFiltersToModel } from '@/app/(protected)/tests/components/test-filter-model';
import { useGridState } from '@/hooks/useGridState';
import { useGridQuery } from '@/hooks/useGridQuery';
import { testSetKeys } from '@/constants/query-keys';

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
  onTotalCountChange?: (count: number) => void;
}

export default function TestSetTestsGrid({
  sessionToken,
  testSetId,
  testSetType,
  onTotalCountChange,
}: TestSetTestsGridProps) {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [drawerFilters, setDrawerFilters] =
    useState<TestFilters>(EMPTY_TEST_FILTERS);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

  const { filterModel, paginationModel, handlePaginationModelChange } =
    useGridState({
      searchQuery,
      applyDrawerFilters: useCallback(
        (prev: GridFilterModel) =>
          applyTestDrawerFiltersToModel(prev, drawerFilters),
        [drawerFilters]
      ),
    });

  const filterString = combineTestFiltersToOData(filterModel);

  const {
    data,
    isLoading: loading,
    errorMessage: error,
    dismissError,
  } = useGridQuery({
    queryKey: [
      ...testSetKeys.detail(testSetId),
      'tests',
      filterString,
      paginationModel.page,
      paginationModel.pageSize,
    ],
    errorFallbackMessage: 'Failed to load tests',
    queryFn: () =>
      new ApiClientFactory(sessionToken)
        .getTestSetsClient()
        .getTestSetTests(testSetId, {
          skip: paginationModel.page * paginationModel.pageSize,
          limit: paginationModel.pageSize,
          sort_by: 'topic',
          sort_order: 'asc',
          ...(filterString && { $filter: filterString }),
        }),
    enabled: !!sessionToken && !!testSetId,
  });

  const tests = data?.data ?? [];
  const totalCount = data?.pagination.totalCount ?? 0;

  React.useEffect(() => {
    if (data && !filterString) onTotalCountChange?.(totalCount);
  }, [data, filterString, totalCount, onTotalCountChange]);

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
        <Alert severity="error" sx={{ mb: 2 }} onClose={dismissError}>
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
