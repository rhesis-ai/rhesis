'use client';

import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestSet, TestSetCreate } from '@/utils/api-client/interfaces/test-set';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import BaseWorkflowSection from '@/components/common/BaseWorkflowSection';

interface TestSetWorkflowSectionProps {
  status?: string;
  priority?: number;
  assignee?: any | null;
  owner?: any | null;
  sessionToken: string;
  testSetId: string;
  onStatusChange?: (newStatus: string) => void;
  onPriorityChange?: (newPriority: number) => void;
  onAssigneeChange?: (newAssignee: User | null) => void;
  onOwnerChange?: (newOwner: User | null) => void;
}

export default function TestSetWorkflowSection({
  status = 'In Review',
  priority = 1,
  assignee,
  owner,
  sessionToken,
  testSetId,
  onStatusChange,
  onPriorityChange,
  onAssigneeChange,
  onOwnerChange,
}: TestSetWorkflowSectionProps) {
  const notifications = useNotifications();

  const updateTestSet = async (
    updateData: Partial<TestSet>,
    fieldName: string
  ) => {
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();
      const {
        id,
        status_details,
        user,
        owner,
        assignee,
        organization,
        ...rest
      } = updateData;
      const processedData: Partial<TestSetCreate> = {
        ...rest,
        tags: updateData.tags?.map(tag =>
          typeof tag === 'string' ? tag : tag.name
        ),
      };
      await testSetsClient.updateTestSet(testSetId, processedData);
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
      clientFactory={new ApiClientFactory(sessionToken)}
      entityId={testSetId}
      entityType="TestSet"
      onStatusChange={onStatusChange}
      onPriorityChange={onPriorityChange}
      onAssigneeChange={onAssigneeChange}
      onOwnerChange={onOwnerChange}
      onUpdateEntity={updateTestSet}
    />
  );
}
