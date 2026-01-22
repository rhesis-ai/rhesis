'use client';

import React, { useState, useEffect } from 'react';
import { Box } from '@mui/material';
import BaseTag from '@/components/common/BaseTag';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { Source } from '@/utils/api-client/interfaces/source';

interface SourceTagsProps {
  sessionToken: string;
  source: Source;
  disableEdition?: boolean;
  onUpdate?: (updatedSource: Source) => void;
}

export default function SourceTags({
  sessionToken,
  source,
  disableEdition = false,
  onUpdate,
}: SourceTagsProps) {
  const [tagNames, setTagNames] = useState<string[]>([]);

  // Initialize and update tag names when source changes
  useEffect(() => {
    if (source.tags) {
      setTagNames(source.tags.map(tag => tag.name));
    }
  }, [source.tags]);

  const handleTagsChange = (newTagNames: string[]) => {
    setTagNames(newTagNames);
    if (onUpdate) {
      onUpdate({
        ...source,
        // create dummy tag objects with just names (imp for ui display). actual values will be set server-side
        tags: newTagNames.map(name => ({
          id:
            source.tags?.find(t => t.name === name)?.id ||
            (Date.now().toString() as any),
          name,
          created_at: Date.now().toString(),
          updated_at: Date.now().toString(),
        })),
      });
    }
  };

  return (
    <Box sx={{ width: '100%' }}>
      <BaseTag
        value={tagNames}
        onChange={handleTagsChange}
        placeholder="Add tags..."
        chipColor="primary"
        disableEdition={disableEdition}
        sessionToken={sessionToken}
        entityType={EntityType.SOURCE}
        entity={source}
      />
    </Box>
  );
}
