'use client';

import React, { useState, useRef } from 'react';
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
  const [reviewInitialStatus, setReviewInitialStatus] = useState<
    'passed' | 'failed' | undefined
  >(undefined);
  const [isConfirmingReview, setIsConfirmingReview] = useState(false);
  const isConfirmingRef = useRef(false);
  const theme = useTheme();

  // Determine if this is a multi-turn test
  const isMultiTurn =
    testSetType?.toLowerCase().includes('multi-turn') || false;

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleReviewTurn = (turnNumber: number, turnSuccess: boolean) => {
    setReviewInitialComment(`Turn ${turnNumber}: `);
    // Set initial status to opposite of automated result
    setReviewInitialStatus(turnSuccess ? 'failed' : 'passed');
    setActiveTab(isMultiTurn ? 3 : 2); // Switch to reviews tab (index depends on multi-turn)
  };

  const handleConfirmAutomatedReview = async () => {
    if (!test) return;

    // Atomic check-and-set to prevent duplicate submissions
    if (isConfirmingRef.current) return;
    isConfirmingRef.current = true;

    try {
      setIsConfirmingReview(true);

      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();
      const statusClient = clientFactory.getStatusClient();

      // Get available statuses for TestResult
      const statuses = await statusClient.getStatuses({
        entity_type: 'TestResult',
      });

      // Determine the automated status from goal_evaluation
      const automatedPassed =
        test.test_output?.goal_evaluation?.all_criteria_met || false;

      // Find appropriate status ID
      // Prioritize exact matches or longer forms (e.g., "Passed" over "Pass", "Failed" over "Fail")
      let targetStatus;
      if (automatedPassed) {
        // Try exact matches first, then longer forms, then any match
        targetStatus =
          statuses.find(s => s.name.toLowerCase() === 'passed') ||
          statuses.find(s => s.name.toLowerCase() === 'pass') ||
          statuses.find(s => s.name.toLowerCase().includes('success')) ||
          statuses.find(s => s.name.toLowerCase().includes('completed'));
      } else {
        // For failed tests, prefer "Failed" over "Fail", avoid "Error"
        targetStatus =
          statuses.find(s => s.name.toLowerCase() === 'failed') ||
          statuses.find(s => s.name.toLowerCase() === 'fail') ||
          statuses.find(s => s.name.toLowerCase().includes('failure'));

        // Only fall back to 'error' if no other failed status is found
        if (!targetStatus) {
          targetStatus = statuses.find(s =>
            s.name.toLowerCase().includes('error')
          );
        }
      }

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
      console.error('Failed to confirm automated review:', error);
    } finally {
      setIsConfirmingReview(false);
      isConfirmingRef.current = false;
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
          {isMultiTurn && (
            <Tab
              icon={<ChatOutlinedIcon fontSize="small" />}
              iconPosition="start"
              label="Conversation"
              id="test-detail-tab-1"
              aria-controls="test-detail-tabpanel-1"
            />
          )}
          <Tab
            icon={<AssessmentOutlinedIcon fontSize="small" />}
            iconPosition="start"
            label="Metrics"
            id={`test-detail-tab-${isMultiTurn ? '2' : '1'}`}
            aria-controls={`test-detail-tabpanel-${isMultiTurn ? '2' : '1'}`}
          />
          <Tab
            icon={<RateReviewIcon fontSize="small" />}
            iconPosition="start"
            label="Reviews"
            id={`test-detail-tab-${isMultiTurn ? '3' : '2'}`}
            aria-controls={`test-detail-tabpanel-${isMultiTurn ? '3' : '2'}`}
          />
          <Tab
            icon={<HistoryIcon fontSize="small" />}
            iconPosition="start"
            label="History"
            id={`test-detail-tab-${isMultiTurn ? '4' : '3'}`}
            aria-controls={`test-detail-tabpanel-${isMultiTurn ? '4' : '3'}`}
          />
          <Tab
            icon={<CommentOutlinedIcon fontSize="small" />}
            iconPosition="start"
            label="Tasks & Comments"
            id={`test-detail-tab-${isMultiTurn ? '5' : '4'}`}
            aria-controls={`test-detail-tabpanel-${isMultiTurn ? '5' : '4'}`}
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

        {isMultiTurn && (
          <TabPanel value={activeTab} index={1}>
            <TestDetailConversationTab
              test={test}
              testSetType={testSetType}
              project={project}
              projectName={projectName}
              onReviewTurn={handleReviewTurn}
              onConfirmAutomatedReview={handleConfirmAutomatedReview}
              isConfirmingReview={isConfirmingReview}
            />
          </TabPanel>
        )}

        <TabPanel value={activeTab} index={isMultiTurn ? 2 : 1}>
          <TestDetailMetricsTab test={test} behaviors={behaviors} />
        </TabPanel>

        <TabPanel value={activeTab} index={isMultiTurn ? 3 : 2}>
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

        <TabPanel value={activeTab} index={isMultiTurn ? 4 : 3}>
          <TestDetailHistoryTab
            test={test}
            testRunId={testRunId}
            sessionToken={sessionToken}
          />
        </TabPanel>

        <TabPanel value={activeTab} index={isMultiTurn ? 5 : 4}>
          <TasksAndCommentsWrapper
            entityType="TestResult"
            entityId={test.id}
            sessionToken={sessionToken}
            currentUserId={currentUserId}
            currentUserName={currentUserName}
            currentUserPicture={currentUserPicture}
            elevation={0}
          />
        </TabPanel>
      </Box>
    </Paper>
  );
}
