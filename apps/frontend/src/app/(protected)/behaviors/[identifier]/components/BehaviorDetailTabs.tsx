'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, Chip, Stack, Typography } from '@mui/material';
import {
  GridColDef,
  GridRenderCellParams,
  GridRowModel,
} from '@mui/x-data-grid';
import GridBadge from '@/components/common/GridBadge';
import { createRowActionsColumn } from '@/components/common/createRowActionsColumn';
import LinkedEntitiesGrid from '@/components/common/LinkedEntitiesGrid';
import AssignEntityDrawer from '@/components/common/AssignEntityDrawer';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import GeneralInfoCard from '@/components/common/GeneralInfoCard';
import ViewField from '@/components/common/ViewField';
import EditableSectionCard from '@/components/common/EditableSection';
import TagsField from '@/components/common/TagsField';
import { AutoGraphIcon } from '@/components/icons';
import { useRouter } from 'next/navigation';
import type {
  BehaviorWithMetrics,
  MetricWithRelationships,
} from '@/utils/api-client/interfaces/behavior';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import { EntityType, type Tag } from '@/utils/api-client/interfaces/tag';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import { TagsClient } from '@/utils/api-client/tags-client';
import BehaviorDrawer from '../../components/BehaviorDrawer';
import type { UUID } from 'crypto';

const TAB_KEYS = ['basic', 'linked-metrics'] as const;

const NAV_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  basic: 'Basic Information',
  'linked-metrics': 'Linked Metrics',
};

interface BehaviorDetailTabsProps {
  behavior: BehaviorWithMetrics;
  sessionToken: string;
}

export default function BehaviorDetailTabs({
  behavior: initialBehavior,
  sessionToken,
}: BehaviorDetailTabsProps) {
  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);
  const [behavior, setBehavior] =
    useState<BehaviorWithMetrics>(initialBehavior);

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label: NAV_LABELS[key],
    id: `behavior-detail-tab-${index}`,
    'aria-controls': `behavior-detail-tabpanel-${index}`,
  }));

  return (
    <Box>
      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={handleTabChange}
        aria-label="Behavior detail tabs"
      />

      <DetailTabPanel value={activeTab} index={0} prefix="behavior-detail">
        <BehaviorBasicInfo
          behavior={behavior}
          sessionToken={sessionToken}
          onUpdated={setBehavior}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={1} prefix="behavior-detail">
        <BehaviorLinkedMetrics
          behavior={behavior}
          sessionToken={sessionToken}
        />
      </DetailTabPanel>
    </Box>
  );
}

function BehaviorBasicInfo({
  behavior,
  sessionToken,
  onUpdated,
}: {
  behavior: BehaviorWithMetrics;
  sessionToken: string;
  onUpdated: (updated: BehaviorWithMetrics) => void;
}) {
  const [editOpen, setEditOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | undefined>();

  const tags = behavior.tags ?? [];

  const handleSave = async (
    name: string,
    description: string,
    tagNames: string[]
  ) => {
    try {
      setSaving(true);
      setSaveError(undefined);

      const client = new BehaviorClient(sessionToken);
      await client.updateBehavior(behavior.id as UUID, {
        name: name.trim(),
        description: description.trim() || null,
      });

      const tagsClient = new TagsClient(sessionToken);
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
            EntityType.BEHAVIOR,
            behavior.id as UUID,
            tag.id as UUID
          )
        )
      );
      await Promise.all(
        toAdd.map(tagName =>
          tagsClient.assignTagToEntity(
            EntityType.BEHAVIOR,
            behavior.id as UUID,
            {
              name: tagName,
              organization_id: behavior.organization_id,
              ...(behavior.user_id ? { user_id: behavior.user_id } : {}),
            }
          )
        )
      );

      const updated = await client.getBehaviorWithMetrics(behavior.id as UUID);
      onUpdated(updated);
      setEditOpen(false);
    } catch {
      setSaveError('Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleTagsSave = async (draft: { tagNames: string[] }) => {
    const tagsClient = new TagsClient(sessionToken);
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
          EntityType.BEHAVIOR,
          behavior.id as UUID,
          tag.id as UUID
        )
      )
    );
    await Promise.all(
      toAdd.map(tagName =>
        tagsClient.assignTagToEntity(EntityType.BEHAVIOR, behavior.id as UUID, {
          name: tagName,
          organization_id: behavior.organization_id,
          ...(behavior.user_id ? { user_id: behavior.user_id } : {}),
        })
      )
    );

    const client = new BehaviorClient(sessionToken);
    const updated = await client.getBehaviorWithMetrics(behavior.id as UUID);
    onUpdated(updated);
  };

  return (
    <>
      <Stack spacing={3}>
        <GeneralInfoCard onEdit={() => setEditOpen(true)}>
          <Stack spacing={3}>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
                gap: 3,
              }}
            >
              <ViewField label="Name" value={behavior.name} />
              {behavior.status?.name && (
                <ViewField label="Status">
                  <Chip
                    label={behavior.status.name}
                    size="small"
                    variant="outlined"
                    sx={{ mt: 0.5 }}
                  />
                </ViewField>
              )}
            </Box>

            <ViewField
              label="Description"
              value={behavior.description || undefined}
              multiline
            />
          </Stack>
        </GeneralInfoCard>

        <EditableSectionCard
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
              helperText="These tags help categorize and find this behavior"
              emptyLabel="No tags"
            />
          )}
        </EditableSectionCard>
      </Stack>

      <BehaviorDrawer
        open={editOpen}
        onClose={() => setEditOpen(false)}
        name={behavior.name}
        description={behavior.description ?? ''}
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

function BehaviorLinkedMetrics({
  behavior,
  sessionToken,
}: {
  behavior: BehaviorWithMetrics;
  sessionToken: string;
}) {
  const router = useRouter();
  const [metrics, setMetrics] = useState<MetricWithRelationships[]>(
    behavior.metrics ?? []
  );
  const [loading, setLoading] = useState(false);

  // Assign drawer state
  const [assignOpen, setAssignOpen] = useState(false);
  const [available, setAvailable] = useState<MetricDetail[]>([]);
  const [loadingAvailable, setLoadingAvailable] = useState(false);

  const fetchLinked = useCallback(async () => {
    setLoading(true);
    try {
      const client = new BehaviorClient(sessionToken);
      const result = await client.getBehaviorWithMetrics(behavior.id as UUID);
      setMetrics(result.metrics ?? []);
    } catch {
      // keep existing
    } finally {
      setLoading(false);
    }
  }, [behavior.id, sessionToken]);

  useEffect(() => {
    fetchLinked();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on mount / id change
  }, [behavior.id, sessionToken]);

  const handleUnassign = useCallback(
    async (metricId: string) => {
      try {
        const client = new MetricsClient(sessionToken);
        await client.removeBehaviorFromMetric(
          metricId as UUID,
          behavior.id as UUID
        );
        setMetrics(prev => prev.filter(m => m.id !== metricId));
      } catch {
        // ignore
      }
    },
    [behavior.id, sessionToken]
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
        onDelete: id => handleUnassign(id),
        deleteTooltip: 'Unassign',
      }),
    ],
    [handleUnassign]
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
    try {
      const client = new MetricsClient(sessionToken);
      const result = await client.getAllMetrics();
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
          client.addBehaviorToMetric(id as UUID, behavior.id as UUID)
        )
      );
      await fetchLinked();
      setAssignOpen(false);
    },
    [behavior.id, sessionToken, fetchLinked]
  );

  return (
    <>
      <LinkedEntitiesGrid
        title="Linked Metrics"
        rows={metrics as GridRowModel[]}
        columns={linkedColumns}
        loading={loading}
        getRowId={row => String(row.id)}
        onRowClick={params => router.push(`/metrics/${String(params.id)}`)}
        onAssignClick={handleAssignClick}
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
              No metrics have been assigned to this behavior yet. Click Assign
              to link a metric and start measuring this behavior.
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
      />
    </>
  );
}
