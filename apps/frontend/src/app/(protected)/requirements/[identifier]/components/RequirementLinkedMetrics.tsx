'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, LinearProgress, Stack, Tooltip, Typography } from '@mui/material';
import {
  GridColDef,
  GridRenderCellParams,
  GridRowModel,
} from '@mui/x-data-grid';
import GridBadge from '@/components/common/GridBadge';
import { useNotifications } from '@/components/common/NotificationContext';
import { createRowActionsColumn } from '@/components/common/createRowActionsColumn';
import { LinkOffIcon, AutoGraphIcon } from '@/components/icons';
import LinkedEntitiesGrid from '@/components/common/LinkedEntitiesGrid';
import AssignEntityDrawer from '@/components/common/AssignEntityDrawer';
import LinkedEntitiesFilterDrawer, {
  type LinkedFilterSectionConfig,
  type LinkedFilterValues,
  emptyLinkedFilters,
  hasActiveLinkedFilters,
  countActiveLinkedFilters,
} from '@/components/common/LinkedEntitiesFilterDrawer';
import type { ToolbarPillTab } from '@/components/common/GridToolbar';
import { useRouter } from 'next/navigation';
import type {
  RequirementWithMetrics,
  MetricWithRelationships,
} from '@/utils/api-client/interfaces/requirement';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { MetricTuningAgreement } from '@/utils/api-client/interfaces/metric-tuning';
import type { Status } from '@/utils/api-client/interfaces/status';
import { RequirementClient } from '@/utils/api-client/requirement-client';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { isTunableMetric } from '@/utils/metric-tunable';
import type { UUID } from 'crypto';

interface TuningSummary {
  agreement: MetricTuningAgreement;
  predatesMetric: boolean;
}

/** How a metric's tuning stands, for the Tuning column. */
function TuningCell({
  metric,
  summary,
}: {
  metric: GridRowModel;
  summary: TuningSummary | null | undefined;
}) {
  if (!isTunableMetric(metric)) {
    return (
      <Typography variant="body2" color="text.secondary">
        —
      </Typography>
    );
  }
  if (summary === undefined) {
    return (
      <Typography variant="body2" color="text.secondary">
        …
      </Typography>
    );
  }
  if (summary === null || summary.agreement.judged === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        Not tuned
      </Typography>
    );
  }
  const { accepted, judged } = summary.agreement;
  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ height: 1 }}>
      <LinearProgress
        variant="determinate"
        value={(accepted / judged) * 100}
        color="success"
        aria-label={`${accepted} of ${judged} accepted`}
        sx={{ width: theme => theme.spacing(8), flexShrink: 0 }}
      />
      <Typography variant="body2" noWrap>
        {accepted} of {judged} accepted
      </Typography>
      {summary.predatesMetric && (
        <Tooltip title="The metric changed after the last tuning run.">
          <Box component="span">
            <GridBadge
              label="outdated"
              sx={{ bgcolor: 'warning.light', color: 'warning.contrastText' }}
            />
          </Box>
        </Tooltip>
      )}
    </Stack>
  );
}

export default function RequirementLinkedMetrics({
  requirement,
}: {
  requirement: RequirementWithMetrics;
}) {
  const router = useRouter();
  const notifications = useNotifications();
  const canEditRequirement = useCan(Capability.Requirement.UPDATE);
  const [metrics, setMetrics] = useState<MetricWithRelationships[]>(
    requirement.metrics ?? []
  );
  const [loading, setLoading] = useState(false);
  // undefined: still loading; null: no run or it failed to load.
  const [tuning, setTuning] = useState<Record<string, TuningSummary | null>>(
    {}
  );

  const tunableIds = useMemo(
    () =>
      metrics
        .filter(m => isTunableMetric(m))
        .map(m => String(m.id))
        .sort()
        .join(','),
    [metrics]
  );

  // One request per custom metric, all at once.
  useEffect(() => {
    if (!tunableIds) return;
    let cancelled = false;
    const ids = tunableIds.split(',');
    const client = new ApiClientFactory().getMetricTuningClient();
    void Promise.allSettled(ids.map(id => client.getTuningRun(id))).then(
      results => {
        if (cancelled) return;
        const next: Record<string, TuningSummary | null> = {};
        results.forEach((result, index) => {
          next[ids[index]] =
            result.status === 'fulfilled'
              ? {
                  agreement: result.value.agreement,
                  predatesMetric: result.value.predates_metric,
                }
              : null;
        });
        setTuning(next);
      }
    );
    return () => {
      cancelled = true;
    };
  }, [tunableIds]);

  // Assign drawer state
  const [assignOpen, setAssignOpen] = useState(false);
  const [available, setAvailable] = useState<MetricDetail[]>([]);
  const [loadingAvailable, setLoadingAvailable] = useState(false);

  // Toolbar filter state
  const [scorePill, setScorePill] = useState('all');
  const [filterOpen, setFilterOpen] = useState(false);
  const [appliedFilters, setAppliedFilters] = useState<LinkedFilterValues>({
    backend: [],
    score_type: [],
    status: [],
  });

  // Assign-drawer toolbar filter state (independent of the linked-grid filters)
  const [assignScorePill, setAssignScorePill] = useState('all');
  const [assignFilterOpen, setAssignFilterOpen] = useState(false);
  const [assignFilters, setAssignFilters] = useState<LinkedFilterValues>({
    backend: [],
    score_type: [],
    status: [],
  });

  const fetchLinked = useCallback(async () => {
    setLoading(true);
    try {
      const client = new RequirementClient();
      const result = await client.getRequirementWithMetrics(
        requirement.id as UUID
      );
      setMetrics(result.metrics ?? []);
    } catch {
      // keep existing
    } finally {
      setLoading(false);
    }
  }, [requirement.id]);

  // No mount fetch: `requirement.metrics` arrives with the server-rendered
  // requirement, so `fetchLinked` only re-reads after an assignment.

  const handleUnassign = useCallback(
    async (metricId: string) => {
      try {
        const client = new MetricsClient();
        await client.removeRequirementFromMetric(
          metricId as UUID,
          requirement.id as UUID
        );
        setMetrics(prev => prev.filter(m => String(m.id) !== metricId));
        notifications.show('Metric unassigned', {
          severity: 'success',
          autoHideDuration: 4000,
        });
      } catch (error) {
        notifications.show(
          error instanceof Error
            ? `Failed to unassign metric: ${error.message}`
            : 'Failed to unassign metric',
          { severity: 'error', autoHideDuration: 6000 }
        );
      }
    },
    [requirement.id, notifications]
  );

  // Linked metrics columns (with unassign action)
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
      {
        field: 'backend',
        headerName: 'Backend',
        width: 130,
        valueGetter: (_value: unknown, row: GridRowModel) => {
          const bt = row.backend_type as { type_value?: string } | null;
          return bt?.type_value ?? '';
        },
        renderCell: (params: GridRenderCellParams) =>
          typeof params.value === 'string' && params.value ? (
            <GridBadge size="detail" label={params.value} />
          ) : null,
      },
      {
        field: 'score_type',
        headerName: 'Score Type',
        width: 130,
        renderCell: (params: GridRenderCellParams) =>
          typeof params.value === 'string' && params.value ? (
            <GridBadge size="detail" label={params.value} />
          ) : null,
      },
      // Only custom metrics can be tuned; without one these columns are all dashes.
      ...(tunableIds
        ? [
            {
              field: 'tuning',
              headerName: 'Tuning',
              width: 260,
              sortable: false,
              renderCell: (params: GridRenderCellParams) => (
                <TuningCell
                  metric={params.row}
                  summary={tuning[String(params.row.id)]}
                />
              ),
            },
            {
              field: 'overruled',
              headerName: 'Overruled in runs',
              width: 150,
              sortable: false,
              valueGetter: (_value: unknown, row: GridRowModel) =>
                tuning[String(row.id)]?.agreement.disagreements_in_runs ?? null,
              renderCell: (params: GridRenderCellParams) => (
                <Typography
                  variant="body2"
                  color={
                    typeof params.value === 'number'
                      ? 'text.primary'
                      : 'text.secondary'
                  }
                >
                  {typeof params.value === 'number' ? params.value : '—'}
                </Typography>
              ),
            },
          ]
        : []),
      createRowActionsColumn({
        canDelete: () => canEditRequirement,
        onDelete: id => handleUnassign(id),
        deleteTooltip: 'Unassign',
        deleteIcon: LinkOffIcon,
      }),
    ],
    [handleUnassign, canEditRequirement, tuning, tunableIds]
  );

  // Assign drawer columns (name + description + badges, no action)
  const drawerColumns = useMemo<GridColDef[]>(
    () => [
      { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
      {
        field: 'description',
        headerName: 'Description',
        flex: 2,
        minWidth: 200,
      },
      {
        field: 'backend',
        headerName: 'Backend',
        width: 130,
        valueGetter: (_value: unknown, row: GridRowModel) => {
          const bt = row.backend_type as { type_value?: string } | null;
          return bt?.type_value ?? '';
        },
        renderCell: (params: GridRenderCellParams) =>
          typeof params.value === 'string' && params.value ? (
            <GridBadge size="detail" label={params.value} />
          ) : null,
      },
      {
        field: 'score_type',
        headerName: 'Score Type',
        width: 130,
        renderCell: (params: GridRenderCellParams) =>
          typeof params.value === 'string' && params.value ? (
            <GridBadge size="detail" label={params.value} />
          ) : null,
      },
    ],
    []
  );

  const linkedIds = useMemo(
    () => new Set(metrics.map(m => String(m.id))),
    [metrics]
  );

  const availableFiltered: GridRowModel[] = useMemo(
    () => available.filter(m => !linkedIds.has(String(m.id))),
    [available, linkedIds]
  );

  const handleAssignClick = useCallback(async () => {
    setLoadingAvailable(true);
    setAssignOpen(true);
    setAssignScorePill('all');
    setAssignFilters({ backend: [], score_type: [], status: [] });
    try {
      const client = new MetricsClient();
      const result = await client.getAllMetrics();
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
          client.addRequirementToMetric(id as UUID, requirement.id as UUID)
        )
      );
      await fetchLinked();
      setAssignOpen(false);
    },
    [requirement.id, fetchLinked]
  );

  // Score Type pill tabs
  const pillTabs: ToolbarPillTab[] = useMemo(
    () => [
      { label: 'All', value: 'all' },
      { label: 'Numeric', value: 'numeric' },
      { label: 'Categorical', value: 'categorical' },
    ],
    []
  );

  // Filter drawer sections: Backend, Score Type, Status (derived from rows)
  const filterSections: LinkedFilterSectionConfig[] = useMemo(() => {
    const backends = Array.from(
      new Set(
        metrics
          .map(m => m.backend_type?.type_value)
          .filter((value): value is string => !!value)
      )
    ).sort();
    const scoreTypes = Array.from(
      new Set(
        metrics
          .map(m => m.score_type)
          .filter((value): value is string => !!value)
      )
    ).sort();
    const statusNames = Array.from(
      new Set(
        metrics
          .map(m => m.status?.name)
          .filter((name): name is string => !!name)
      )
    ).sort();

    return [
      {
        key: 'backend',
        title: 'Backend',
        options: backends.map(value => ({ value, label: value })),
      },
      {
        key: 'score_type',
        title: 'Score Type',
        options: scoreTypes.map(value => ({
          value,
          label: value.charAt(0).toUpperCase() + value.slice(1),
        })),
      },
      {
        key: 'status',
        title: 'Status',
        options: statusNames.map(value => ({ value, label: value })),
      },
    ];
  }, [metrics]);

  const makeRowFilter = useCallback(
    (pill: string, filters: LinkedFilterValues) => (row: GridRowModel) => {
      const scoreType =
        typeof row.score_type === 'string' ? row.score_type : '';
      if (pill !== 'all' && scoreType !== pill) return false;

      const backends = filters.backend ?? [];
      if (backends.length > 0) {
        const bt = row.backend_type as { type_value?: string } | null;
        if (!backends.includes(bt?.type_value ?? '')) return false;
      }

      const scoreTypes = filters.score_type ?? [];
      if (scoreTypes.length > 0 && !scoreTypes.includes(scoreType))
        return false;

      const statuses = filters.status ?? [];
      if (statuses.length > 0) {
        const statusName =
          (row.status as Status | null | undefined)?.name ?? '';
        if (!statuses.includes(statusName)) return false;
      }

      return true;
    },
    []
  );

  const rowFilter = useMemo(
    () => makeRowFilter(scorePill, appliedFilters),
    [makeRowFilter, scorePill, appliedFilters]
  );

  const assignRowFilter = useMemo(
    () => makeRowFilter(assignScorePill, assignFilters),
    [makeRowFilter, assignScorePill, assignFilters]
  );

  // Assign-drawer filter sections derived from the available (unlinked) metrics
  const assignFilterSections: LinkedFilterSectionConfig[] = useMemo(() => {
    const backends = Array.from(
      new Set(
        availableFiltered
          .map(
            m => (m.backend_type as { type_value?: string } | null)?.type_value
          )
          .filter((value): value is string => !!value)
      )
    ).sort();
    const scoreTypes = Array.from(
      new Set(
        availableFiltered
          .map(m => (typeof m.score_type === 'string' ? m.score_type : ''))
          .filter((value): value is string => !!value)
      )
    ).sort();
    const statusNames = Array.from(
      new Set(
        availableFiltered
          .map(m => (m.status as Status | null | undefined)?.name)
          .filter((name): name is string => !!name)
      )
    ).sort();

    return [
      {
        key: 'backend',
        title: 'Backend',
        options: backends.map(value => ({ value, label: value })),
      },
      {
        key: 'score_type',
        title: 'Score Type',
        options: scoreTypes.map(value => ({
          value,
          label: value.charAt(0).toUpperCase() + value.slice(1),
        })),
      },
      {
        key: 'status',
        title: 'Status',
        options: statusNames.map(value => ({ value, label: value })),
      },
    ];
  }, [availableFiltered]);

  return (
    <>
      <LinkedEntitiesGrid
        title="Linked Metrics"
        rows={metrics as GridRowModel[]}
        columns={linkedColumns}
        loading={loading}
        getRowId={row => String(row.id)}
        onRowClick={params => router.push(`/metrics/${String(params.id)}`)}
        onAssignClick={canEditRequirement ? handleAssignClick : undefined}
        searchPlaceholder="Search metrics…"
        rowFilter={rowFilter}
        onFilterClick={() => setFilterOpen(true)}
        hasActiveFilters={hasActiveLinkedFilters(appliedFilters)}
        activeFilterCount={countActiveLinkedFilters(appliedFilters)}
        pillTabs={pillTabs}
        activePill={scorePill}
        onPillChange={setScorePill}
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
            <AutoGraphIcon sx={{ fontSize: 32, color: 'primary.main' }} />
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              No metrics assigned yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              No metrics have been assigned to this requirement yet. Click
              Assign to link a metric and start measuring this requirement.
            </Typography>
          </Box>
        }
      />

      <AssignEntityDrawer
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        title="Assign Metric"
        rows={availableFiltered}
        columns={drawerColumns}
        loading={loadingAvailable}
        getRowId={row => String(row.id)}
        onAssign={handleAssign}
        searchPlaceholder="Search metrics…"
        rowFilter={assignRowFilter}
        pillTabs={pillTabs}
        activePill={assignScorePill}
        onPillChange={setAssignScorePill}
        onFilterClick={() => setAssignFilterOpen(true)}
        hasActiveFilters={hasActiveLinkedFilters(assignFilters)}
        activeFilterCount={countActiveLinkedFilters(assignFilters)}
        onCreateNew={() => router.push('/metrics/new')}
        createNewLabel="Create new metric"
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
