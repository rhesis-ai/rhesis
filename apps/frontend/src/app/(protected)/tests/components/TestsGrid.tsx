'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { Typography, Box, Alert, Chip } from '@mui/material';
import { useSession } from 'next-auth/react';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
  type EntityGridSelectionContext,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { Tag } from '@/utils/api-client/interfaces/tag';
import {
  AttachFileIcon,
  ChatIcon,
  DescriptionIcon,
  ScienceIcon,
} from '@/components/icons';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import TestDrawer from './TestDrawer';
import TestSetSelectionDrawer from './TestSetSelectionDrawer';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { TestSetsClient } from '@/utils/api-client/test-sets-client';
import { useNotifications } from '@/components/common/NotificationContext';
import { testsList } from './list';
import TestFilterDrawer, {
  type TestFilters,
  EMPTY_TEST_FILTERS,
  countActiveTestFilters,
} from './TestFilterDrawer';
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
import type { BulkDeleteActionsState } from '@/hooks/useBulkDelete';

interface TestsTableProps {
  onNewTest?: () => void;
  disableAddButton?: boolean;
  canCreate?: boolean;
  insightsFailedFilter?: InsightsFailedTestsFilter | null;
  insightsEndpointName?: string;
  onBulkActionsChange?: (actions: TestsBulkActionsState) => void;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: TestDetail[];
  initialTotalCount?: number;
}

export interface TestsBulkActionsState extends BulkDeleteActionsState {
  assignDisabled: boolean;
  onAssign: () => void;
}

// A pill click wins over the drawer's own testType value (the pill is applied
// after drawer filters).
function toFilters(state: EntityGridFilterState<TestFilters>) {
  return {
    search: state.search,
    testType: state.pill || state.drawer.testType,
    requirement: state.drawer.requirement,
    category: state.drawer.category,
    topic: state.drawer.topic,
    tagsPresence: state.drawer.tags,
    commentsPresence: state.drawer.comments,
    tasksPresence: state.drawer.tasks,
  };
}

const drawerAdapter: EntityGridDrawerAdapter<TestFilters> = {
  empty: EMPTY_TEST_FILTERS,
  countActive: countActiveTestFilters,
  render: props => (
    <TestFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
  // If the drawer sets a test type, sync the pill tab too.
  pillFromApply: (applied, previous) =>
    applied.testType ? applied.testType : !previous.testType ? '' : undefined,
};

function selectedTestTypes(selectedTests: TestDetail[]) {
  const typeValues = new Set(
    selectedTests.map(t => t.test_type?.type_value ?? null)
  );
  return {
    isMixed: typeValues.size > 1,
    commonTypeValue:
      typeValues.size === 1 ? ([...typeValues][0] ?? undefined) : undefined,
  };
}

export default function TestsTable({
  onNewTest,
  disableAddButton = false,
  canCreate,
  insightsFailedFilter = null,
  insightsEndpointName,
  onBulkActionsChange,
  initialData,
  initialTotalCount,
}: TestsTableProps) {
  const notifications = useNotifications();
  const canEditTest = useCan(Capability.Test.UPDATE);
  const canExport = useCan(Capability.TestSet.EXPORT);
  const { status } = useSession();

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTest, setSelectedTest] = useState<TestDetail | undefined>();
  const [testSetDrawerOpen, setTestSetDrawerOpen] = useState(false);

  // ── Insights deep link: resolve failed-test ids into an extra OData filter ──
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

  const extraFilters = useMemo(
    () => (insightsIdFilter ? [insightsIdFilter] : undefined),
    [insightsIdFilter]
  );

  const insightsBanner = insightsFailedFilter ? (
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
  ) : undefined;

  // ── Edit drawer + bulk assign ───────────────────────────────────────────────
  const handleEditTest = useCallback((_id: string, row: TestDetail) => {
    setSelectedTest(row);
    setDrawerOpen(true);
  }, []);

  const handleDrawerClose = useCallback(() => {
    setDrawerOpen(false);
    setSelectedTest(undefined);
  }, []);

  const buildBulkActions = useCallback(
    (
      base: BulkDeleteActionsState,
      ctx: EntityGridSelectionContext<TestDetail>
    ): TestsBulkActionsState => ({
      ...base,
      assignDisabled: selectedTestTypes(ctx.selectedRows).isMixed,
      onAssign: () => setTestSetDrawerOpen(true),
    }),
    []
  );

  const makeTestSetsAssign = useCallback(
    (ctx: EntityGridSelectionContext<TestDetail>) =>
      async (testSets: TestSet[]) => {
        if (!isAuthenticated(status) || testSets.length === 0) return;

        const testIds = ctx.selectedIds;
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
    [notifications, status]
  );

  // ── Column definitions ──────────────────────────────────────────────────────
  const columns: GridColDef[] = useMemo(
    () => [
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
    ],
    []
  );

  return (
    <EntityGrid<
      TestDetail,
      typeof testsList.filters,
      TestFilters,
      TestsBulkActionsState
    >
      descriptor={testsList}
      columns={columns}
      toFilters={toFilters}
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
      initialData={initialData}
      initialTotalCount={initialTotalCount}
      extraFilters={extraFilters}
      enabled={insightsFilterReady}
      banner={insightsBanner}
      searchPlaceholder="Search tests…"
      pills={{ tabs: TEST_TYPE_PILL_TABS }}
      drawer={drawerAdapter}
      selectionLabel="Select tests"
      showExport={canExport}
      getRowUrl={row => `/tests/${row.id}`}
      editAction={{ onClick: handleEditTest, can: () => canEditTest }}
      onBulkActionsChange={onBulkActionsChange}
      buildBulkActions={buildBulkActions}
      persistState={!insightsFailedFilter}
      pageSizeOptions={[10, 25, 50]}
      initialState={{
        columns: {
          columnVisibilityModel: {
            'test_metadata.sources': false,
          },
        },
      }}
      renderSelectionExtras={ctx =>
        isAuthenticated(status) && (
          <>
            <TestDrawer
              open={drawerOpen}
              onClose={handleDrawerClose}
              test={selectedTest}
              onSuccess={ctx.refresh}
            />
            <TestSetSelectionDrawer
              open={testSetDrawerOpen}
              onClose={() => setTestSetDrawerOpen(false)}
              onSelect={makeTestSetsAssign(ctx)}
              testTypeValue={
                selectedTestTypes(ctx.selectedRows).commonTypeValue
              }
            />
          </>
        )
      }
    />
  );
}
