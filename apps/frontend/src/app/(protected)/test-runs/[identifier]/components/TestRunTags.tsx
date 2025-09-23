'use client';

import React, { useState, useEffect } from 'react';
import { Box } from '@mui/material';
import BaseTag from '@/components/common/BaseTag';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

interface TestRunTagsProps {
  sessionToken: string;
  testRun: TestRunDetail;
}

export default function TestRunTags({ sessionToken, testRun }: TestRunTagsProps) {
  const [tagNames, setTagNames] = useState<string[]>([]);

  // Initialize and update tag names when testRun changes
  useEffect(() => {
    if (testRun.tags) {
      setTagNames(testRun.tags.map(tag => tag.name));
    }
  }, [testRun.tags]);

  return (
    <Box sx={{ width: '100%' }}>
      <BaseTag
        value={tagNames}
        onChange={setTagNames}
        label="Tags" 
        placeholder="Add tags (press Enter or comma to add)"
        helperText="These tags help categorize and find this test run"
        chipColor="default"
        addOnBlur
        delimiters={[',', 'Enter']}
        size="small"
        margin="normal"
        fullWidth
        sessionToken={sessionToken}
        entityType={EntityType.TEST_RUN}
        entity={testRun}
      />
    </Box>
  );
} 