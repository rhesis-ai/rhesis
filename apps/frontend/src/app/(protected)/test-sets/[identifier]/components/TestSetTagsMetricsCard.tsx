'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import EditableSection from '@/components/common/EditableSection';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import TagsField from '@/components/common/TagsField';
import TestSetMetrics from './TestSetMetrics';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { useNotifications } from '@/components/common/NotificationContext';
import { EntityType, Tag } from '@/utils/api-client/interfaces/tag';
import { TagsClient } from '@/utils/api-client/tags-client';
import type { UUID } from 'crypto';

interface TagsDraft {
  tagNames: string[];
}

interface TestSetTagsMetricsCardProps {
  sessionToken: string;
  testSet: TestSet;
  onUpdate?: () => void;
}

export default function TestSetTagsMetricsCard({
  sessionToken,
  testSet,
  onUpdate: _onUpdate,
}: TestSetTagsMetricsCardProps) {
  const notifications = useNotifications();
  const canEditTestSet = useCan(Capability.TestSet.UPDATE);

  const initialTagNames = (testSet.tags ?? []).map((t: Tag) => t.name);
  const initialDraft: TagsDraft = { tagNames: initialTagNames };

  const handleSave = async (draft: TagsDraft) => {
    const tagsClient = new TagsClient(sessionToken);
    const currentNames = initialTagNames;
    const newNames = draft.tagNames;

    const toRemove = currentNames.filter(n => !newNames.includes(n));
    const toAdd = newNames.filter(n => !currentNames.includes(n));

    for (const name of toRemove) {
      const tag = testSet.tags?.find((t: Tag) => t.name === name);
      if (tag) {
        await tagsClient.removeTagFromEntity(
          EntityType.TEST_SET,
          testSet.id as UUID,
          tag.id
        );
      }
    }

    for (const name of toAdd) {
      await tagsClient.assignTagToEntity(
        EntityType.TEST_SET,
        testSet.id as UUID,
        {
          name,
          organization_id: testSet.organization_id,
          user_id: testSet.user_id,
        }
      );
    }

    notifications.show('Tags updated', {
      severity: 'success',
      autoHideDuration: 4000,
    });
  };

  return (
    <EditableSection
      editable={canEditTestSet}
      title="Metrics & tags"
      initialValue={initialDraft}
      onSave={handleSave}
      isDirty={(draft, initial) =>
        JSON.stringify(draft.tagNames.slice().sort()) !==
        JSON.stringify(initial.tagNames.slice().sort())
      }
    >
      {({ draft, setDraft, isEditing }) => (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Metrics — auto-managed, not part of the Edit/Save cycle */}
          <Box>
            <Typography
              sx={{
                fontSize: 18,
                fontWeight: 700,
                lineHeight: '25px',
                color: 'text.primary',
                mb: '2px',
              }}
            >
              Metrics
            </Typography>
            <Typography
              sx={{
                fontSize: 12,
                lineHeight: '18px',
                color: 'text.secondary',
                display: 'block',
                mb: 2,
              }}
            >
              Evaluation metrics linked to this test set
            </Typography>
            <TestSetMetrics
              testSetId={testSet.id as string}
              sessionToken={sessionToken}
            />
          </Box>

          {/* Tags */}
          <TagsField
            tagNames={draft.tagNames}
            isEditing={isEditing}
            onChange={tagNames => setDraft(d => ({ ...d, tagNames }))}
            helperText="These tags help categorize and find this test set"
            emptyLabel="No tags"
          />
        </Box>
      )}
    </EditableSection>
  );
}
