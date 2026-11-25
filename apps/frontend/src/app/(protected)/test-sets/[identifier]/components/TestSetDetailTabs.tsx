'use client';

import React, { useCallback } from 'react';
import { Box } from '@mui/material';
import LinkIcon from '@mui/icons-material/Link';
import TestRunsIcon from '@/components/TestRunsIcon';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import { useRouter } from 'next/navigation';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';
import TestSetDetailsCard from './TestSetDetailsCard';
import TestSetTagsMetricsCard from './TestSetTagsMetricsCard';
import TestSetLinkedTestsSection from './TestSetLinkedTestsSection';
import TestSetRunsGrid from './TestSetRunsGrid';
import { TAB_KEYS, TAB_LABELS, type TestSetTabKey } from './tabs';

interface TestSetDetailTabsProps {
  testSet: TestSet;
  testCount: number;
  /** Server-prefetched first page of the Tests tab; undefined falls back to a client fetch. */
  initialTests?: TestDetail[];
  isGenerating?: boolean;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export default function TestSetDetailTabs({
  testSet,
  testCount,
  initialTests,
  isGenerating = false,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TestSetDetailTabsProps) {
  const router = useRouter();
  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);

  const tabIcons: Partial<Record<TestSetTabKey, React.ReactElement>> = {
    linked: <LinkIcon />,
    runs: <TestRunsIcon />,
  };

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label: TAB_LABELS[key],
    ...(tabIcons[key] && { icon: tabIcons[key] }),
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
        <TestSetRunsGrid testSetId={testSet.id as string} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={3} prefix="test-set-detail">
        <TasksAndCommentsWrapper
          entityType="TestSet"
          entityId={testSet.id as string}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
        />
      </DetailTabPanel>
    </Box>
  );
}
