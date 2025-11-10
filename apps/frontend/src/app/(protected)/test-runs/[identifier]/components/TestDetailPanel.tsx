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
import ChatOutlinedIcon from '@mui/icons-material/ChatOutlined';
import AssessmentOutlinedIcon from '@mui/icons-material/AssessmentOutlined';
import HistoryIcon from '@mui/icons-material/History';
import CommentOutlinedIcon from '@mui/icons-material/CommentOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import RateReviewIcon from '@mui/icons-material/RateReview';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import TestDetailOverviewTab from './TestDetailOverviewTab';
import TestDetailConversationTab from './TestDetailConversationTab';
import TestDetailMetricsTab from './TestDetailMetricsTab';
import TestDetailReviewsTab from './TestDetailReviewsTab';
import TestDetailHistoryTab from './TestDetailHistoryTab';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

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
  testSetType?: string; // e.g., "Multi-turn" or "Single-turn"
  project?: { icon?: string; useCase?: string; name?: string };
  projectName?: string;
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
  testSetType,
  project,
  projectName,
}: TestDetailPanelProps) {
  const [activeTab, setActiveTab] = useState(0);
  const [reviewInitialComment, setReviewInitialComment] = useState<string>('');
  const [reviewInitialStatus, setReviewInitialStatus] = useState<'passed' | 'failed' | undefined>(undefined);
  const theme = useTheme();

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleReviewTurn = (turnNumber: number, turnSuccess: boolean) => {
    setReviewInitialComment(`Turn ${turnNumber}: `);
    // Set initial status to opposite of automated result
    setReviewInitialStatus(turnSuccess ? 'failed' : 'passed');
    setActiveTab(3); // Switch to reviews tab (index 3)
  };

  const handleConfirmAutomatedReview = async () => {
    if (!test) return;

    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();
      const statusClient = clientFactory.getStatusClient();

      // Get available statuses for TestResult
      const statuses = await statusClient.getStatuses({
        entity_type: 'TestResult',
      });

      // Determine the automated status from goal_evaluation
      const automatedPassed = test.test_output?.goal_evaluation?.all_criteria_met || false;

      // Find appropriate status ID
      const statusKeywords = automatedPassed
        ? ['pass', 'success', 'completed']
        : ['fail', 'error'];
      const targetStatus = statuses.find(status =>
        statusKeywords.some(keyword =>
          status.name.toLowerCase().includes(keyword)
        )
      );

      if (!targetStatus) {
        return;
      }

      // Create a review that matches the automated result
      await testResultsClient.createReview(
        test.id,
        targetStatus.id,
        `Confirmed automated ${automatedPassed ? 'pass' : 'fail'} result.`,
        { type: 'test', reference: null }
      );

      // Refresh the test result
      const updatedTest = await testResultsClient.getTestResult(test.id);
      onTestResultUpdate(updatedTest);
    } catch (error) {
      // Error handling - could be logged to monitoring service
    }
  };

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
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          aria-label="test detail tabs"
          variant="scrollable"
          scrollButtons="auto"
        >
          <Tab
            icon={<InfoOutlinedIcon fontSize="small" />}
            iconPosition="start"
            label="Overview"
            id="test-detail-tab-0"
            aria-controls="test-detail-tabpanel-0"
          />
          <Tab
            icon={<ChatOutlinedIcon fontSize="small" />}
            iconPosition="start"
            label="Conversation"
            id="test-detail-tab-1"
            aria-controls="test-detail-tabpanel-1"
          />
          <Tab
            icon={<AssessmentOutlinedIcon fontSize="small" />}
            iconPosition="start"
            label="Metrics"
            id="test-detail-tab-2"
            aria-controls="test-detail-tabpanel-2"
          />
          <Tab
            icon={<RateReviewIcon fontSize="small" />}
            iconPosition="start"
            label="Reviews"
            id="test-detail-tab-3"
            aria-controls="test-detail-tabpanel-3"
          />
          <Tab
            icon={<HistoryIcon fontSize="small" />}
            iconPosition="start"
            label="History"
            id="test-detail-tab-4"
            aria-controls="test-detail-tabpanel-4"
          />
          <Tab
            icon={<CommentOutlinedIcon fontSize="small" />}
            iconPosition="start"
            label="Tasks & Comments"
            id="test-detail-tab-5"
            aria-controls="test-detail-tabpanel-5"
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
            testSetType={testSetType}
          />
        </TabPanel>

        <TabPanel value={activeTab} index={1}>
          <TestDetailConversationTab 
            test={test} 
            testSetType={testSetType} 
            project={project}
            projectName={projectName}
            onReviewTurn={handleReviewTurn}
            onConfirmAutomatedReview={handleConfirmAutomatedReview}
          />
        </TabPanel>

        <TabPanel value={activeTab} index={2}>
          <TestDetailMetricsTab test={test} behaviors={behaviors} />
        </TabPanel>

        <TabPanel value={activeTab} index={3}>
          <TestDetailReviewsTab
            test={test}
            sessionToken={sessionToken}
            onTestResultUpdate={onTestResultUpdate}
            currentUserId={currentUserId}
            initialComment={reviewInitialComment}
            initialStatus={reviewInitialStatus}
            onCommentUsed={() => {
              setReviewInitialComment('');
              setReviewInitialStatus(undefined);
            }}
          />
        </TabPanel>

        <TabPanel value={activeTab} index={4}>
          <TestDetailHistoryTab
            test={test}
            testRunId={testRunId}
            sessionToken={sessionToken}
          />
        </TabPanel>

        <TabPanel value={activeTab} index={5}>
          <TasksAndCommentsWrapper
            entityType="TestRun"
            entityId={testRunId}
            sessionToken={sessionToken}
            currentUserId={currentUserId}
            currentUserName={currentUserName}
            currentUserPicture={currentUserPicture}
            elevation={0}
            additionalMetadata={{ test_result_id: test.id }}
          />
        </TabPanel>
      </Box>
    </Paper>
  );
}
