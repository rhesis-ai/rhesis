'use client';

import * as React from 'react';
import EditableSection from '@/components/common/EditableSection';
import TagsField from '@/components/common/TagsField';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { useNotifications } from '@/components/common/NotificationContext';
import { EntityType, Tag } from '@/utils/api-client/interfaces/tag';
import { TagsClient } from '@/utils/api-client/tags-client';
import { UUID } from 'crypto';

interface TagsDraft {
  tagNames: string[];
}

interface TestFormElementsCardProps {
  sessionToken: string;
  test: TestDetail;
  onUpdate?: () => void;
}

export default function TestFormElementsCard({
  sessionToken,
  test,
  onUpdate: _onUpdate,
}: TestFormElementsCardProps) {
  const notifications = useNotifications();

  const initialTagNames = (test.tags ?? []).map((t: Tag) => t.name);

  const initialDraft: TagsDraft = { tagNames: initialTagNames };

  const handleSave = async (draft: TagsDraft) => {
    const tagsClient = new TagsClient(sessionToken);
    const currentNames = initialTagNames;
    const newNames = draft.tagNames;

    const tagsToRemove = currentNames.filter(n => !newNames.includes(n));
    const tagsToAdd = newNames.filter(n => !currentNames.includes(n));

    for (const name of tagsToRemove) {
      const tag = test.tags?.find((t: Tag) => t.name === name);
      if (tag) {
        await tagsClient.removeTagFromEntity(
          EntityType.TEST,
          test.id as UUID,
          tag.id
        );
      }
    }

    for (const name of tagsToAdd) {
      await tagsClient.assignTagToEntity(EntityType.TEST, test.id as UUID, {
        name,
        organization_id: test.organization_id,
        user_id: test.user_id,
      });
    }

    notifications.show('Tags updated', {
      severity: 'success',
      autoHideDuration: 4000,
    });
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
          helperText="These tags help categorize and find this test"
        />
      )}
    </EditableSection>
  );
}
