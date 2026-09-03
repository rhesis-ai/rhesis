'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { GridColDef, GridRowModel } from '@mui/x-data-grid';
import { Box, Tooltip, Typography, Avatar, Chip } from '@mui/material';
import {
  ChatIcon,
  DescriptionIcon,
  HorizontalSplitIcon,
} from '@/components/icons';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import PersonIcon from '@mui/icons-material/Person';
import { useSession } from 'next-auth/react';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import RunDrawer from '@/components/common/RunDrawer';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import type { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Tag } from '@/utils/api-client/interfaces/tag';
import { NotificationSection } from '@/constants/notifications';
import { formatDate } from '@/utils/date';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { TEST_TYPE_PILL_TABS } from '@/constants/test-types';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import type { BulkDeleteActionsState } from '@/hooks/useBulkDelete';
import { testSetsList } from './list';
import TestSetFilterDrawer, {
  type TestSetFilters,
  EMPTY_TEST_SET_FILTERS,
  countActiveTestSetFilters,
} from './TestSetFilterDrawer';

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

export interface TestSetsBulkActionsState extends BulkDeleteActionsState {
  onRun: () => void;
}

// A pill click wins over the drawer's own testSetType value (the pill is
// applied after drawer filters).
function toFilters(state: EntityGridFilterState<TestSetFilters>) {
  return {
    search: state.search,
    testSetType: state.pill || state.drawer.testSetType,
    status: state.drawer.status,
    creator: state.drawer.creator,
    tag: state.drawer.tag,
    tagsPresence: state.drawer.tags,
    commentsPresence: state.drawer.comments,
    tasksPresence: state.drawer.tasks,
  };
}

const drawerAdapter: EntityGridDrawerAdapter<TestSetFilters> = {
  empty: EMPTY_TEST_SET_FILTERS,
  countActive: countActiveTestSetFilters,
  render: props => (
    <TestSetFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
  // Applying a type in the drawer syncs the pill; clearing it resets the pill
  // only when no drawer type was active before.
  pillFromApply: (applied, previous) =>
    applied.testSetType
      ? applied.testSetType
      : !previous.testSetType
        ? ''
        : undefined,
};

// The grid renders a flattened projection of the test set, not the entity
// itself -- most columns live under attributes.metadata.
function mapRows(testSets: TestSet[]): GridRowModel[] {
  return testSets.map(testSet => ({
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
  }));
}

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
  const { status } = useSession();
  const canEditTestSet = useCan(Capability.TestSet.UPDATE);
  const [testRunDrawerOpen, setTestRunDrawerOpen] = useState(false);

  const buildBulkActions = useCallback(
    (base: BulkDeleteActionsState): TestSetsBulkActionsState => ({
      ...base,
      onRun: () => setTestRunDrawerOpen(true),
    }),
    []
  );

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 2,
        minWidth: 120,
        filterable: true,
      },
      {
        field: 'requirements',
        headerName: 'Requirements',
        flex: 1.5,
        minWidth: 100,
        sortable: false,
        renderCell: params => (
          <ChipContainer items={params.row.requirements || []} />
        ),
      },
      {
        field: 'categories',
        headerName: 'Categories',
        flex: 1.5,
        minWidth: 100,
        sortable: false,
        renderCell: params => (
          <ChipContainer items={params.row.categories || []} />
        ),
      },
      {
        field: 'testSetType',
        headerName: 'Type',
        flex: 1,
        minWidth: 90,
        filterable: true,
        sortable: false,
        valueGetter: (_, row) => row.testSetType || '',
        renderCell: params =>
          params.value ? <GridBadge label={params.value} /> : null,
      },
      {
        field: 'created_at',
        headerName: 'Created',
        flex: 1,
        minWidth: 100,
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
        flex: 0.6,
        minWidth: 60,
        sortable: false,
        valueGetter: (_, row) => row.totalTests,
      },
      {
        field: 'creator',
        headerName: 'Creator',
        flex: 1.5,
        minWidth: 120,
        sortable: false,
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
        flex: 0.8,
        minWidth: 80,
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
        flex: 0.8,
        minWidth: 80,
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
        flex: 0.6,
        minWidth: 60,
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
        flex: 1.5,
        minWidth: 140,
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
    ],
    []
  );

  return (
    <EntityGrid<
      TestSet,
      typeof testSetsList.filters,
      TestSetFilters,
      TestSetsBulkActionsState
    >
      descriptor={testSetsList}
      columns={columns}
      toFilters={toFilters}
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
      initialData={initialData}
      initialTotalCount={initialTotalCount}
      refreshTrigger={refreshTrigger}
      mapRows={mapRows}
      searchPlaceholder="Search test sets…"
      pills={{ tabs: TEST_TYPE_PILL_TABS }}
      drawer={drawerAdapter}
      selectionLabel="Select test sets"
      getRowUrl={row => `/test-sets/${row.id}`}
      highlightSection={NotificationSection.TEST_SETS}
      editAction={{ can: () => canEditTestSet }}
      onBulkActionsChange={onBulkActionsChange}
      buildBulkActions={buildBulkActions}
      pageSizeOptions={[10, 25, 50]}
      initialState={{
        columns: {
          columnVisibilityModel: {
            sources: false,
          },
        },
      }}
      renderSelectionExtras={ctx =>
        isAuthenticated(status) && (
          <RunDrawer
            mode="createFromGrid"
            open={testRunDrawerOpen}
            onClose={() => setTestRunDrawerOpen(false)}
            data={{ selectedTestSetIds: ctx.selectedIds }}
            onSuccess={() => setTestRunDrawerOpen(false)}
          />
        )
      }
    />
  );
}
