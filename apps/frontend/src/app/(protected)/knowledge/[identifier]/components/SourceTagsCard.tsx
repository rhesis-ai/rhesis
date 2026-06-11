'use client';

import * as React from 'react';
import EditableSection from '@/components/common/EditableSection';
import TagsField from '@/components/common/TagsField';
import { Source } from '@/utils/api-client/interfaces/source';
import { useNotifications } from '@/components/common/NotificationContext';
import { EntityType, Tag } from '@/utils/api-client/interfaces/tag';
import { TagsClient } from '@/utils/api-client/tags-client';
import { UUID } from 'crypto';

interface TagsDraft {
  tagNames: string[];
}

interface SourceTagsCardProps {
  sessionToken: string;
  source: Source;
  onUpdate?: () => void;
}

export default function SourceTagsCard({
  sessionToken,
  source,
  onUpdate,
}: SourceTagsCardProps) {
  const notifications = useNotifications();

  const initialTagNames = (source.tags ?? []).map((t: Tag) => t.name);
  const initialDraft: TagsDraft = { tagNames: initialTagNames };

  const handleSave = async (draft: TagsDraft) => {
    const tagsClient = new TagsClient(sessionToken);
    const currentNames = initialTagNames;
    const newNames = draft.tagNames;

    const tagsToRemove = currentNames.filter(n => !newNames.includes(n));
    const tagsToAdd = newNames.filter(n => !currentNames.includes(n));

    for (const name of tagsToRemove) {
      const tag = source.tags?.find((t: Tag) => t.name === name);
      if (tag) {
        await tagsClient.removeTagFromEntity(
          EntityType.SOURCE,
          source.id as UUID,
          tag.id
        );
      }
    }

    for (const name of tagsToAdd) {
      await tagsClient.assignTagToEntity(EntityType.SOURCE, source.id as UUID, {
        name,
        organization_id: source.organization_id,
        user_id: source.user_id,
      });
    }

    notifications.show('Tags updated', {
      severity: 'success',
      autoHideDuration: 4000,
    });
    await onUpdate?.();
  };

  return (
    <EditableSection
      title="Tags"
      initialValue={initialDraft}
      onSave={handleSave}
      isDirty={(draft, initial) =>
        JSON.stringify(draft.tagNames.slice().sort()) !==
        JSON.stringify(initial.tagNames.slice().sort())
      }
    >
      {({ draft, setDraft, isEditing }) => (
        <TagsField
          tagNames={draft.tagNames}
          isEditing={isEditing}
          onChange={tagNames => setDraft(d => ({ ...d, tagNames }))}
          helperText="These tags help categorize and find this source"
          emptyLabel="No tags"
        />
      )}
    </EditableSection>
  );
}
