'use client';

import * as React from 'react';
import EditableSection from '@/components/common/EditableSection';
import TagsField from '@/components/common/TagsField';
import { Project } from '@/utils/api-client/interfaces/project';

interface TagsDraft {
  tagNames: string[];
}

interface ProjectTagsCardProps {
  project: Project;
  onSave: (updatedProject: Partial<Project>) => Promise<boolean>;
}

export default function ProjectTagsCard({
  project,
  onSave,
}: ProjectTagsCardProps) {
  const initialTagNames = project.tags ?? [];
  const initialDraft: TagsDraft = { tagNames: initialTagNames };

  const handleSave = async (draft: TagsDraft) => {
    await onSave({ tags: draft.tagNames });
  };

  return (
    <EditableSection
      title="Tags"
      initialValue={initialDraft}
      onSave={handleSave}
      isDirty={(draft, initial) =>
        JSON.stringify([...draft.tagNames].sort()) !==
        JSON.stringify([...initial.tagNames].sort())
      }
    >
      {({ draft, setDraft, isEditing }) => (
        <TagsField
          tagNames={draft.tagNames}
          isEditing={isEditing}
          onChange={tagNames => setDraft(d => ({ ...d, tagNames }))}
          helperText="Tags help categorize and find this project"
        />
      )}
    </EditableSection>
  );
}
