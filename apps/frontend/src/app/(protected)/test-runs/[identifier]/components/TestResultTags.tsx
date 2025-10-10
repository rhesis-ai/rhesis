'use client';

import React, { useState, useEffect } from 'react';
import { Box } from '@mui/material';
import BaseTag from '@/components/common/BaseTag';
import { EntityType, Tag } from '@/utils/api-client/interfaces/tag';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

interface TestResultTagsProps {
  sessionToken: string;
  testResult: TestResultDetail;
  onUpdate: (updatedTest: TestResultDetail) => void;
}

export default function TestResultTags({
  sessionToken,
  testResult,
  onUpdate,
}: TestResultTagsProps) {
  const [tagNames, setTagNames] = useState<string[]>([]);

  // Initialize and update tag names when testResult changes
  useEffect(() => {
    // Reset tags whenever test result changes (based on ID)
    // TestResult now has tags property via TagsMixin
    const tags = testResult.tags;
    if (tags && Array.isArray(tags)) {
      setTagNames(tags.map((tag: any) => tag.name));
    } else {
      setTagNames([]);
    }
  }, [testResult.id]);

  // Handle tag changes and update parent state
  const handleTagChange = async (newTagNames: string[]) => {
    // Update local state immediately
    setTagNames(newTagNames);

    // After BaseTag completes its API calls, fetch the updated test result
    // We use a small delay to ensure API calls have completed
    setTimeout(async () => {
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const testResultsClient = apiFactory.getTestResultsClient();
        const updatedTestResult = await testResultsClient.getTestResult(
          testResult.id
        );

        // Notify parent of the update
        onUpdate(updatedTestResult);
      } catch (error) {
        console.error('Failed to fetch updated test result:', error);
      }
    }, 500);
  };

  return (
    <Box sx={{ width: '100%' }}>
      <BaseTag
        value={tagNames}
        onChange={handleTagChange}
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
