'use client';

import React, { useCallback } from 'react';
import { Box, Tab, Tabs } from '@mui/material';
import { GREYSCALE } from '@/styles/theme';
import { useRouter, useSearchParams } from 'next/navigation';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';
import LinkedTestSetsSection from '@/components/tests/LinkedTestSetsSection';
import TestMetadataCard from './TestMetadataCard';
import TestTechnicalCard from './TestTechnicalCard';
import TestFormElementsCard from './TestFormElementsCard';

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
      id={`test-detail-tabpanel-${index}`}
      aria-labelledby={`test-detail-tab-${index}`}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

interface TestDetailTabsProps {
  test: TestDetail;
  sessionToken: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export default function TestDetailTabs({
  test,
  sessionToken,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TestDetailTabsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const activeTab = tabIndexFromKey(searchParams.get('tab'));

  const handleTabChange = useCallback(
    (_event: React.SyntheticEvent, newValue: number) => {
      const key = TAB_KEYS[newValue];
      const params = new URLSearchParams(searchParams.toString());
      params.set('tab', key);
      router.push(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  const handleTestUpdate = useCallback(() => {
    router.refresh();
  }, [router]);

  return (
    <Box>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          aria-label="test detail tabs"
          sx={{
            '& .MuiTabs-flexContainer': { gap: 6 },
            '& .MuiTab-root': {
              textTransform: 'none',
              fontSize: 18,
              fontWeight: 700,
              lineHeight: '25px',
              minHeight: 48,
              px: 0,
              py: 0.625,
              color: '#b6bdc9',
              '&.Mui-selected': {
                color: GREYSCALE.light.title,
              },
            },
            '& .MuiTabs-indicator': {
              height: 3,
              backgroundColor: 'primary.main',
            },
          }}
        >
          <Tab
            label="Basic Information"
            id="test-detail-tab-0"
            aria-controls="test-detail-tabpanel-0"
          />
          <Tab
            label="Linked entities"
            id="test-detail-tab-1"
            aria-controls="test-detail-tabpanel-1"
          />
          <Tab
            label="Tasks"
            id="test-detail-tab-2"
            aria-controls="test-detail-tabpanel-2"
          />
        </Tabs>
      </Box>

      {/* Basic Information */}
      <TabPanel value={activeTab} index={0}>
        <TestMetadataCard
          sessionToken={sessionToken}
          test={test}
          onUpdate={handleTestUpdate}
        />
        <TestTechnicalCard
          sessionToken={sessionToken}
          test={test}
          onUpdate={handleTestUpdate}
        />
        <TestFormElementsCard
          sessionToken={sessionToken}
          test={test}
          onUpdate={handleTestUpdate}
        />
      </TabPanel>

      {/* Linked entities */}
      <TabPanel value={activeTab} index={1}>
        <LinkedTestSetsSection testId={test.id} sessionToken={sessionToken} />
      </TabPanel>

      {/* Tasks */}
      <TabPanel value={activeTab} index={2}>
        <TasksAndCommentsWrapper
          entityType="Test"
          entityId={test.id}
          sessionToken={sessionToken}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
        />
      </TabPanel>
    </Box>
  );
}
