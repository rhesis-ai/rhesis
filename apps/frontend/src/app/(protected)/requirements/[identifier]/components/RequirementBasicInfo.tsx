'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { Box, Link as MuiLink, Stack } from '@mui/material';
import GeneralInfoCard from '@/components/common/GeneralInfoCard';
import ViewField from '@/components/common/ViewField';
import EditableSectionCard from '@/components/common/EditableSection';
import TagsField from '@/components/common/TagsField';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';
import { EntityType, type Tag } from '@/utils/api-client/interfaces/tag';
import { RequirementClient } from '@/utils/api-client/requirement-client';
import { TagsClient } from '@/utils/api-client/tags-client';
import type { UUID } from 'crypto';
import RequirementDrawer, {
  type RequirementDetailsInput,
} from '../../components/RequirementDrawer';
import RequirementSourcesCard from './RequirementSourcesCard';
import { useRequirementActions } from './useRequirementActions';

interface RequirementBasicInfoProps {
  requirement: RequirementWithMetrics;
  onUpdated: (updated: RequirementWithMetrics) => void;
}

const normalizeTag = (s: string) => s.trim().toLowerCase();

export default function RequirementBasicInfo({
  requirement,
  onUpdated,
}: RequirementBasicInfoProps) {
  const canEdit = useCan(Capability.Requirement.UPDATE);
  const [editOpen, setEditOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | undefined>();

  const requirementId = requirement.id as UUID;
  const { refresh } = useRequirementActions(requirementId, onUpdated);
  const tags = useMemo(() => requirement.tags ?? [], [requirement.tags]);
  const tagNames = useMemo(() => tags.map((t: Tag) => t.name), [tags]);

  const syncTags = async (nextNames: string[]) => {
    const tagsClient = new TagsClient();
    const initialTagMap = new Map(tags.map(t => [normalizeTag(t.name), t]));
    const nextNorm = new Set(
      nextNames.map(normalizeTag).filter(s => s.length > 0)
    );
    const toRemove = tags.filter(t => !nextNorm.has(normalizeTag(t.name)));
    const toAdd = nextNames
      .map(n => n.trim())
      .filter(n => n.length > 0 && !initialTagMap.has(normalizeTag(n)));

    await Promise.all(
      toRemove.map(tag =>
        tagsClient.removeTagFromEntity(
          EntityType.REQUIREMENT,
          requirementId,
          tag.id as UUID
        )
      )
    );
    await Promise.all(
      toAdd.map(tagName =>
        tagsClient.assignTagToEntity(EntityType.REQUIREMENT, requirementId, {
          name: tagName,
          organization_id: requirement.organization_id,
          ...(requirement.user_id ? { user_id: requirement.user_id } : {}),
        })
      )
    );
  };

  const handleSave = async (
    name: string,
    description: string,
    nextTagNames: string[],
    details: RequirementDetailsInput
  ) => {
    try {
      setSaving(true);
      setSaveError(undefined);
      await new RequirementClient().updateRequirement(requirementId, {
        name: name.trim(),
        description: description.trim() || null,
        ...details,
      });
      await syncTags(nextTagNames);
      await refresh();
      setEditOpen(false);
    } catch {
      setSaveError('Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const parentOption = requirement.parent
    ? { id: requirement.parent.id, name: requirement.parent.name }
    : null;

  return (
    <>
      <Box>
        {/* Section cards below carry their own bottom margin; this gives
            General Information the same, so every gap matches. */}
        <Box sx={{ mb: 3 }}>
          <GeneralInfoCard
            onEdit={canEdit ? () => setEditOpen(true) : undefined}
          >
            <Stack spacing={3}>
              <ViewField label="Name" value={requirement.name} />
              <ViewField
                label="Description"
                value={requirement.description || undefined}
                multiline
              />
              <ViewField
                label="Impact"
                value={requirement.impact?.type_value}
              />
              {requirement.parent ? (
                <ViewField label="Parent requirement">
                  <MuiLink
                    component={Link}
                    href={`/requirements/${requirement.parent.id}`}
                    underline="hover"
                  >
                    {requirement.parent.name}
                  </MuiLink>
                </ViewField>
              ) : (
                <ViewField label="Parent requirement" />
              )}
            </Stack>
          </GeneralInfoCard>
        </Box>

        <RequirementSourcesCard
          requirement={requirement}
          editable={canEdit}
          onChanged={refresh}
        />

        <EditableSectionCard
          editable={canEdit}
          title="Tags"
          initialValue={{ tagNames }}
          onSave={async draft => {
            await syncTags(draft.tagNames);
            await refresh();
          }}
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
      </Box>

      <RequirementDrawer
        open={editOpen}
        onClose={() => setEditOpen(false)}
        name={requirement.name}
        description={requirement.description ?? ''}
        initialTagNames={tagNames}
        tagSuggestions={tagNames}
        initialImpactId={
          requirement.impact_id ?? requirement.impact?.id ?? null
        }
        initialParent={parentOption}
        selfId={requirementId}
        hasChildren={(requirement.children_count ?? 0) > 0}
        onSave={handleSave}
        isNew={false}
        loading={saving}
        error={saveError}
      />
    </>
  );
}
