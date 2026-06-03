'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, Chip, Stack, Paper, Typography } from '@mui/material';
import { GridColDef } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import GridBadge from '@/components/common/GridBadge';
import {
  createRowActionsColumn,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';
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

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        setLoading(true);
        const client = new BehaviorClient(sessionToken);
        const result = await client.getBehaviorWithMetrics(behavior.id as UUID);
        setMetrics(result.metrics ?? []);
      } catch {
        // keep existing
      } finally {
        setLoading(false);
      }
    };
    fetchMetrics();
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

  const columns: GridColDef<MetricWithRelationships>[] = useMemo(
    () => [
      { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
      {
        field: 'description',
        headerName: 'Description',
        flex: 2,
        minWidth: 200,
        renderCell: params => (
          <Box
            title={params.value ?? ''}
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {params.value || '—'}
          </Box>
        ),
      },
      {
        field: 'backend',
        headerName: 'Backend',
        width: 130,
        valueGetter: (_value, row) => row.backend_type?.type_value ?? '',
        renderCell: params =>
          params.value ? (
            <GridBadge size="detail" label={params.value} />
          ) : null,
      },
      {
        field: 'score_type',
        headerName: 'Score Type',
        width: 130,
        renderCell: params =>
          params.value ? (
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

  const isEmpty = !loading && metrics.length === 0;

  return (
    <>
      {isEmpty ? (
        <Paper elevation={1} sx={{ p: 3 }}>
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
              No metrics have been assigned to this behavior yet. Navigate to
              Metrics to assign a metric to start measuring this behavior.
            </Typography>
          </Box>
        </Paper>
      ) : (
        <Paper elevation={1} sx={{ p: 3 }}>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: 2,
            }}
          >
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              Linked Metrics ({metrics.length})
            </Typography>
          </Box>
          <BaseDataGrid
            rows={metrics}
            columns={columns}
            loading={loading}
            getRowId={row => row.id}
            onRowClick={params => router.push(`/metrics/${String(params.id)}`)}
            pageSizeOptions={[5, 10, 25]}
            disableRowSelectionOnClick
            disablePaperWrapper={true}
            sx={rowActionsHoverSx}
          />
        </Paper>
      )}
    </>
  );
}
