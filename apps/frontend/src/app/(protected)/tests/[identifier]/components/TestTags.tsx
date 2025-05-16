'use client';

import React, { useState, useEffect } from 'react';
import { Box } from '@mui/material';
import BaseTag from '@/components/common/BaseTag';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { TestDetail } from '@/utils/api-client/interfaces/tests';

interface TestTagsProps {
  sessionToken: string;
  test: TestDetail;
}

export default function TestTags({ sessionToken, test }: TestTagsProps) {
  const [tagNames, setTagNames] = useState<string[]>([]);

  // Initialize and update tag names when test changes
  useEffect(() => {
    if (test.tags) {
      setTagNames(test.tags.map(tag => tag.name));
    }
  }, [test.tags]);

  return (
    <Box sx={{ width: '100%' }}>
      <BaseTag
        value={tagNames}
        onChange={setTagNames}
        label="Tags" 
        placeholder="Add tags (press Enter or comma to add)"
        helperText="These tags help categorize and find this test"
        chipColor="primary"
        addOnBlur
        delimiters={[',', 'Enter']}
        size="small"
        margin="normal"
        fullWidth
        sessionToken={sessionToken}
        entityType={EntityType.TEST}
        entity={test}
        sx={{
          '& .MuiInputBase-root': {
            padding: '16.5px 14px'
          }
        }}
      />
    </Box>
  );
} 