'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Box, Typography } from '@mui/material';
import { useSession } from 'next-auth/react';
import {
  GridColDef,
  GridRenderCellParams,
  GridRowModel,
} from '@mui/x-data-grid';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import DetailTabNav from '@/components/common/DetailTabNav';
import { useNotifications } from '@/components/common/NotificationContext';
import { createRowActionsColumn } from '@/components/common/createRowActionsColumn';
import LinkedEntitiesGrid from '@/components/common/LinkedEntitiesGrid';
import AssignEntityDrawer from '@/components/common/AssignEntityDrawer';
import LinkedEntitiesFilterDrawer, {
  type LinkedFilterSectionConfig,
  type LinkedFilterValues,
  emptyLinkedFilters,
  hasActiveLinkedFilters,
  countActiveLinkedFilters,
} from '@/components/common/LinkedEntitiesFilterDrawer';
import { RouteIcon } from '@/components/icons';
import { MetricDetailView } from './MetricDetailView';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import type {
  BehaviorReference,
  BehaviorWithMetrics,
} from '@/utils/api-client/interfaces/behavior';
import type { Status } from '@/utils/api-client/interfaces/status';
import type { UUID } from 'crypto';

/** Linked behaviors come back with the status relationship at runtime. */
type LinkedBehaviorRow = BehaviorReference & { status?: Status | null };

const TAB_KEYS = ['basic', 'linked-behaviors'] as const;

const NAV_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  basic: 'Basic Information',
  'linked-behaviors': 'Linked Behaviors',
};

export default function MetricDetailPageTabs() {
  const params = useParams();
  const { data: session } = useSession();

  const metricId = params.identifier as string;
  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label: NAV_LABELS[key],
    id: `metric-detail-tab-${index}`,
    'aria-controls': `metric-detail-tabpanel-${index}`,
  }));

  const sessionToken = session?.session_token ?? '';

  const tabNav = (
    <DetailTabNav
      tabs={navTabs}
      activeIndex={activeTab}
      onChange={handleTabChange}
      aria-label="Metric detail tabs"
    />
  );

  return (
    <MetricDetailView
      metricId={metricId}
      mode="page"
      tabNav={tabNav}
      tabBody={
        activeTab === 1 ? (
          <MetricLinkedBehaviors
            metricId={metricId}
            sessionToken={sessionToken}
          />
        ) : undefined
      }
    />
  );
}

function MetricLinkedBehaviors({
  metricId,
  sessionToken,
}: {
  metricId: string;
  sessionToken: string;
}) {
  const router = useRouter();
  const notifications = useNotifications();
  const [behaviors, setBehaviors] = useState<LinkedBehaviorRow[]>([]);
  const [loading, setLoading] = useState(true);

  // Assign drawer state
  const [assignOpen, setAssignOpen] = useState(false);
  const [available, setAvailable] = useState<BehaviorWithMetrics[]>([]);
  const [loadingAvailable, setLoadingAvailable] = useState(false);

  // Filter drawer state
  const [filterOpen, setFilterOpen] = useState(false);
  const [appliedFilters, setAppliedFilters] = useState<LinkedFilterValues>({
    status: [],
  });

  // Assign-drawer filter state (independent of the linked-grid filters)
  const [assignFilterOpen, setAssignFilterOpen] = useState(false);
  const [assignFilters, setAssignFilters] = useState<LinkedFilterValues>({
    status: [],
  });

  const fetchLinked = useCallback(async () => {
    if (!sessionToken) return;
    setLoading(true);
    try {
      const client = new MetricsClient(sessionToken);
      const result = await client.getMetricBehaviors(metricId as UUID);
      const data =
        (result as unknown as { data: LinkedBehaviorRow[] }).data ?? [];
      setBehaviors(data);
    } catch {
      setBehaviors([]);
    } finally {
      setLoading(false);
    }
  }, [metricId, sessionToken]);

  useEffect(() => {
    fetchLinked();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on mount / id change
  }, [metricId, sessionToken]);

  const handleUnassign = useCallback(
    async (behaviorId: string) => {
      try {
        const client = new MetricsClient(sessionToken);
        await client.removeBehaviorFromMetric(
          metricId as UUID,
          behaviorId as UUID
        );
        setBehaviors(prev => prev.filter(b => String(b.id) !== behaviorId));
        notifications.show('Behavior unassigned', {
          severity: 'success',
          autoHideDuration: 4000,
        });
      } catch (error) {
        notifications.show(
          error instanceof Error
            ? `Failed to unassign behavior: ${error.message}`
            : 'Failed to unassign behavior',
          { severity: 'error', autoHideDuration: 6000 }
        );
      }
    },
    [metricId, sessionToken, notifications]
  );

  // Linked behaviors columns
  const linkedColumns = useMemo<GridColDef[]>(
    () => [
      { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
      {
        field: 'description',
        headerName: 'Description',
        flex: 2,
        minWidth: 200,
        renderCell: (params: GridRenderCellParams) => (
          <Box
            title={typeof params.value === 'string' ? params.value : ''}
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {typeof params.value === 'string' ? params.value : '—'}
          </Box>
        ),
      },
      createRowActionsColumn({
        onDelete: id => handleUnassign(id),
        deleteTooltip: 'Unassign',
      }),
    ],
    [handleUnassign]
  );

  // Assign drawer columns (no actions)
  const drawerColumns = useMemo<GridColDef[]>(
    () => [
      { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
      {
        field: 'description',
        headerName: 'Description',
        flex: 2,
        minWidth: 200,
      },
    ],
    []
  );

  const linkedIds = useMemo(
    () => new Set(behaviors.map(b => String(b.id))),
    [behaviors]
  );

  const availableFiltered: GridRowModel[] = useMemo(
    () => available.filter(b => !linkedIds.has(String(b.id))),
    [available, linkedIds]
  );

  const handleAssignClick = useCallback(async () => {
    setLoadingAvailable(true);
    setAssignOpen(true);
    setAssignFilters({ status: [] });
    try {
      const client = new BehaviorClient(sessionToken);
      const result = await client.getBehaviors({ skip: 0, limit: 100 });
      setAvailable(result);
    } catch {
      setAvailable([]);
    } finally {
      setLoadingAvailable(false);
    }
  }, [sessionToken]);

  const handleAssign = useCallback(
    async (selectedIds: string[]) => {
      const client = new MetricsClient(sessionToken);
      await Promise.all(
        selectedIds.map(id =>
          client.addBehaviorToMetric(metricId as UUID, id as UUID)
        )
      );
      await fetchLinked();
      setAssignOpen(false);
    },
    [metricId, sessionToken, fetchLinked]
  );

  // Filter drawer: Status only (linked behaviors have no other filterable field)
  const filterSections: LinkedFilterSectionConfig[] = useMemo(() => {
    const statusNames = Array.from(
      new Set(
        behaviors
          .map(b => b.status?.name)
          .filter((name): name is string => !!name)
      )
    ).sort();
    return [
      {
        key: 'status',
        title: 'Status',
        options: statusNames.map(name => ({ value: name, label: name })),
      },
    ];
  }, [behaviors]);

  const rowFilter = useCallback(
    (row: GridRowModel) => {
      const statuses = appliedFilters.status ?? [];
      if (statuses.length === 0) return true;
      const statusName = (row.status as Status | null | undefined)?.name ?? '';
      return statuses.includes(statusName);
    },
    [appliedFilters]
  );

  // Assign-drawer filter sections derived from available (unlinked) behaviors
  const assignFilterSections: LinkedFilterSectionConfig[] = useMemo(() => {
    const statusNames = Array.from(
      new Set(
        availableFiltered
          .map(b => (b.status as Status | null | undefined)?.name)
          .filter((name): name is string => !!name)
      )
    ).sort();
    return [
      {
        key: 'status',
        title: 'Status',
        options: statusNames.map(name => ({ value: name, label: name })),
      },
    ];
  }, [availableFiltered]);

  const assignRowFilter = useCallback(
    (row: GridRowModel) => {
      const statuses = assignFilters.status ?? [];
      if (statuses.length === 0) return true;
      const statusName = (row.status as Status | null | undefined)?.name ?? '';
      return statuses.includes(statusName);
    },
    [assignFilters]
  );

  return (
    <>
      <LinkedEntitiesGrid
        title="Linked Behaviors"
        rows={behaviors as GridRowModel[]}
        columns={linkedColumns}
        loading={loading}
        getRowId={row => String(row.id)}
        onRowClick={params => router.push(`/behaviors/${String(params.id)}`)}
        onAssignClick={handleAssignClick}
        searchPlaceholder="Search behaviors…"
        rowFilter={rowFilter}
        onFilterClick={() => setFilterOpen(true)}
        hasActiveFilters={hasActiveLinkedFilters(appliedFilters)}
        activeFilterCount={countActiveLinkedFilters(appliedFilters)}
        emptyState={
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              py: 5,
              gap: 2,
              textAlign: 'center',
            }}
          >
            <RouteIcon sx={{ fontSize: 32, color: 'primary.main' }} />
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              No behaviors assigned yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              No behaviors have been assigned to this metric yet. Click Assign
              to link a behavior.
            </Typography>
          </Box>
        }
      />

      <AssignEntityDrawer
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        title="Assign Behavior"
        rows={availableFiltered}
        columns={drawerColumns}
        loading={loadingAvailable}
        getRowId={row => String(row.id)}
        onAssign={handleAssign}
        searchPlaceholder="Search behaviors…"
        rowFilter={assignRowFilter}
        onFilterClick={() => setAssignFilterOpen(true)}
        hasActiveFilters={hasActiveLinkedFilters(assignFilters)}
        activeFilterCount={countActiveLinkedFilters(assignFilters)}
        onCreateNew={() => router.push('/behaviors')}
        createNewLabel="Create new behavior"
      />

      <LinkedEntitiesFilterDrawer
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        sections={filterSections}
        filters={appliedFilters}
        onApply={next =>
          setAppliedFilters(next ?? emptyLinkedFilters(filterSections))
        }
      />

      <LinkedEntitiesFilterDrawer
        open={assignFilterOpen}
        onClose={() => setAssignFilterOpen(false)}
        sections={assignFilterSections}
        filters={assignFilters}
        onApply={next =>
          setAssignFilters(next ?? emptyLinkedFilters(assignFilterSections))
        }
      />
    </>
  );
}
