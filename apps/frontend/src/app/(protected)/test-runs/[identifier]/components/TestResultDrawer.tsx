'use client';

import React, { useState, useRef, useMemo } from 'react';
import {
  Box,
  Tabs,
  Tab,
  Typography,
  Skeleton,
  useTheme,
  Button,
  Stack,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import {
  TestResultDetail,
  REVIEW_TARGET_TYPES,
} from '@/utils/api-client/interfaces/test-results';
import BaseDrawer from '@/components/common/BaseDrawer';
import TestDetailOverviewTab from './TestDetailOverviewTab';
import TestDetailConversationTab from './TestDetailConversationTab';
import TestDetailMetricsTab from './TestDetailMetricsTab';
import TestDetailHistoryTab from './TestDetailHistoryTab';
import TestDetailReviewsTab from './TestDetailReviewsTab';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { findStatusByCategory } from '@/utils/test-result-status';
import { MentionOption } from '@/components/common/MentionTextInput';
import { EntityType } from '@/types/entity-type';

export const TEST_RESULT_DRAWER_TAB = {
  overview: 0,
  conversation: 1,
  metrics: 2,
  reviews: 3,
  history: 4,
  tasks: 5,
} as const;

interface TestResultDrawerProps {
  open: boolean;
  onClose: () => void;
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
  onTestResultUpdate: (updatedTest: TestResultDetail) => void;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
  initialTab?: number;
  testSetType?: string; // e.g., "Multi-turn" or "Single-turn"
  project?: { icon?: string; useCase?: string; name?: string };
  projectName?: string;
  /** Source of metrics used in this test run */
  metricsSource?: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  const isActive = value === index;
  return (
    <div
      role="tabpanel"
      id={`test-detail-tabpanel-${index}`}
      aria-labelledby={`test-detail-tab-${index}`}
      style={{
        height: isActive ? '100%' : 0,
        overflow: isActive ? undefined : 'hidden',
        visibility: isActive ? undefined : 'hidden',
      }}
    >
      <Box sx={{ height: '100%' }}>{children}</Box>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <Box>
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

export default function TestResultDrawer({
  open,
  onClose,
  test,
  loading = false,
  prompts,
  behaviors,
  testRunId,
  onTestResultUpdate,
  currentUserId,
  currentUserName,
  currentUserPicture,
  initialTab = 0,
  testSetType,
  project,
  projectName,
  metricsSource,
}: TestResultDrawerProps) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [reviewInitialComment, setReviewInitialComment] = useState<string>('');
  const [reviewInitialStatus, setReviewInitialStatus] = useState<
    'passed' | 'failed' | undefined
  >(undefined);
  const [isConfirmingReview, setIsConfirmingReview] = useState(false);
  const isConfirmingRef = useRef(false);
  const theme = useTheme();

  const isMultiTurn =
    testSetType?.toLowerCase().includes('multi-turn') || false;

  const TAB = TEST_RESULT_DRAWER_TAB;

  // Update active tab when initialTab changes (when drawer opens with specific tab)
  React.useEffect(() => {
    if (open) {
      setActiveTab(initialTab);
    }
  }, [open, initialTab]);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleReviewTurn = (turnNumber: number, turnSuccess: boolean) => {
    setReviewInitialComment(`@[Turn ${turnNumber}](turn:${turnNumber}) `);
    setReviewInitialStatus(turnSuccess ? 'failed' : 'passed');
    setActiveTab(TAB.reviews);
  };

  const mentionableMetrics: MentionOption[] = useMemo(() => {
    if (!test?.test_metrics?.metrics) return [];
    return Object.keys(test.test_metrics.metrics).map(name => ({
      id: name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, ''),
      display: name,
      type: 'metric' as const,
    }));
  }, [test]);

  const mentionableTurns: MentionOption[] = useMemo(() => {
    const summary = test?.test_output?.conversation_summary;
    if (!summary || !Array.isArray(summary)) return [];
    return summary.map((turn: { turn: number }) => ({
      id: String(turn.turn),
      display: `Turn ${turn.turn}`,
      type: 'turn' as const,
    }));
  }, [test]);

  const handleConfirmAutomatedReview = async () => {
    if (!test) return;

    // Atomic check-and-set to prevent duplicate submissions
    if (isConfirmingRef.current) return;
    isConfirmingRef.current = true;

    try {
      setIsConfirmingReview(true);

      const clientFactory = new ApiClientFactory();
      const testResultsClient = clientFactory.getTestResultsClient();
      const statusClient = clientFactory.getStatusClient();

      // Get available statuses for TestResult
      const statuses = await statusClient.getStatuses({
        entity_type: EntityType.TEST_RESULT,
      });

      // Determine the automated status from goal_evaluation
      const automatedPassed =
        test.test_output?.goal_evaluation?.all_criteria_met || false;

      // Find appropriate status ID using centralized utility
      const targetStatus = findStatusByCategory(
        statuses,
        automatedPassed ? 'passed' : 'failed'
      );

      if (!targetStatus) {
        return;
      }

      // Create a review that matches the automated result
      await testResultsClient.createReview(
        test.id,
        targetStatus.id,
        `Confirmed automated ${automatedPassed ? 'pass' : 'fail'} result.`,
        { type: REVIEW_TARGET_TYPES.TEST_RESULT, reference: null }
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

  // Handle counts change (when comments/tasks are added or deleted)
  const handleCountsChange = React.useCallback(async () => {
    if (!test) return;

    // Refetch the test result to get updated counts
    try {
      const { ApiClientFactory } =
        await import('@/utils/api-client/client-factory');
      const apiFactory = new ApiClientFactory();
      const testResultsClient = apiFactory.getTestResultsClient();
      const updatedTest = await testResultsClient.getTestResult(test.id);

      // Notify parent to update its state
      onTestResultUpdate(updatedTest);
    } catch (error) {
      console.error('Failed to update test result counts:', error);
    }
  }, [test, onTestResultUpdate]);

  const drawerContent = () => {
    if (loading) {
      return <LoadingSkeleton />;
    }

    if (!test) {
      return <EmptyState />;
    }

    return (
      <Box
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
            backgroundColor: theme.palette.background.paper,
            position: 'sticky',
            top: 0,
            zIndex: 1,
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
                minHeight: 43,
                minWidth: 'auto',
                paddingX: 0,
                paddingY: '5px',
                marginRight: theme.spacing(6.25),
                textTransform: 'none',
                fontSize: theme.typography.pxToRem(18),
                fontWeight: 700,
                lineHeight: '25px',
                color: theme.palette.text.disabled,
                '&:hover:not(.Mui-selected)': {
                  color: theme.palette.text.secondary,
                  backgroundColor: 'transparent',
                },
                '&.Mui-selected': {
                  color: theme.palette.text.primary,
                  fontWeight: 700,
                  backgroundColor: 'transparent',
                },
              },
              '& .MuiTabs-indicator': {
                height: 2,
                backgroundColor: theme.palette.text.primary,
              },
              '& .MuiTabs-flexContainer': {
                gap: 0,
              },
            }}
          >
            <Tab
              label="Overview"
              id="test-detail-tab-0"
              aria-controls="test-detail-tabpanel-0"
            />
            <Tab
              label="Conversation"
              id="test-detail-tab-1"
              aria-controls="test-detail-tabpanel-1"
            />
            <Tab
              label="Metrics"
              id="test-detail-tab-2"
              aria-controls="test-detail-tabpanel-2"
            />
            <Tab
              label="Reviews"
              id="test-detail-tab-3"
              aria-controls="test-detail-tabpanel-3"
            />
            <Tab
              label="History"
              id="test-detail-tab-4"
              aria-controls="test-detail-tabpanel-4"
            />
            <Tab
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
          <TabPanel value={activeTab} index={TAB.overview}>
            <TestDetailOverviewTab
              test={test}
              prompts={prompts}
              onTestResultUpdate={onTestResultUpdate}
              testSetType={testSetType}
            />
          </TabPanel>

          <TabPanel value={activeTab} index={TAB.conversation}>
            <TestDetailConversationTab
              test={test}
              testSetType={testSetType}
              project={project}
              projectName={projectName}
              onReviewTurn={isMultiTurn ? handleReviewTurn : undefined}
              onConfirmAutomatedReview={handleConfirmAutomatedReview}
              isConfirmingReview={isConfirmingReview}
            />
          </TabPanel>

          <TabPanel value={activeTab} index={TAB.metrics}>
            <TestDetailMetricsTab
              test={test}
              behaviors={behaviors}
              metricsSource={metricsSource}
            />
          </TabPanel>

          <TabPanel value={activeTab} index={TAB.reviews}>
            <TestDetailReviewsTab
              test={test}
              onTestResultUpdate={onTestResultUpdate}
              currentUserId={currentUserId}
              initialComment={reviewInitialComment}
              initialStatus={reviewInitialStatus}
              onCommentUsed={() => {
                setReviewInitialComment('');
                setReviewInitialStatus(undefined);
              }}
              mentionableMetrics={mentionableMetrics}
              mentionableTurns={mentionableTurns}
            />
          </TabPanel>

          <TabPanel value={activeTab} index={TAB.history}>
            <TestDetailHistoryTab test={test} testRunId={testRunId} />
          </TabPanel>

          <TabPanel value={activeTab} index={TAB.tasks}>
            <Box sx={{ pt: '40px' }}>
              <TasksAndCommentsWrapper
                entityType="TestResult"
                entityId={test.id}
                currentUserId={currentUserId}
                currentUserName={currentUserName}
                currentUserPicture={currentUserPicture}
                onCountsChange={handleCountsChange}
                additionalMetadata={{ test_run_id: testRunId }}
              />
            </Box>
          </TabPanel>
        </Box>

        <Box
          sx={{
            flexShrink: 0,
            px: 2,
            py: 2,
            bgcolor: 'background.paper',
          }}
        >
          <Stack direction="row" spacing={2} justifyContent="flex-end">
            {(test?.test?.id ?? test?.test_id) && (
              <Button
                variant="outlined"
                endIcon={<OpenInNewIcon />}
                component="a"
                href={`/tests/${test.test?.id ?? test.test_id}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Go to Test
              </Button>
            )}
            <Button variant="contained" onClick={onClose}>
              Close
            </Button>
          </Stack>
        </Box>
      </Box>
    );
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      width="75%"
      showHeader={false}
      closeButtonText=""
    >
      {drawerContent()}
    </BaseDrawer>
  );
}
