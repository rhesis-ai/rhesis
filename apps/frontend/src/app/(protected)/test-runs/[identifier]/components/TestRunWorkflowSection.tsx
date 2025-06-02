'use client';

import { useMemo } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {  TestRunUpdate } from '@/utils/api-client/interfaces/test-run';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import BaseWorkflowSection from '@/components/common/BaseWorkflowSection';
import { Box, Typography } from '@mui/material';

interface TestRunWorkflowSectionProps {
  status?: string;
  assignee?: any | null;
  owner?: any | null;
  sessionToken: string;
  testRunId: string;
  testConfigurationId?: string;
  onAssigneeChange?: (newAssignee: User | null) => void;
  onOwnerChange?: (newOwner: User | null) => void;
}

export default function TestRunWorkflowSection({ 
  status = 'Created',
  assignee,
  owner,
  sessionToken,
  testRunId,
  testConfigurationId,
  onAssigneeChange,
  onOwnerChange
}: TestRunWorkflowSectionProps) {
  const notifications = useNotifications();
  
  // Create a memoized apiClientFactory instance
  const clientFactory = useMemo(() => new ApiClientFactory(sessionToken), [sessionToken]);

  const updateTestRun = async (updateData: TestRunUpdate, fieldName: string) => {
    try {
      const testRunsClient = clientFactory.getTestRunsClient();
      
      await testRunsClient.updateTestRun(testRunId, updateData);
      notifications.show(`${fieldName} updated successfully`, { severity: 'success' });
    } catch (error) {
      console.error('Error updating test run:', error);
      notifications.show(`Failed to update ${fieldName}`, { severity: 'error' });
      throw error; // Re-throw to let the base component handle the error
    }
  };

  return (
    <Box>
      <Typography 
        variant="h6" 
        gutterBottom 
        sx={{ 
          fontWeight: 'medium',
          mb: 1
        }}
      >
        Workflow
      </Typography>
      
      <BaseWorkflowSection
        title=""
        status={status}
        assignee={assignee}
        clientFactory={clientFactory}
        entityId={testRunId}
        entityType="TestRun"
        onAssigneeChange={onAssigneeChange}
        onOwnerChange={onOwnerChange}
        onUpdateEntity={updateTestRun}
        statusReadOnly={true}
        showPriority={false}
      />
    </Box>
  );
} 