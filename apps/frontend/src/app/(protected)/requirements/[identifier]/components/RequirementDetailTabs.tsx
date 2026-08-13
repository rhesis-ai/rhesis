'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, Stack, Typography } from '@mui/material';
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
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import GeneralInfoCard from '@/components/common/GeneralInfoCard';
import ViewField from '@/components/common/ViewField';
import EditableSectionCard from '@/components/common/EditableSection';
import TagsField from '@/components/common/TagsField';
import { useRouter } from 'next/navigation';
import type {
  RequirementWithMetrics,
  MetricWithRelationships,
} from '@/utils/api-client/interfaces/requirement';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { Status } from '@/utils/api-client/interfaces/status';
import { EntityType, type Tag } from '@/utils/api-client/interfaces/tag';
import { RequirementClient } from '@/utils/api-client/requirement-client';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import { TagsClient } from '@/utils/api-client/tags-client';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import RequirementDrawer from '../../components/RequirementDrawer';
import RequirementLinkedTests from './RequirementLinkedTests';
import type { UUID } from 'crypto';

const TAB_KEYS = ['basic', 'linked-metrics', 'linked-tests'] as const;

const NAV_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  basic: 'Basic Information',
  'linked-metrics': 'Linked Metrics',
  'linked-tests': 'Linked Tests',
};

interface RequirementDetailTabsProps {
  requirement: RequirementWithMetrics;
  onUpdated: (updated: RequirementWithMetrics) => void;
}

export default function RequirementDetailTabs({
  requirement,
  onUpdated,
}: RequirementDetailTabsProps) {
  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label: NAV_LABELS[key],
    id: `requirement-detail-tab-${index}`,
    'aria-controls': `requirement-detail-tabpanel-${index}`,
  }));

  return (
    <Box>
      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={handleTabChange}
        aria-label="Requirement detail tabs"
      />

      <DetailTabPanel value={activeTab} index={0} prefix="requirement-detail">
        <RequirementBasicInfo requirement={requirement} onUpdated={onUpdated} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={1} prefix="requirement-detail">
        <RequirementLinkedMetrics requirement={requirement} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={2} prefix="requirement-detail">
        <RequirementLinkedTests requirement={requirement} />
      </DetailTabPanel>
    </Box>
  );
}

function RequirementBasicInfo({
  requirement,
  onUpdated,
}: {
  requirement: RequirementWithMetrics;
  onUpdated: (updated: RequirementWithMetrics) => void;
}) {
  const [editOpen, setEditOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | undefined>();
  const canEditRequirement = useCan(Capability.Requirement.UPDATE);

  const tags = requirement.tags ?? [];

  const handleSave = async (
    name: string,
    description: string,
    tagNames: string[]
  ) => {
    try {
      setSaving(true);
      setSaveError(undefined);

      const client = new RequirementClient();
      await client.updateRequirement(requirement.id as UUID, {
        name: name.trim(),
        description: description.trim() || null,
      });

      const tagsClient = new TagsClient();
      const normalizeTag = (s: string) => s.trim().toLowerCase();
      const initialTagMap = new Map(tags.map(t => [normalizeTag(t.name), t]));
      const nextNorm = new Set(
        tagNames.map(normalizeTag).filter(s => s.length > 0)
      );

      const toRemove = tags.filter(t => !nextNorm.has(normalizeTag(t.name)));
      const toAdd = tagNames
        .map(n => n.trim())
        .filter(n => n.length > 0 && !initialTagMap.has(normalizeTag(n)));

      await Promise.all(
        toRemove.map(tag =>
          tagsClient.removeTagFromEntity(
            EntityType.REQUIREMENT,
            requirement.id as UUID,
            tag.id as UUID
          )
        )
      );
      await Promise.all(
        toAdd.map(tagName =>
          tagsClient.assignTagToEntity(
            EntityType.REQUIREMENT,
            requirement.id as UUID,
            {
              name: tagName,
              organization_id: requirement.organization_id,
              ...(requirement.user_id ? { user_id: requirement.user_id } : {}),
            }
          )
        )
      );

      const updated = await client.getRequirementWithMetrics(requirement.id as UUID);
      onUpdated(updated);
      setEditOpen(false);
    } catch {
      setSaveError('Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleTagsSave = async (draft: { tagNames: string[] }) => {
    const tagsClient = new TagsClient();
    const normalizeTag = (s: string) => s.trim().toLowerCase();
    const initialTagMap = new Map(tags.map(t => [normalizeTag(t.name), t]));
    const nextNorm = new Set(
      draft.tagNames.map(normalizeTag).filter(s => s.length > 0)
    );

    const toRemove = tags.filter(t => !nextNorm.has(normalizeTag(t.name)));
    const toAdd = draft.tagNames
      .map(n => n.trim())
      .filter(n => n.length > 0 && !initialTagMap.has(normalizeTag(n)));

    await Promise.all(
      toRemove.map(tag =>
        tagsClient.removeTagFromEntity(
          EntityType.REQUIREMENT,
          requirement.id as UUID,
          tag.id as UUID
        )
      )
    );
    await Promise.all(
      toAdd.map(tagName =>
        tagsClient.assignTagToEntity(EntityType.REQUIREMENT, requirement.id as UUID, {
          name: tagName,
          organization_id: requirement.organization_id,
          ...(requirement.user_id ? { user_id: requirement.user_id } : {}),
        })
      )
    );

    const client = new RequirementClient();
    const updated = await client.getRequirementWithMetrics(requirement.id as UUID);
    onUpdated(updated);
  };

  return (
    <>
      <Stack spacing={3}>
        <GeneralInfoCard
          onEdit={canEditRequirement ? () => setEditOpen(true) : undefined}
        >
          <Stack spacing={3}>
            <ViewField label="Name" value={requirement.name} />

            <ViewField
              label="Description"
              value={requirement.description || undefined}
              multiline
            />
          </Stack>
        </GeneralInfoCard>

        <EditableSectionCard
          editable={canEditRequirement}
          title="Tags"
          initialValue={{ tagNames: tags.map((t: Tag) => t.name) }}
          onSave={handleTagsSave}
          isDirty={(draft, initial) =>
            JSON.stringify(draft.tagNames.slice().sort()) !==
            JSON.stringify(initial.tagNames.slice().sort())
          }
        >
          {({ draft, setDraft, isEditing: isTagsEditing }) => (
            <TagsField
              tagNames={draft.tagNames}
              isEditing={isTagsEditing}
              onChange={names => setDraft(d => ({ ...d, tagNames: names }))}
              helperText="These tags help categorize and find this requirement"
              emptyLabel="No tags"
            />
          )}
        </EditableSectionCard>
      </Stack>

      <RequirementDrawer
        open={editOpen}
        onClose={() => setEditOpen(false)}
        name={requirement.name}
        description={requirement.description ?? ''}
        initialTagNames={tags.map((t: Tag) => t.name)}
        tagSuggestions={tags.map((t: Tag) => t.name)}
        onSave={handleSave}
        isNew={false}
        loading={saving}
        error={saveError}
      />
    </>
  );
}

function RequirementLinkedMetrics({
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
      const result = await client.getRequirementWithMetrics(requirement.id as UUID);
      setMetrics(result.metrics ?? []);
    } catch {
      // keep existing
    } finally {
      setLoading(false);
    }
  }, [requirement.id]);

  useEffect(() => {
    fetchLinked();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on mount / id change
  }, [requirement.id]);

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
      createRowActionsColumn({
        canDelete: () => canEditRequirement,
        onDelete: id => handleUnassign(id),
        deleteTooltip: 'Unassign',
        deleteIcon: LinkOffIcon,
      }),
    ],
    [handleUnassign, canEditRequirement]
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
              No metrics have been assigned to this requirement yet. Click Assign
              to link a metric and start measuring this requirement.
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
