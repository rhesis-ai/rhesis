'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Test } from '@/utils/api-client/interfaces/tests';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import BaseWorkflowSection from '@/components/common/BaseWorkflowSection';

interface TestWorkflowSectionProps {
  status?: string;
  priority?: number;
  assignee?: any | null;
  owner?: any | null;
  sessionToken: string;
  testId: string;
  onStatusChange?: (newStatus: string) => void;
  onPriorityChange?: (newPriority: number) => void;
  onAssigneeChange?: (newAssignee: User | null) => void;
  onOwnerChange?: (newOwner: User | null) => void;
}

export default function TestWorkflowSection({
  status = 'In Review',
  priority = 1,
  assignee,
  owner,
  sessionToken,
  testId,
  onStatusChange,
  onPriorityChange,
  onAssigneeChange,
  onOwnerChange,
}: TestWorkflowSectionProps) {
  const notifications = useNotifications();

  // Create API clients exactly once
  const apiClients = useMemo(() => {
    if (!sessionToken) return null;

    const clientFactory = new ApiClientFactory(sessionToken);
    return {
      clientFactory,
      testsClient: clientFactory.getTestsClient(),
    };
  }, [sessionToken]);

  const updateTest = async (updateData: Partial<Test>, fieldName: string) => {
    if (!apiClients?.testsClient) {
      notifications.show('Client not initialized', { severity: 'error' });
      return;
    }

    try {
      await apiClients.testsClient.updateTest(testId, updateData);
      notifications.show(`${fieldName} updated successfully`, {
        severity: 'success',
      });
    } catch (error) {
      notifications.show(`Failed to update ${fieldName}`, {
        severity: 'error',
      });
      throw error;
    }
  };

  return (
    <BaseWorkflowSection
      title=""
      status={status}
      priority={priority}
      assignee={assignee}
      owner={owner}
      clientFactory={apiClients?.clientFactory}
      entityId={testId}
      entityType="Test"
      onStatusChange={onStatusChange}
      onPriorityChange={onPriorityChange}
      onAssigneeChange={onAssigneeChange}
      onOwnerChange={onOwnerChange}
      onUpdateEntity={updateTest}
    />
  );
}
