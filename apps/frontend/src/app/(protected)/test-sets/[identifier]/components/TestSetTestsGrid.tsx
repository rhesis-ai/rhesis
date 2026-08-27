'use client';

import React, { useCallback, useContext, useMemo, useState } from 'react';
import {
  GridColDef,
  GridRowParams,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Alert } from '@mui/material';
import GridToolbar from '@/components/common/GridToolbar';
import { useRouter } from 'next/navigation';
import { getTestSetTestColumns } from './testSetTestColumns';
import TestFilterDrawer, {
  type TestFilters,
  EMPTY_TEST_FILTERS,
  hasActiveTestFilters,
} from '@/app/(protected)/tests/components/TestFilterDrawer';
import { useList } from '@/hooks/useList';
import { testSetTestsList } from './list';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';

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
  const canExport = useCan(Capability.TestSet.EXPORT);
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
          {canExport && <GridToolbarExport />}
        </>
      }
    />
  );
}

interface TestSetTestsGridProps {
  testSetId: string;
  testSetType?: string;
  /** When true, grid is rendered inside embedding atlas (spacing only). */
  embedded?: boolean;
  /** Server-prefetched first page (default sort, no filters); skips the mount fetch. */
  initialTests?: TestDetail[];
  initialTotalCount?: number;
  onTotalCountChange?: (count: number) => void;
}

export default function TestSetTestsGrid({
  testSetId,
  testSetType,
  initialTests,
  initialTotalCount,
  onTotalCountChange,
}: TestSetTestsGridProps) {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [drawerFilters, setDrawerFilters] =
    useState<TestFilters>(EMPTY_TEST_FILTERS);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [errorDismissed, setErrorDismissed] = useState(false);

  const descriptor = useMemo(() => testSetTestsList(testSetId), [testSetId]);

  const filters = useMemo(
    () => ({
      search: searchQuery,
      testType: drawerFilters.testType,
      requirement: drawerFilters.requirement,
      category: drawerFilters.category,
      topic: drawerFilters.topic,
      tagsPresence: drawerFilters.tags,
      commentsPresence: drawerFilters.comments,
      tasksPresence: drawerFilters.tasks,
    }),
    [searchQuery, drawerFilters]
  );

  const filtersActive = !!searchQuery || hasActiveTestFilters(drawerFilters);

  const {
    data: tests,
    totalCount,
    isLoading: loading,
    error: rawError,
    paginationModel,
    onPaginationModelChange: handlePaginationModelChange,
  } = useList(descriptor, {
    filters,
    enabled: !!testSetId,
    initialData: initialTests,
    initialTotalCount,
    onError: () => setErrorDismissed(false),
  });

  React.useEffect(() => {
    setErrorDismissed(false);
  }, [rawError]);

  const error = rawError && !errorDismissed ? rawError : null;
  const dismissError = useCallback(() => setErrorDismissed(true), []);

  React.useEffect(() => {
    if (!loading && !filtersActive) onTotalCountChange?.(totalCount);
  }, [loading, filtersActive, totalCount, onTotalCountChange]);

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
        onApply={setDrawerFilters}
      />
    </LinkedTestsToolbarContext.Provider>
  );
}
