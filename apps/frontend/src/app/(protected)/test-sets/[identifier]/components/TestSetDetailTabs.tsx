'use client';

import React, { useCallback } from 'react';
import { Box } from '@mui/material';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import { useRouter } from 'next/navigation';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import type { Task } from '@/types/tasks';
import type { Comment } from '@/types/comments';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';
import TestSetDetailsCard from './TestSetDetailsCard';
import TestSetTagsMetricsCard from './TestSetTagsMetricsCard';
import TestSetLinkedTestsSection from './TestSetLinkedTestsSection';

const TAB_KEYS = ['basic', 'linked', 'tasks'] as const;

interface TestSetDetailTabsProps {
  testSet: TestSet;
  testCount: number;
  /** Server-prefetched first page of the Tests tab; undefined falls back to a client fetch. */
  initialTests?: TestDetail[];
  /** Server-prefetched first page of the Tasks tab. */
  initialTasks?: Task[];
  initialTasksTotalCount?: number;
  initialComments?: Comment[];
  isGenerating?: boolean;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export default function TestSetDetailTabs({
  testSet,
  testCount,
  initialTests,
  initialTasks,
  initialTasksTotalCount,
  initialComments,
  isGenerating = false,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TestSetDetailTabsProps) {
  const router = useRouter();
  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label:
      key === 'basic'
        ? 'Basic Information'
        : key === 'linked'
          ? 'Tests'
          : 'Tasks',
    id: `test-set-detail-tab-${index}`,
    'aria-controls': `test-set-detail-tabpanel-${index}`,
  }));

  const handleUpdate = useCallback(() => {
    router.refresh();
  }, [router]);

  return (
    <Box>
      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={handleTabChange}
        aria-label="Test set detail tabs"
      />

      <DetailTabPanel value={activeTab} index={0} prefix="test-set-detail">
        <TestSetDetailsCard testSet={testSet} onUpdate={handleUpdate} />
        <TestSetTagsMetricsCard testSet={testSet} onUpdate={handleUpdate} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={1} prefix="test-set-detail">
        <TestSetLinkedTestsSection
          testSetId={testSet.id as string}
          testSetType={testSet.test_set_type?.type_value}
          testCount={testCount}
          initialTests={initialTests}
          isGenerating={isGenerating}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={2} prefix="test-set-detail">
        <TasksAndCommentsWrapper
          entityType="TestSet"
          entityId={testSet.id as string}
          initialTasks={initialTasks}
          initialTasksTotalCount={initialTasksTotalCount}
          initialComments={initialComments}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
        />
      </DetailTabPanel>
    </Box>
  );
}
