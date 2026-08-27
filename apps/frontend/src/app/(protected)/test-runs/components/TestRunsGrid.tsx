'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { GridColDef } from '@mui/x-data-grid';
import {
  Typography,
  Box,
  Avatar,
  Chip,
  Button,
  ButtonGroup,
  Tooltip,
} from '@mui/material';
import ListIcon from '@mui/icons-material/List';
import PersonIcon from '@mui/icons-material/Person';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import TagLabel from '@/components/common/Tag';
import { DeleteModal } from '@/components/common/DeleteModal';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import {
  ChatIcon,
  DescriptionIcon,
  ScienceIcon,
  BiotechIcon,
  PlayArrowIcon,
} from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { NotificationSection } from '@/constants/notifications';
import { TestRun, TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { can } from '@/utils/affordances';
import { Capability } from '@/constants/capabilities';
import { Tag } from '@/utils/api-client/interfaces/tag';
import type { BulkDeleteActionsState } from '@/hooks/useBulkDelete';
import { testRunsList } from './list';
import TestRunFilterDrawer, {
  type TestRunFilters,
  EMPTY_TEST_RUN_FILTERS,
  countActiveTestRunFilters,
} from './TestRunFilterDrawer';
import { passRate } from '@/constants/outcomes';

type RunKindFilter = 'all' | 'tests' | 'experiments';

interface TestRunsGridProps {
  canCreate?: boolean;
  onCreateClick?: () => void;
  onBulkActionsChange?: (actions: BulkDeleteActionsState) => void;
  /** Bumped by the page after a cancel succeeds, to trigger a re-fetch. */
  refreshTrigger?: number;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: TestRunDetail[];
  initialTotalCount?: number;
}

function formatReviewTooltip(reviewed: number, corrected: number): string {
  const reviewedLabel = `${reviewed} test${reviewed === 1 ? '' : 's'} reviewed`;
  if (corrected > 0) {
    return `${reviewedLabel} · ${corrected} corrected`;
  }
  return reviewedLabel;
}

const STATUS_TABS = [
  { label: 'All', value: 'all' },
  { label: 'In Progress', value: 'Progress' },
  { label: 'Completed', value: 'Completed' },
  { label: 'Partial', value: 'Partial' },
  { label: 'Failed', value: 'Failed' },
];

function toFilters(state: EntityGridFilterState<TestRunFilters>) {
  return {
    search: state.search,
    status: state.pill,
    testSet: state.drawer.testSet,
    executor: state.drawer.executor,
    tag: state.drawer.tag,
    tagsPresence: state.drawer.tags,
    commentsPresence: state.drawer.comments,
    tasksPresence: state.drawer.tasks,
    // Owned by the toolbar's run-kind toggle, merged in via externalFilters.
    runKind: 'all',
    reviews: state.drawer.reviews ?? 'all',
  };
}

const drawerAdapter: EntityGridDrawerAdapter<TestRunFilters> = {
  empty: EMPTY_TEST_RUN_FILTERS,
  countActive: countActiveTestRunFilters,
  render: props => (
    <TestRunFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
};

function isCancellableRun(row: Record<string, unknown>): boolean {
  const statusName = (
    (row.status as { name?: string } | undefined)?.name ?? ''
  ).toLowerCase();
  return statusName === 'queued' || statusName === 'progress';
}

export default function TestRunsGrid({
  canCreate,
  onCreateClick,
  onBulkActionsChange,
  refreshTrigger,
  initialData,
  initialTotalCount,
}: TestRunsGridProps) {
  const notifications = useNotifications();

  const [runKindFilter, setRunKindFilter] = useState<RunKindFilter>('all');
  const [pendingCancelId, setPendingCancelId] = useState<string | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  const externalFilters = useMemo(
    () => ({ runKind: runKindFilter }),
    [runKindFilter]
  );

  const runKindToolbar = useMemo(
    () => (
      <ButtonGroup size="small" variant="outlined">
        <Button
          onClick={() => setRunKindFilter('all')}
          variant={runKindFilter === 'all' ? 'contained' : 'outlined'}
          startIcon={<ListIcon fontSize="small" />}
        >
          All
        </Button>
        <Button
          onClick={() => setRunKindFilter('tests')}
          variant={runKindFilter === 'tests' ? 'contained' : 'outlined'}
          startIcon={<ScienceIcon fontSize="small" />}
        >
          Tests
        </Button>
        <Button
          onClick={() => setRunKindFilter('experiments')}
          variant={runKindFilter === 'experiments' ? 'contained' : 'outlined'}
          startIcon={<BiotechIcon fontSize="small" />}
        >
          Experiments
        </Button>
      </ButtonGroup>
    ),
    [runKindFilter]
  );

  const handleCancelClose = useCallback(() => {
    setPendingCancelId(null);
  }, []);

  const makeCancelConfirm = useCallback(
    (refresh: () => void) => async () => {
      if (!pendingCancelId) return;
      try {
        setIsCancelling(true);
        await new ApiClientFactory()
          .getTestRunsClient()
          .cancelTestRun(pendingCancelId);
        notifications.show('Successfully cancelled test run', {
          severity: 'success',
        });
        refresh();
      } catch {
        notifications.show('Failed to cancel test run', { severity: 'error' });
      } finally {
        setIsCancelling(false);
        setPendingCancelId(null);
      }
    },
    [pendingCancelId, notifications]
  );

  const extraRowActions = useMemo(
    () => [
      {
        key: 'cancel',
        icon: StopCircleOutlinedIcon,
        tooltip: 'Cancel',
        onClick: (id: string) => setPendingCancelId(id),
        can: isCancellableRun,
      },
    ],
    []
  );

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        width: 180,
        minWidth: 120,
        resizable: true,
        filterable: true,
        valueGetter: (_, row) => row.name || '',
      },
      {
        field: 'test_configuration.test_set.name',
        headerName: 'Test Sets',
        width: 160,
        minWidth: 100,
        resizable: true,
        filterable: true,
        valueGetter: (_, row) => {
          const testSet = row.test_configuration?.test_set;
          return testSet?.name || '';
        },
      },
      {
        field: 'total_tests',
        headerName: 'Total Tests',
        width: 110,
        minWidth: 80,
        resizable: true,
        align: 'right',
        headerAlign: 'right',
        valueGetter: (_, row) => {
          const attributes = row?.attributes;
          return attributes?.total_tests || 0;
        },
      },
      {
        field: 'pass_rate',
        headerName: 'Pass Rate',
        width: 110,
        minWidth: 90,
        resizable: true,
        align: 'right',
        headerAlign: 'right',
        sortable: false,
        filterable: false,
        valueGetter: (_, row) => {
          const stats = row.stats;
          if (!stats) return null;
          return passRate(stats.passed, stats.failed);
        },
        renderCell: params => {
          const value = params.value as number | null;
          if (value === null || value === undefined) {
            return (
              <Typography variant="body2" color="text.secondary">
                —
              </Typography>
            );
          }
          return <Typography variant="body2">{value.toFixed(1)}%</Typography>;
        },
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        minWidth: 90,
        resizable: true,
        renderCell: params => {
          const status = params.row.status?.name;
          if (!status) return null;

          return <GridBadge label={status} />;
        },
      },
      {
        field: 'test_set_type',
        headerName: 'Type',
        width: 120,
        minWidth: 90,
        resizable: true,
        filterable: true,
        valueGetter: (_, row) => {
          return (
            row.test_configuration?.test_set?.test_set_type?.type_value || ''
          );
        },
        renderCell: params => {
          const testSetType =
            params.row.test_configuration?.test_set?.test_set_type?.type_value;

          if (!testSetType) return null;

          return <GridBadge label={testSetType} />;
        },
      },
      {
        field: 'experiment',
        headerName: 'Experiment',
        flex: 1,
        sortable: false,
        filterable: false,
        valueGetter: (_, row) => {
          if (!row.experiment_id) return '';
          const name =
            (row.attributes?.parameter_experiment_name as string) || '';
          const ver = (row.attributes?.parameter_version as string) || '';
          return `${name} ${ver}`.trim();
        },
        renderCell: params => {
          if (!params.row.experiment_id) return null;
          const name =
            (params.row.attributes?.parameter_experiment_name as string) ||
            undefined;
          const version = params.row.attributes?.parameter_version as
            string | undefined;

          if (!name && !version) return null;

          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
              }}
            >
              {name && (
                <Typography
                  variant="body2"
                  sx={{ fontSize: theme => theme.typography.body2.fontSize }}
                  noWrap
                >
                  {name}
                </Typography>
              )}
              {version && (
                <Chip
                  label={version}
                  size="small"
                  variant="outlined"
                  sx={{ height: 20, '& .MuiChip-label': { px: 0.75 } }}
                />
              )}
            </Box>
          );
        },
      },
      {
        field: 'user.name',
        headerName: 'Executor',
        width: 160,
        minWidth: 120,
        resizable: true,
        filterable: true,
        valueGetter: (_, row) => {
          const executor = row.user;
          if (!executor) return '';
          return (
            executor.name ||
            `${executor.given_name || ''} ${executor.family_name || ''}`.trim() ||
            executor.email
          );
        },
        renderCell: params => {
          const executor = params.row.user;
          if (!executor) return null;

          const displayName =
            executor.name ||
            `${executor.given_name || ''} ${executor.family_name || ''}`.trim() ||
            executor.email;

          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Avatar src={executor.picture} sx={{ width: 24, height: 24 }}>
                <PersonIcon />
              </Avatar>
              <Typography variant="body2">{displayName}</Typography>
            </Box>
          );
        },
      },
      {
        field: 'counts.reviewed_tests',
        headerName: 'Reviews',
        width: 100,
        minWidth: 80,
        resizable: true,
        sortable: false,
        filterable: false,
        valueGetter: (_, row) => row.counts?.reviewed_tests ?? 0,
        renderCell: params => {
          const reviewed = params.row.counts?.reviewed_tests || 0;
          if (reviewed === 0) return null;

          const corrected = params.row.counts?.corrected_tests || 0;
          const iconColor = corrected > 0 ? 'primary.dark' : 'text.secondary';

          return (
            <Tooltip title={formatReviewTooltip(reviewed, corrected)}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  width: '100%',
                }}
              >
                <RateReviewOutlinedIcon
                  sx={{ fontSize: 16, color: iconColor }}
                />
                <Typography variant="body2">{reviewed}</Typography>
              </Box>
            </Tooltip>
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
        field: 'tags',
        headerName: 'Tags',
        width: 180,
        minWidth: 140,
        resizable: true,
        sortable: true,
        filterable: true,
        valueGetter: (_, row) =>
          row.tags?.filter((tag: Tag) => tag && tag.id && tag.name).length ?? 0,
        renderCell: params => {
          const testRun = params.row as TestRunDetail;
          if (!testRun.tags || testRun.tags.length === 0) {
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
              {testRun.tags
                .filter((tag: Tag) => tag && tag.id && tag.name)
                .slice(0, 2)
                .map((tag: Tag) => (
                  <TagLabel key={tag.id} label={tag.name} />
                ))}
              {testRun.tags.filter((tag: Tag) => tag && tag.id && tag.name)
                .length > 2 && (
                <TagLabel
                  label={`+${testRun.tags.filter((tag: Tag) => tag && tag.id && tag.name).length - 2}`}
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
    <EntityGrid<TestRunDetail, typeof testRunsList.filters, TestRunFilters>
      descriptor={testRunsList}
      columns={columns}
      toFilters={toFilters}
      externalFilters={externalFilters}
      emptyState={
        <EntityEmptyState
          card
          icon={PlayArrowIcon}
          title="No test runs yet"
          description="Execute a test set against an AI endpoint to start your first test run. Test runs measure quality, safety, and reliability of your AI endpoints."
          actionLabel={canCreate ? 'Create test run' : undefined}
          onAction={canCreate ? onCreateClick : undefined}
          enrichment={getEntityEmptyStateEnrichment('test-runs')}
        />
      }
      initialData={initialData}
      initialTotalCount={initialTotalCount}
      refreshTrigger={refreshTrigger}
      searchPlaceholder="Search test runs…"
      pills={{ tabs: STATUS_TABS }}
      drawer={drawerAdapter}
      toolbarRight={runKindToolbar}
      selectionLabel="Select test runs"
      getRowUrl={row => `/test-runs/${row.id}`}
      highlightSection={NotificationSection.TEST_RUNS}
      editAction={{
        can: (row: TestRunDetail) =>
          can(row as TestRun, Capability.TestRun.UPDATE),
      }}
      extraRowActions={extraRowActions}
      rowActionsWidth={112}
      onBulkActionsChange={onBulkActionsChange}
      storageKey="test-runs-grid-v2"
      pageSizeOptions={[10, 25, 50]}
      renderSelectionExtras={ctx => (
        <DeleteModal
          open={pendingCancelId !== null}
          onClose={handleCancelClose}
          onConfirm={makeCancelConfirm(ctx.refresh)}
          isLoading={isCancelling}
          title="Cancel Test Run"
          message="Are you sure you want to cancel this test run? It will be stopped and marked as Cancelled."
          itemType="test run"
          confirmButtonText={isCancelling ? 'Cancelling...' : 'Cancel Run'}
          cancelButtonText="Keep Running"
        />
      )}
    />
  );
}
