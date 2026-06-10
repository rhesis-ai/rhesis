'use client';

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useRouter } from 'next/navigation';
import type {
  GridFilterModel,
  GridPaginationModel,
  GridRowModel,
} from '@mui/x-data-grid';
import AssignEntityDrawer from '@/components/common/AssignEntityDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import { combineTestFiltersToOData } from '@/utils/odata-filter';
import TestFilterDrawer, {
  type TestFilters,
  EMPTY_TEST_FILTERS,
  hasActiveTestFilters,
  countActiveTestFilters,
} from '@/app/(protected)/tests/components/TestFilterDrawer';
import {
  applyQuickFilterToModel,
  applyTestDrawerFiltersToModel,
} from '@/app/(protected)/tests/components/test-filter-model';
import { getTestDisplayContent } from '@/app/(protected)/tests/components/test-grid-helpers';
import { getTestSetTestColumns } from './testSetTestColumns';

interface AssignTestsDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  testSetId: string;
  testSetType?: string;
  onAssign: (tests: TestDetail[]) => Promise<void>;
}

export default function AssignTestsDrawer({
  open,
  onClose,
  sessionToken,
  testSetId,
  testSetType,
  onAssign,
}: AssignTestsDrawerProps) {
  const router = useRouter();
  const [available, setAvailable] = useState<TestDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [drawerFilters, setDrawerFilters] =
    useState<TestFilters>(EMPTY_TEST_FILTERS);
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });
  const [totalCount, setTotalCount] = useState(0);

  const [resolvedLinkedIds, setResolvedLinkedIds] = useState<Set<string>>(
    new Set()
  );
  const testsByIdRef = useRef<Map<string, TestDetail>>(new Map());
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    available.forEach(test => {
      if (test.id) {
        testsByIdRef.current.set(String(test.id), test);
      }
    });
  }, [available]);

  const fetchLinkedIds = useCallback(async () => {
    try {
      const factory = new ApiClientFactory(sessionToken);
      const testSetsClient = factory.getTestSetsClient();
      const linkedTests = await testSetsClient.getAllTestSetTests(testSetId);
      if (!isMountedRef.current) return;
      setResolvedLinkedIds(
        new Set(linkedTests.map(test => String(test.id)).filter(Boolean))
      );
    } catch {
      if (!isMountedRef.current) return;
      setResolvedLinkedIds(new Set());
    }
  }, [sessionToken, testSetId]);

  const fetchTests = useCallback(async () => {
    if (!sessionToken || !open) return;

    try {
      setLoading(true);

      const factory = new ApiClientFactory(sessionToken);
      const testsClient = factory.getTestsClient();
      const filterString = combineTestFiltersToOData(filterModel);

      const response = await testsClient.getTests({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc',
        ...(filterString && { filter: filterString }),
      });

      if (!isMountedRef.current) return;
      setAvailable(response.data);
      setTotalCount(response.pagination.totalCount);
    } catch {
      if (!isMountedRef.current) return;
      setAvailable([]);
      setTotalCount(0);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [
    sessionToken,
    open,
    filterModel,
    paginationModel.page,
    paginationModel.pageSize,
  ]);

  useEffect(() => {
    if (!open) return;

    setSearchQuery('');
    setDrawerFilters(EMPTY_TEST_FILTERS);
    setFilterModel({ items: [] });
    setPaginationModel({ page: 0, pageSize: 25 });
    void fetchLinkedIds();
  }, [open, fetchLinkedIds]);

  useEffect(() => {
    if (!open) return;
    setFilterModel(prev => applyQuickFilterToModel(prev, searchQuery));
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [open, searchQuery]);

  useEffect(() => {
    if (!open) return;
    setFilterModel(prev => applyTestDrawerFiltersToModel(prev, drawerFilters));
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [open, drawerFilters]);

  useEffect(() => {
    if (!open) return;
    void fetchTests();
  }, [open, fetchTests]);

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const columns = useMemo(
    () => getTestSetTestColumns(testSetType),
    [testSetType]
  );

  const availableFiltered = useMemo(
    () =>
      available
        .filter(test => test.id && !resolvedLinkedIds.has(String(test.id)))
        .map(test => ({
          ...test,
          name: getTestDisplayContent(test),
        })) as GridRowModel[],
    [available, resolvedLinkedIds]
  );

  const handleAssign = useCallback(
    async (selectedIds: string[]) => {
      const selected = selectedIds
        .map(id => testsByIdRef.current.get(id))
        .filter((test): test is TestDetail => test != null);
      await onAssign(selected);
    },
    [onAssign]
  );

  return (
    <>
      <AssignEntityDrawer
        open={open}
        onClose={onClose}
        title="Assign tests"
        rows={availableFiltered}
        columns={columns}
        loading={loading}
        getRowId={row => String(row.id)}
        onAssign={handleAssign}
        saveButtonText="Assign"
        searchPlaceholder="Search tests…"
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        serverSidePagination
        totalRows={totalCount}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        onFilterClick={() => setFilterOpen(true)}
        hasActiveFilters={hasActiveTestFilters(drawerFilters)}
        activeFilterCount={countActiveTestFilters(drawerFilters)}
        onCreateNew={() => {
          onClose();
          router.push('/tests/new-manual');
        }}
        createNewLabel="Create new test"
      />
      <TestFilterDrawer
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        filters={drawerFilters}
        sessionToken={sessionToken}
        onApply={setDrawerFilters}
      />
    </>
  );
}
