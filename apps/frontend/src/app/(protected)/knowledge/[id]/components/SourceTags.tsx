'use client';

import React, { useState, useEffect } from 'react';
import { Box } from '@mui/material';
import BaseTag from '@/components/common/BaseTag';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { Source } from '@/utils/api-client/interfaces/source';

interface SourceTagsProps {
  sessionToken: string;
  source: Source;
}

export default function SourceTags({ sessionToken, source }: SourceTagsProps) {
  const [tagNames, setTagNames] = useState<string[]>([]);

  // Initialize and update tag names when source changes
  useEffect(() => {
    if (source.tags) {
      setTagNames(source.tags.map(tag => tag.name));
    }
  }, [source.tags]);

  return (
    <Box sx={{ width: '100%' }}>
      <BaseTag
        value={tagNames}
        onChange={setTagNames}
        label="Tags"
        placeholder="Add tags (press Enter or comma to add)"
        helperText="These tags help categorize and find this source"
        chipColor="primary"
        addOnBlur
        delimiters={[',', 'Enter']}
        size="small"
        margin="normal"
        fullWidth
        sessionToken={sessionToken}
        entityType={EntityType.SOURCE}
        entity={source}
      />
    </Box>
  );
}
