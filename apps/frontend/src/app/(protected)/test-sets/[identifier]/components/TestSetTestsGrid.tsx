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
import { Box, Alert } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import TagLabel from '@/components/common/Tag';
import GridToolbar from '@/components/common/GridToolbar';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter } from 'next/navigation';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { Tag } from '@/utils/api-client/interfaces/tag';
import {
  getTestContentValue,
  renderTestContentCell,
} from '@/app/(protected)/tests/components/test-grid-helpers';
import { isMultiTurnTest } from '@/constants/test-types';
import { combineTestFiltersToOData } from '@/utils/odata-filter';
import TestFilterDrawer, {
  type TestFilters,
  EMPTY_TEST_FILTERS,
  hasActiveTestFilters,
} from '@/app/(protected)/tests/components/TestFilterDrawer';

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
      const drawerItems: GridFilterModel['items'] = [];
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

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const columns: GridColDef[] = React.useMemo(
    () => [
      {
        field: 'prompt.content',
        headerName: isMultiTurnTest(testSetType) ? 'Goal' : 'Content',
        flex: 3,
        valueGetter: getTestContentValue,
        renderCell: renderTestContentCell,
      },
      {
        field: 'behavior',
        headerName: 'Behavior',
        flex: 1,
        renderCell: params => {
          const behaviorName = params.row.behavior?.name;
          if (!behaviorName) return null;

          return <GridBadge label={behaviorName} />;
        },
      },
      {
        field: 'topic',
        headerName: 'Topic',
        flex: 1,
        renderCell: params => {
          const topicName = params.row.topic?.name;
          if (!topicName) return null;

          return <GridBadge label={topicName} />;
        },
      },
      {
        field: 'category',
        headerName: 'Category',
        flex: 1,
        renderCell: params => {
          const categoryName = params.row.category?.name;
          if (!categoryName) return null;

          return <GridBadge label={categoryName} />;
        },
      },
      {
        field: 'test_type.type_value',
        headerName: 'Test Type',
        flex: 1,
        valueGetter: (_value, row) => row.test_type?.type_value || '',
        renderCell: params => {
          const testType = params.row.test_type?.type_value;
          if (!testType) return null;

          return <GridBadge label={testType} />;
        },
      },
      {
        field: 'tags',
        headerName: 'Tags',
        flex: 1.5,
        minWidth: 140,
        sortable: false,
        renderCell: params => {
          const test = params.row;
          if (!test.tags || test.tags.length === 0) {
            return null;
          }

          const validTags = test.tags.filter(
            (tag: Tag) => tag && tag.id && tag.name
          );

          return (
            <Box
              sx={{
                display: 'flex',
                gap: 0.5,
                flexWrap: 'nowrap',
                overflow: 'hidden',
              }}
            >
              {validTags.slice(0, 2).map((tag: Tag) => (
                <TagLabel key={tag.id} label={tag.name} />
              ))}
              {validTags.length > 2 && (
                <TagLabel label={`+${validTags.length - 2}`} />
              )}
            </Box>
          );
        },
      },
    ],
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
