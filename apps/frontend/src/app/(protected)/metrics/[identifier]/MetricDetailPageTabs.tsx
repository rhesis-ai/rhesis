'use client';

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  fetchMetricLinkedRequirements,
  type LinkedRequirementRow,
  type MetricTuningData,
} from './metric-data';
import { useRouter } from 'next/navigation';
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
import { LinkOffIcon, RouteIcon } from '@/components/icons';
import LinkedEntitiesGrid from '@/components/common/LinkedEntitiesGrid';
import AssignEntityDrawer from '@/components/common/AssignEntityDrawer';
import LinkedEntitiesFilterDrawer, {
  type LinkedFilterSectionConfig,
  type LinkedFilterValues,
  emptyLinkedFilters,
  hasActiveLinkedFilters,
  countActiveLinkedFilters,
} from '@/components/common/LinkedEntitiesFilterDrawer';
import { MetricDetailView } from './MetricDetailView';
import MetricTuningTab from './tuning/MetricTuningTab';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import { RequirementClient } from '@/utils/api-client/requirement-client';
import { API_ENDPOINTS } from '@/utils/api-client/config';
import { useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import { BetaBadge } from '@/components/common/BetaBadge';
import PageLoadingState from '@/components/common/PageLoadingState';
import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { Status } from '@/utils/api-client/interfaces/status';
import type { UUID } from 'crypto';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

const TAB_KEYS = ['basic', 'linked-requirements', 'tuning'] as const;

const NAV_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  basic: 'Basic Information',
  'linked-requirements': 'Linked Requirements',
  tuning: 'Tuning',
};

export default function MetricDetailPageTabs({
  metricId,
  initialMetric,
  initialRequirements,
  initialTuning,
}: {
  metricId: string;
  /** Fetched by the server page so the first paint already has content. */
  initialMetric: MetricDetail;
  /** Same, for the other tabs; undefined falls back to a client fetch. */
  initialRequirements?: LinkedRequirementRow[];
  initialTuning?: MetricTuningData;
}) {
  const { status } = useSession();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Metric.READ
  );

  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);
  // Bumped when a tab writes the metric, so the detail view re-reads it instead
  // of serving the copy it fetched on mount.
  const [metricRevision, setMetricRevision] = useState(0);
  // This page also serves `rhesis` metrics, and the tuning routes refuse
  // anything that is not custom. Tuning rewrites the prompt, never the backend
  // type, so the server-fetched copy stays authoritative.
  const showTuning =
    initialMetric.backend_type?.type_value?.toLowerCase() === 'custom';

  const navTabs = TAB_KEYS.filter(key => key !== 'tuning' || showTuning).map(
    (key, index) => ({
      key,
      label: NAV_LABELS[key],
      // Beta belongs on the tab, not inside the panel: it qualifies the whole
      // feature, and in the panel header it read as a label on the buttons.
      ...(key === 'tuning' && { badge: <BetaBadge /> }),
      id: `metric-detail-tab-${index}`,
      'aria-controls': `metric-detail-tabpanel-${index}`,
    })
  );

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="metrics" />;

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
      initialMetric={initialMetric}
      mode="page"
      refreshKey={metricRevision}
      tabNav={tabNav}
      tabBody={
        activeTab === 1 ? (
          <MetricLinkedRequirements
            metricId={metricId}
            sessionStatus={status}
            initialRequirements={initialRequirements}
          />
        ) : activeTab === 2 && showTuning ? (
          <MetricTuningTab
            metricId={metricId}
            initialData={initialTuning}
            onMetricChanged={() => setMetricRevision(revision => revision + 1)}
          />
        ) : undefined
      }
    />
  );
}

function MetricLinkedRequirements({
  metricId,
  sessionStatus,
  initialRequirements,
}: {
  metricId: string;
  sessionStatus: 'loading' | 'authenticated' | 'unauthenticated';
  initialRequirements?: LinkedRequirementRow[];
}) {
  const router = useRouter();
  const notifications = useNotifications();
  const canEditMetric = useCan(Capability.Metric.UPDATE);
  const [requirements, setRequirements] = useState<LinkedRequirementRow[]>(
    initialRequirements ?? []
  );
  const [loading, setLoading] = useState(!initialRequirements);
  // The metric id the server-rendered rows belong to: no mount fetch for it.
  const seededMetricIdRef = useRef(initialRequirements ? metricId : null);

  // Assign drawer state
  const [assignOpen, setAssignOpen] = useState(false);
  const [available, setAvailable] = useState<RequirementWithMetrics[]>([]);
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
    if (!isAuthenticated(sessionStatus)) return;
    setLoading(true);
    try {
      setRequirements(
        await fetchMetricLinkedRequirements(new ApiClientFactory(), metricId)
      );
    } catch {
      setRequirements([]);
    } finally {
      setLoading(false);
    }
  }, [metricId, sessionStatus]);

  useEffect(() => {
    if (seededMetricIdRef.current === metricId) return;
    fetchLinked();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on mount / id change
  }, [metricId]);

  const handleUnassign = useCallback(
    async (requirementId: string) => {
      try {
        const client = new MetricsClient();
        await client.removeRequirementFromMetric(
          metricId as UUID,
          requirementId as UUID
        );
        setRequirements(prev =>
          prev.filter(b => String(b.id) !== requirementId)
        );
        notifications.show('Requirement unassigned', {
          severity: 'success',
          autoHideDuration: 4000,
        });
      } catch (error) {
        notifications.show(
          error instanceof Error
            ? `Failed to unassign requirement: ${error.message}`
            : 'Failed to unassign requirement',
          { severity: 'error', autoHideDuration: 6000 }
        );
      }
    },
    [metricId, notifications]
  );

  // Linked requirements columns
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
        canDelete: () => canEditMetric,
        onDelete: id => handleUnassign(id),
        deleteTooltip: 'Unassign',
        deleteIcon: LinkOffIcon,
      }),
    ],
    [handleUnassign, canEditMetric]
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
    () => new Set(requirements.map(b => String(b.id))),
    [requirements]
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
      const client = new RequirementClient();
      const result = await client.getRequirements({ skip: 0, limit: 100 });
      setAvailable(result);
    } catch {
      setAvailable([]);
    } finally {
      setLoadingAvailable(false);
    }
  }, []);

  const handleAssign = useCallback(
    async (selectedIds: string[]) => {
      const client = new MetricsClient();
      await Promise.all(
        selectedIds.map(id =>
          client.addRequirementToMetric(metricId as UUID, id as UUID)
        )
      );
      await fetchLinked();
      setAssignOpen(false);
    },
    [metricId, fetchLinked]
  );

  // Filter drawer: Status only (linked requirements have no other filterable field)
  const filterSections: LinkedFilterSectionConfig[] = useMemo(() => {
    const statusNames = Array.from(
      new Set(
        requirements
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
  }, [requirements]);

  const rowFilter = useCallback(
    (row: GridRowModel) => {
      const statuses = appliedFilters.status ?? [];
      if (statuses.length === 0) return true;
      const statusName = (row.status as Status | null | undefined)?.name ?? '';
      return statuses.includes(statusName);
    },
    [appliedFilters]
  );

  // Assign-drawer filter sections derived from available (unlinked) requirements
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
        title="Linked Requirements"
        rows={requirements as GridRowModel[]}
        columns={linkedColumns}
        loading={loading}
        getRowId={row => String(row.id)}
        onRowClick={params =>
          router.push(`${API_ENDPOINTS.requirements}/${String(params.id)}`)
        }
        onAssignClick={canEditMetric ? handleAssignClick : undefined}
        searchPlaceholder="Search requirements…"
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
              No requirements assigned yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              No requirements have been assigned to this metric yet. Click
              Assign to link a requirement.
            </Typography>
          </Box>
        }
      />

      <AssignEntityDrawer
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        title="Assign Requirement"
        rows={availableFiltered}
        columns={drawerColumns}
        loading={loadingAvailable}
        getRowId={row => String(row.id)}
        onAssign={handleAssign}
        searchPlaceholder="Search requirements…"
        rowFilter={assignRowFilter}
        onFilterClick={() => setAssignFilterOpen(true)}
        hasActiveFilters={hasActiveLinkedFilters(assignFilters)}
        activeFilterCount={countActiveLinkedFilters(assignFilters)}
        onCreateNew={() => router.push(API_ENDPOINTS.requirements)}
        createNewLabel="Create new requirement"
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
