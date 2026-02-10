'use client';

import React, { useState, useEffect } from 'react';
import { Box } from '@mui/material';
import BaseTag from '@/components/common/BaseTag';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { useTheme } from '@mui/material/styles';

interface TestSetTagsProps {
  sessionToken: string;
  testSet: TestSet;
}

export default function TestSetTags({
  sessionToken,
  testSet,
}: TestSetTagsProps) {
  const [tagNames, setTagNames] = useState<string[]>([]);
  const _theme = useTheme();

  // Initialize and update tag names when testSet changes
  useEffect(() => {
    if (testSet.tags) {
      setTagNames(testSet.tags.map(tag => tag.name));
    }
  }, [testSet.tags]);

  return (
    <Box sx={{ width: '100%' }} suppressHydrationWarning>
      <BaseTag
        value={tagNames}
        onChange={setTagNames}
        label="Tags"
        placeholder="Add tags (press Enter or comma to add)"
        helperText="These tags help categorize and find this test set"
        chipColor="primary"
        addOnBlur
        delimiters={[',', 'Enter']}
        size="small"
        margin="normal"
        fullWidth
        sessionToken={sessionToken}
        entityType={EntityType.TEST_SET}
        entity={testSet}
        className="test-set-tags"
        sx={{
          '&.test-set-tags .MuiInputBase-root': {
            padding: theme => theme.spacing(2),
          },
        }}
      />
    </Box>
  );
}
