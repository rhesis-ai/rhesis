'use client';

import React, { useCallback } from 'react';
import { Box } from '@mui/material';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import { useRouter } from 'next/navigation';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import type { TestSet } from '@/utils/api-client/interfaces/test-set';
import type { Task } from '@/types/tasks';
import type { Comment } from '@/types/comments';
import type { TestExecutionHistoryRow } from '@/components/tests/test-execution-history';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';
import LinkedTestSetsSection from '@/components/tests/LinkedTestSetsSection';
import TestExecutionHistorySection from '@/components/tests/TestExecutionHistorySection';
import TestMetadataCard from './TestMetadataCard';
import TestTechnicalCard from './TestTechnicalCard';
import TestFormElementsCard from './TestFormElementsCard';
import TestInterpretationCard from './TestInterpretationCard';

const TAB_KEYS = ['basic', 'linked', 'history', 'tasks'] as const;

interface TestDetailTabsProps {
  test: TestDetail;
  /** Server-prefetched first pages for the Linked Test Sets and Tasks tabs. */
  initialLinkedTestSets?: TestSet[];
  initialLinkedTestSetsTotalCount?: number;
  initialTasks?: Task[];
  initialTasksTotalCount?: number;
  initialComments?: Comment[];
  initialExecutionHistory?: TestExecutionHistoryRow[];
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export default function TestDetailTabs({
  test,
  initialLinkedTestSets,
  initialLinkedTestSetsTotalCount,
  initialTasks,
  initialTasksTotalCount,
  initialComments,
  initialExecutionHistory,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TestDetailTabsProps) {
  const router = useRouter();
  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label:
      key === 'basic'
        ? 'Overview'
        : key === 'linked'
          ? 'Linked Test Sets'
          : key === 'history'
            ? 'Execution History'
            : 'Tasks',
    id: `test-detail-tab-${index}`,
    'aria-controls': `test-detail-tabpanel-${index}`,
  }));

  const handleTestUpdate = useCallback(() => {
    router.refresh();
  }, [router]);

  return (
    <Box>
      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={handleTabChange}
        aria-label="Test detail tabs"
      />

      <DetailTabPanel value={activeTab} index={0} prefix="test-detail">
        <TestMetadataCard test={test} onUpdate={handleTestUpdate} />
        <TestTechnicalCard test={test} onUpdate={handleTestUpdate} />
        <TestInterpretationCard test={test} />
        <TestFormElementsCard test={test} onUpdate={handleTestUpdate} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={1} prefix="test-detail">
        <LinkedTestSetsSection
          testId={test.id}
          initialTestSets={initialLinkedTestSets}
          initialTotalCount={initialLinkedTestSetsTotalCount}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={2} prefix="test-detail">
        <TestExecutionHistorySection
          testId={test.id}
          initialRows={initialExecutionHistory}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={3} prefix="test-detail">
        <TasksAndCommentsWrapper
          entityType="Test"
          entityId={test.id}
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
