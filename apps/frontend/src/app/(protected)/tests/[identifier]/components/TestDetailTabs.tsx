'use client';

import React, { useCallback } from 'react';
import { Box } from '@mui/material';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import { useRouter } from 'next/navigation';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';
import LinkedTestSetsSection from '@/components/tests/LinkedTestSetsSection';
import TestExecutionHistorySection from '@/components/tests/TestExecutionHistorySection';
import TestMetadataCard from './TestMetadataCard';
import TestTechnicalCard from './TestTechnicalCard';
import TestFormElementsCard from './TestFormElementsCard';

const TAB_KEYS = ['basic', 'linked', 'history', 'tasks'] as const;

interface TestDetailTabsProps {
  test: TestDetail;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export default function TestDetailTabs({
  test,
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
        <TestFormElementsCard test={test} onUpdate={handleTestUpdate} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={1} prefix="test-detail">
        <LinkedTestSetsSection testId={test.id} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={2} prefix="test-detail">
        <TestExecutionHistorySection testId={test.id} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={3} prefix="test-detail">
        <TasksAndCommentsWrapper
          entityType="Test"
          entityId={test.id}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
        />
      </DetailTabPanel>
    </Box>
  );
}
