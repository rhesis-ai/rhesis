'use client';

import React, { useState } from 'react';
import {
  Box,
  Paper,
  Tabs,
  Tab,
  Typography,
  Divider,
  Skeleton,
  useTheme,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import AssessmentOutlinedIcon from '@mui/icons-material/AssessmentOutlined';
import HistoryIcon from '@mui/icons-material/History';
import CommentOutlinedIcon from '@mui/icons-material/CommentOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import GavelIcon from '@mui/icons-material/Gavel';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import TestDetailOverviewTab from './TestDetailOverviewTab';
import TestDetailMetricsTab from './TestDetailMetricsTab';
import TestDetailHistoryTab from './TestDetailHistoryTab';
import TestDetailReviewsTab from './TestDetailReviewsTab';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';

interface TestDetailPanelProps {
  test: TestResultDetail | null;
  loading?: boolean;
  prompts: Record<string, { content: string; name?: string }>;
  behaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }>;
  testRunId: string;
  sessionToken: string;
  onTestResultUpdate: (updatedTest: TestResultDetail) => void;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
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
      style={{ height: '100%' }}
    >
      {value === index && <Box sx={{ height: '100%' }}>{children}</Box>}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <Box sx={{ p: 3 }}>
      <Skeleton variant="rectangular" height={40} sx={{ mb: 2 }} />
      <Skeleton variant="text" width="60%" height={24} sx={{ mb: 1 }} />
      <Skeleton variant="text" width="80%" height={20} sx={{ mb: 3 }} />
      <Skeleton variant="rectangular" height={200} sx={{ mb: 2 }} />
      <Skeleton variant="rectangular" height={150} />
    </Box>
  );
}

function EmptyState() {
  const theme = useTheme();

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        p: 4,
        textAlign: 'center',
      }}
    >
      <InfoOutlinedIcon
        sx={{
          fontSize: 64,
          color: theme.palette.text.disabled,
          mb: 2,
        }}
      />
      <Typography variant="h6" color="text.secondary" gutterBottom>
        No Test Selected
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Select a test from the list to view its details
      </Typography>
    </Box>
  );
}

export default function TestDetailPanel({
  test,
  loading = false,
  prompts,
  behaviors,
  testRunId,
  sessionToken,
  onTestResultUpdate,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TestDetailPanelProps) {
  const [activeTab, setActiveTab] = useState(0);
  const theme = useTheme();

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  // Handle counts change (when comments/tasks are added or deleted)
  const handleCountsChange = React.useCallback(async () => {
    if (!test) return;

    // Refetch the test result to get updated counts
    try {
      const { ApiClientFactory } = await import(
        '@/utils/api-client/client-factory'
      );
      const apiFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = apiFactory.getTestResultsClient();
      const updatedTest = await testResultsClient.getTestResult(test.id);

      // Notify parent to update its state
      onTestResultUpdate(updatedTest);
    } catch (error) {
      console.error('Error refetching test result:', error);
    }
  }, [test, sessionToken, onTestResultUpdate]);

  if (loading) {
    return (
      <Paper
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <LoadingSkeleton />
      </Paper>
    );
  }

  if (!test) {
    return (
      <Paper
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <EmptyState />
      </Paper>
    );
  }

  return (
    <Paper
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Tabs Header */}
      <Box
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          backgroundColor: theme.palette.background.paper,
        }}
      >
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          aria-label="test detail tabs"
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            '& .MuiTab-root': {
              minHeight: 56,
              textTransform: 'none',
              fontWeight: 500,
              color: theme.palette.text.secondary,
              '& .MuiSvgIcon-root': {
                color: 'inherit',
              },
              '&:hover:not(.Mui-selected)': {
                backgroundColor: theme.palette.action.hover,
                color: theme.palette.text.primary,
              },
              '&.Mui-selected': {
                backgroundColor: 'transparent',
                color: theme.palette.primary.main,
                fontWeight: 600,
                '& .MuiSvgIcon-root': {
                  color: 'inherit',
                },
              },
            },
            '& .MuiTabs-indicator': {
              height: 3,
              borderTopLeftRadius: theme.shape.borderRadius,
              borderTopRightRadius: theme.shape.borderRadius,
            },
          }}
        >
          <Tab
            icon={<InfoOutlinedIcon fontSize="small" />}
            iconPosition="start"
            label="Overview"
            id="test-detail-tab-0"
            aria-controls="test-detail-tabpanel-0"
          />
          <Tab
            icon={<AssessmentOutlinedIcon fontSize="small" />}
            iconPosition="start"
            label="Metrics"
            id="test-detail-tab-1"
            aria-controls="test-detail-tabpanel-1"
          />
          <Tab
            icon={<GavelIcon fontSize="small" />}
            iconPosition="start"
            label="Reviews"
            id="test-detail-tab-2"
            aria-controls="test-detail-tabpanel-2"
          />
          <Tab
            icon={<HistoryIcon fontSize="small" />}
            iconPosition="start"
            label="History"
            id="test-detail-tab-3"
            aria-controls="test-detail-tabpanel-3"
          />
          <Tab
            icon={<CommentOutlinedIcon fontSize="small" />}
            iconPosition="start"
            label="Tasks & Comments"
            id="test-detail-tab-4"
            aria-controls="test-detail-tabpanel-4"
          />
        </Tabs>
      </Box>

      {/* Tab Content - with scrolling */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          // Custom scrollbar styling
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-track': {
            background: theme.palette.background.default,
            borderRadius: '4px',
          },
          '&::-webkit-scrollbar-thumb': {
            background: theme.palette.divider,
            borderRadius: '4px',
            '&:hover': {
              background: theme.palette.action.hover,
            },
          },
        }}
      >
        <TabPanel value={activeTab} index={0}>
          <TestDetailOverviewTab
            test={test}
            prompts={prompts}
            sessionToken={sessionToken}
            onTestResultUpdate={onTestResultUpdate}
          />
        </TabPanel>

        <TabPanel value={activeTab} index={1}>
          <TestDetailMetricsTab test={test} behaviors={behaviors} />
        </TabPanel>

        <TabPanel value={activeTab} index={2}>
          <TestDetailReviewsTab test={test} />
        </TabPanel>

        <TabPanel value={activeTab} index={3}>
          <TestDetailHistoryTab
            test={test}
            testRunId={testRunId}
            sessionToken={sessionToken}
          />
        </TabPanel>

        <TabPanel value={activeTab} index={4}>
          <TasksAndCommentsWrapper
            entityType="TestResult"
            entityId={test.id}
            sessionToken={sessionToken}
            currentUserId={currentUserId}
            currentUserName={currentUserName}
            currentUserPicture={currentUserPicture}
            elevation={0}
            onCountsChange={handleCountsChange}
          />
        </TabPanel>
      </Box>
    </Paper>
  );
}
