'use client';

import React, { useState, useEffect } from 'react';
import { Box } from '@mui/material';
import BaseTag from '@/components/common/BaseTag';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

interface TestResultTagsProps {
  sessionToken: string;
  testResult: TestResultDetail;
}

export default function TestResultTags({
  sessionToken,
  testResult,
}: TestResultTagsProps) {
  const [tagNames, setTagNames] = useState<string[]>([]);

  // Initialize and update tag names when testResult changes
  useEffect(() => {
    if (testResult.tags) {
      setTagNames(testResult.tags.map(tag => tag.name));
    }
  }, [testResult.tags]);

  return (
    <Box sx={{ width: '100%' }}>
      <BaseTag
        value={tagNames}
        onChange={setTagNames}
        label="Test Result Tags"
        placeholder="Add tags (press Enter or comma to add)"
        helperText="Tags help categorize and find this test result"
        chipColor="primary"
        addOnBlur
        delimiters={[',', 'Enter']}
        size="small"
        margin="normal"
        fullWidth
        sessionToken={sessionToken}
        entityType={EntityType.TEST_RESULT}
        entity={testResult}
      />
    </Box>
  );
}

