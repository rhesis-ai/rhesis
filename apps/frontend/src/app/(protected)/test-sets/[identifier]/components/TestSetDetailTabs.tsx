'use client';

import React, { useCallback } from 'react';
import { Box } from '@mui/material';
import DetailTabNav from '@/components/common/DetailTabNav';
import { useRouter, useSearchParams } from 'next/navigation';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';
import TestSetDetailsCard from './TestSetDetailsCard';
import TestSetTagsMetricsCard from './TestSetTagsMetricsCard';
import TestSetLinkedTestsSection from './TestSetLinkedTestsSection';

const TAB_KEYS = ['basic', 'linked', 'tasks'] as const;
type TabKey = (typeof TAB_KEYS)[number];

function tabIndexFromKey(key: string | null): number {
  const idx = TAB_KEYS.indexOf(key as TabKey);
  return idx >= 0 ? idx : 0;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`test-set-detail-tabpanel-${index}`}
      aria-labelledby={`test-set-detail-tab-${index}`}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

interface TestSetDetailTabsProps {
  testSet: TestSet;
  testCount: number;
  sessionToken: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export default function TestSetDetailTabs({
  testSet,
  testCount,
  sessionToken,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TestSetDetailTabsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeTab = tabIndexFromKey(searchParams.get('tab'));

  const handleTabChange = useCallback(
    (newValue: number) => {
      const key = TAB_KEYS[newValue];
      const params = new URLSearchParams(searchParams.toString());
      params.set('tab', key);
      router.push(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label:
      key === 'basic'
        ? 'Basic Information'
        : key === 'linked'
          ? 'Linked entities'
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

      {/* Basic Information */}
      <TabPanel value={activeTab} index={0}>
        <TestSetDetailsCard
          sessionToken={sessionToken}
          testSet={testSet}
          onUpdate={handleUpdate}
        />
        <TestSetTagsMetricsCard
          sessionToken={sessionToken}
          testSet={testSet}
          onUpdate={handleUpdate}
        />
      </TabPanel>

      {/* Linked entities */}
      <TabPanel value={activeTab} index={1}>
        <TestSetLinkedTestsSection
          testSetId={testSet.id as string}
          sessionToken={sessionToken}
          testSetType={testSet.test_set_type?.type_value}
          testCount={testCount}
        />
      </TabPanel>

      {/* Tasks */}
      <TabPanel value={activeTab} index={2}>
        <TasksAndCommentsWrapper
          entityType="TestSet"
          entityId={testSet.id as string}
          sessionToken={sessionToken}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
        />
      </TabPanel>
    </Box>
  );
}
