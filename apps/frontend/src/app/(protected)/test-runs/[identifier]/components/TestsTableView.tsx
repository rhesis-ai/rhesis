'use client';

import React, { useState, useMemo } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Box,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  TablePagination,
  useTheme,
  alpha,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import CommentOutlinedIcon from '@mui/icons-material/CommentOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import CheckIcon from '@mui/icons-material/Check';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import CircleOutlinedIcon from '@mui/icons-material/CircleOutlined';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import TestResultDrawer from './TestResultDrawer';
import ReviewJudgementDrawer, { ReviewData } from './ReviewJudgementDrawer';

interface TestsTableViewProps {
  tests: TestResultDetail[];
  prompts: Record<string, { content: string; name?: string }>;
  behaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }>;
  testRunId: string;
  sessionToken: string;
  loading?: boolean;
  onTestResultUpdate: (updatedTest: TestResultDetail) => void;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
  initialSelectedTestId?: string;
  testSetType?: string; // e.g., "Multi-turn" or "Single-turn"
  project?: { icon?: string; useCase?: string; name?: string };
  projectName?: string;
}

export default function TestsTableView({
  tests,
  prompts,
  behaviors,
  testRunId,
  sessionToken,
  loading = false,
  onTestResultUpdate,
  currentUserId,
  currentUserName,
  currentUserPicture,
  initialSelectedTestId,
  testSetType,
  project,
  projectName,
}: TestsTableViewProps) {
  const isMultiTurn =
    testSetType?.toLowerCase().includes('multi-turn') || false;
  const theme = useTheme();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [selectedTest, setSelectedTest] = useState<TestResultDetail | null>(
    null
  );
  const [selectedRowIndex, setSelectedRowIndex] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [initialTab, setInitialTab] = useState<number>(0);
  const [overruleDrawerOpen, setOverruleDrawerOpen] = useState(false);
  const [testToOverrule, setTestToOverrule] = useState<TestResultDetail | null>(
    null
  );
  const [hasInitialSelection, setHasInitialSelection] = useState(false);
  const [isConfirmingReview, setIsConfirmingReview] = useState(false);

  // Local state to track immediate test updates before parent prop updates
  const [localTestUpdates, setLocalTestUpdates] = useState<
    Record<string, TestResultDetail>
  >({});

  // Merge local updates with tests prop for immediate UI updates
  const mergedTests = React.useMemo(() => {
    if (Object.keys(localTestUpdates).length === 0) {
      return tests;
    }
    const merged = tests.map(test => {
      const updated = localTestUpdates[test.id];
      return updated || test;
    });
    return merged;
  }, [tests, localTestUpdates]);

  // Clear local updates when tests prop changes AND includes our local updates
  React.useEffect(() => {
    if (Object.keys(localTestUpdates).length > 0) {
      // Check if any of our local updates are now in the tests prop
      const allUpdatesIncluded = Object.keys(localTestUpdates).every(testId => {
        const propTest = tests.find(t => t.id === testId);
        const localTest = localTestUpdates[testId];
        // Check if the prop test has the same last_review as our local update
        return (
          propTest?.last_review?.review_id === localTest?.last_review?.review_id
        );
      });

      if (allUpdatesIncluded) {
        setLocalTestUpdates({});
      }
    }
  }, [tests, localTestUpdates]);

  // Handle initial selection when initialSelectedTestId is provided
  React.useEffect(() => {
    if (
      initialSelectedTestId &&
      mergedTests.length > 0 &&
      !hasInitialSelection
    ) {
      const testIndex = mergedTests.findIndex(
        t => t.id === initialSelectedTestId
      );
      if (testIndex !== -1) {
        // Calculate which page the test is on
        const testPage = Math.floor(testIndex / rowsPerPage);
        const rowIndexInPage = testIndex % rowsPerPage;

        setPage(testPage);
        setSelectedTest(mergedTests[testIndex]);
        setSelectedRowIndex(rowIndexInPage);
        setDrawerOpen(true);
        setHasInitialSelection(true);
      }
    }
  }, [initialSelectedTestId, mergedTests, rowsPerPage, hasInitialSelection]);

  // Sync selectedTest with tests array when tests are updated (e.g., after review changes)
  React.useEffect(() => {
    if (selectedTest) {
      const updatedTest = mergedTests.find(t => t.id === selectedTest.id);
      if (updatedTest && updatedTest !== selectedTest) {
        setSelectedTest(updatedTest);
      }
    }
    // Note: selectedTest is intentionally excluded from dependencies to avoid infinite loops
    // since this effect updates selectedTest itself
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mergedTests]);

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleRowClick = (
    test: TestResultDetail,
    index: number,
    tabIndex: number = 0
  ) => {
    setSelectedTest(test);
    setSelectedRowIndex(index);
    setInitialTab(tabIndex);
    setDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setDrawerOpen(false);
  };

  // Handle test result updates from the drawer (e.g., when reviews are added/deleted)
  const handleTestResultUpdateInDrawer = (updatedTest: TestResultDetail) => {
    // Update local selected test state if it's the same test
    if (selectedTest && selectedTest.id === updatedTest.id) {
      setSelectedTest(updatedTest);
    }
    // Propagate to parent component to update the tests array
    onTestResultUpdate(updatedTest);
  };

  const handleOverruleJudgement = (
    event: React.MouseEvent,
    test: TestResultDetail
  ) => {
    event.stopPropagation();
    setTestToOverrule(test);
    setOverruleDrawerOpen(true);
  };

  const handleOverruleSave = async (testId: string, reviewData: ReviewData) => {
    try {
      // Fetch the updated test result from the backend
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();
      const updatedTest = await testResultsClient.getTestResult(testId);

      // Update the test in the parent component
      onTestResultUpdate(updatedTest);
    } catch (error) {
      console.error('Failed to save overrule judgement:', error);
    }
  };

  const handleConfirmReview = async (
    event: React.MouseEvent,
    test: TestResultDetail
  ) => {
    event.stopPropagation();

    // Prevent duplicate submissions
    if (isConfirmingReview) return;

    try {
      setIsConfirmingReview(true);

      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();
      const statusClient = clientFactory.getStatusClient();

      // Get available statuses for TestResult
      const statuses = await statusClient.getStatuses({
        entity_type: 'TestResult',
      });

      // Determine the current automated status
      // For multi-turn tests
      let automatedPassed = false;
      if (isMultiTurn && test.test_output?.goal_evaluation) {
        automatedPassed =
          test.test_output.goal_evaluation.all_criteria_met || false;
      } else {
        // For single-turn tests
        const metrics = test.test_metrics?.metrics || {};
        const metricValues = Object.values(metrics);
        const totalMetrics = metricValues.length;
        const passedMetrics = metricValues.filter(m => m.is_successful).length;
        automatedPassed = totalMetrics > 0 && passedMetrics === totalMetrics;
      }

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

      // Poll for the updated test result with exponential backoff
      let updatedTest: TestResultDetail | null = null;
      const delays = [100, 200, 400, 800, 1600]; // Exponential backoff delays

      for (const delay of delays) {
        await new Promise(resolve => setTimeout(resolve, delay));
        const fetchedTest = await testResultsClient.getTestResult(test.id);

        // Check if last_review property is now present
        if (fetchedTest.last_review) {
          updatedTest = fetchedTest;
          break;
        }
      }

      // If we still don't have the updated test after all attempts, fetch one more time
      if (!updatedTest) {
        updatedTest = await testResultsClient.getTestResult(test.id);
      }

      // IMMEDIATELY update local state for instant UI feedback
      setLocalTestUpdates(prev => ({
        ...prev,
        [updatedTest.id]: updatedTest,
      }));

      // Update local selected test if this is the currently selected test
      if (selectedTest && selectedTest.id === test.id) {
        setSelectedTest(updatedTest);
      }

      // Propagate to parent component
      onTestResultUpdate(updatedTest);
    } catch (error) {
      console.error('Failed to confirm review:', error);
    } finally {
      setIsConfirmingReview(false);
    }
  };

  // Calculate test result status (considering reviews from backend)
  const getTestStatus = (test: TestResultDetail) => {
    // For multi-turn tests, use goal_evaluation
    if (isMultiTurn && test.test_output?.goal_evaluation) {
      const allCriteriaMet = test.test_output.goal_evaluation.all_criteria_met;
      const totalCriteria =
        test.test_output.goal_evaluation.criteria_evaluations?.length || 0;
      const metCriteria =
        test.test_output.goal_evaluation.criteria_evaluations?.filter(
          c => c.met
        )?.length || 0;

      const originalPassed = allCriteriaMet === true;
      const lastReview = test.last_review;

      // Check for human review FIRST (reviews override automated results)
      if (lastReview && lastReview.status?.name) {
        const reviewStatusName = lastReview.status.name.toLowerCase();
        const reviewPassed =
          reviewStatusName.includes('pass') ||
          reviewStatusName.includes('success') ||
          reviewStatusName.includes('completed');

        // Calculate conflict ourselves (don't trust backend's matches_review)
        // A conflict exists if the review decision differs from the automated decision
        const hasConflict = reviewPassed !== originalPassed;

        const result = {
          passed: reviewPassed,
          label: reviewPassed ? 'Passed' : 'Failed',
          count: `${metCriteria}/${totalCriteria}`,
          isOverruled: true,
          hasConflict,
          automatedPassed: originalPassed,
          hasExecutionError: false,
          reviewData: {
            reviewer: lastReview.user?.name || 'Unknown',
            comments: lastReview.comments,
            updated_at: lastReview.updated_at,
            newStatus: reviewPassed ? 'passed' : 'failed',
          },
        };

        return result;
      }

      // No review, check for execution errors/failures
      const hasExecutionError = test.test_output.status === 'error';
      const hasExecutionFailure = test.test_output.status === 'failure';

      if (hasExecutionError) {
        return {
          passed: false,
          label: 'Error',
          count: `${metCriteria}/${totalCriteria}`,
          isOverruled: false,
          hasConflict: false,
          hasExecutionError: true,
        };
      }

      if (hasExecutionFailure) {
        return {
          passed: false,
          label: 'Failed',
          count: `${metCriteria}/${totalCriteria}`,
          isOverruled: false,
          hasConflict: false,
          hasExecutionError: false,
        };
      }

      return {
        passed: originalPassed,
        label: originalPassed ? 'Passed' : 'Failed',
        count: `${metCriteria}/${totalCriteria}`,
        isOverruled: false,
        hasConflict: false,
        automatedPassed: originalPassed,
        hasExecutionError: false,
      };
    }

    // For single-turn tests, use metrics (original logic)
    const metrics = test.test_metrics?.metrics || {};
    const metricValues = Object.values(metrics);
    const totalMetrics = metricValues.length;
    const passedMetrics = metricValues.filter(m => m.is_successful).length;

    // Check for execution error (no metrics or empty metrics)
    const hasExecutionError = !test.test_metrics || totalMetrics === 0;

    if (hasExecutionError) {
      return {
        passed: false,
        label: 'Error',
        count: '0/0',
        isOverruled: false,
        hasConflict: false,
        hasExecutionError: true,
      };
    }

    const originalPassed = passedMetrics === totalMetrics;
    const lastReview = test.last_review;

    // If there's a review, use the review status
    if (lastReview && lastReview.status?.name) {
      const reviewStatusName = lastReview.status.name.toLowerCase();
      const reviewPassed =
        reviewStatusName.includes('pass') ||
        reviewStatusName.includes('success') ||
        reviewStatusName.includes('completed');

      // Calculate conflict ourselves (don't trust backend's matches_review)
      // A conflict exists if the review decision differs from the automated decision
      const hasConflict = reviewPassed !== originalPassed;

      return {
        passed: reviewPassed,
        label: reviewPassed ? 'Passed' : 'Failed',
        count: `${passedMetrics}/${totalMetrics}`,
        isOverruled: true,
        hasConflict,
        automatedPassed: originalPassed, // Keep original automated result
        hasExecutionError: false,
        reviewData: {
          reviewer: lastReview.user?.name || 'Unknown',
          comments: lastReview.comments,
          updated_at: lastReview.updated_at,
          newStatus: reviewPassed ? 'passed' : 'failed',
        },
      };
    }

    return {
      passed: originalPassed,
      label: originalPassed ? 'Passed' : 'Failed',
      count: `${passedMetrics}/${totalMetrics}`,
      isOverruled: false,
      hasConflict: false,
      automatedPassed: originalPassed, // Same as passed when no review
      hasExecutionError: false,
    };
  };

  // Get failed metrics names
  const getFailedMetrics = (test: TestResultDetail): string[] => {
    const metrics = test.test_metrics?.metrics || {};
    return Object.entries(metrics)
      .filter(([_, metric]) => !metric.is_successful)
      .map(([name]) => name);
  };

  // Paginated tests
  const paginatedTests = useMemo(() => {
    return mergedTests.slice(
      page * rowsPerPage,
      page * rowsPerPage + rowsPerPage
    );
  }, [mergedTests, page, rowsPerPage]);

  // Keyboard navigation
  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Only handle if drawer is not open
      if (drawerOpen || overruleDrawerOpen) return;
      if (paginatedTests.length === 0) return;

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        const newIndex =
          selectedRowIndex === null
            ? 0
            : Math.min(selectedRowIndex + 1, paginatedTests.length - 1);
        setSelectedRowIndex(newIndex);
        setSelectedTest(paginatedTests[newIndex]);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        const newIndex =
          selectedRowIndex === null
            ? paginatedTests.length - 1
            : Math.max(selectedRowIndex - 1, 0);
        setSelectedRowIndex(newIndex);
        setSelectedTest(paginatedTests[newIndex]);
      } else if (event.key === 'Enter') {
        if (selectedRowIndex !== null && paginatedTests[selectedRowIndex]) {
          event.preventDefault();
          setDrawerOpen(true);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [paginatedTests, selectedRowIndex, drawerOpen, overruleDrawerOpen]);

  // Reset selected row when page changes
  React.useEffect(() => {
    setSelectedRowIndex(null);
    setSelectedTest(null);
  }, [page]);

  // Truncate text helper
  const truncateText = (text: string, maxLength: number) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  return (
    <Box>
      <TableContainer
        component={Paper}
        elevation={2}
        sx={{
          maxHeight: 'calc(100vh - 250px)',
          minHeight: 800,
        }}
      >
        <Table stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell
                sx={{
                  backgroundColor: theme.palette.background.paper,
                  fontWeight: 600,
                  width: '22%',
                }}
              >
                {isMultiTurn ? 'Goal' : 'Prompt'}
              </TableCell>
              <TableCell
                sx={{
                  backgroundColor: theme.palette.background.paper,
                  fontWeight: 600,
                  width: '10%',
                  textAlign: 'center',
                }}
              >
                Result
              </TableCell>
              <TableCell
                sx={{
                  backgroundColor: theme.palette.background.paper,
                  fontWeight: 600,
                  width: '30%',
                }}
              >
                {isMultiTurn ? 'Evaluation Reasoning' : 'Response'}
              </TableCell>
              <TableCell
                sx={{
                  backgroundColor: theme.palette.background.paper,
                  fontWeight: 600,
                  width: '13%',
                  textAlign: 'center',
                }}
              >
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 0.5,
                  }}
                >
                  Review
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.25,
                      ml: 0.5,
                    }}
                  >
                    <SmartToyOutlinedIcon
                      fontSize="small"
                      sx={{ fontSize: 16 }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      /
                    </Typography>
                    <PersonOutlineIcon fontSize="small" sx={{ fontSize: 16 }} />
                  </Box>
                </Box>
              </TableCell>
              <TableCell
                sx={{
                  backgroundColor: theme.palette.background.paper,
                  fontWeight: 600,
                  width: '12%',
                  textAlign: 'center',
                }}
              >
                Activity
              </TableCell>
              <TableCell
                sx={{
                  backgroundColor: theme.palette.background.paper,
                  fontWeight: 600,
                  width: '13%',
                  textAlign: 'center',
                }}
              >
                Actions
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 8 }}>
                  <Typography color="text.secondary">
                    Loading tests...
                  </Typography>
                </TableCell>
              </TableRow>
            ) : paginatedTests.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 8 }}>
                  <Typography color="text.secondary">
                    No tests to display
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              paginatedTests.map((test, index) => {
                const status = getTestStatus(test);
                const failedMetrics = getFailedMetrics(test);

                // Get prompt/goal content based on test type
                const promptContent = isMultiTurn
                  ? test.test_output?.test_configuration?.goal || 'N/A'
                  : test.prompt_id && prompts[test.prompt_id]
                    ? prompts[test.prompt_id].content
                    : test.test?.prompt?.content || 'N/A';

                // Get response/evaluation content based on test type
                const responseContent = isMultiTurn
                  ? test.test_output?.goal_evaluation?.reasoning || 'N/A'
                  : test.test_output?.output || 'N/A';

                const isRowSelected = selectedRowIndex === index;

                return (
                  <TableRow
                    key={test.id}
                    hover
                    onClick={() => handleRowClick(test, index)}
                    sx={{
                      cursor: 'pointer',
                      '&:hover': {
                        backgroundColor: alpha(
                          theme.palette.primary.main,
                          0.04
                        ),
                      },
                      ...(isRowSelected && {
                        backgroundColor: alpha(
                          theme.palette.primary.main,
                          0.08
                        ),
                        outline: `2px solid ${theme.palette.primary.main}`,
                        outlineOffset: '-2px',
                      }),
                    }}
                  >
                    {/* Prompt Column */}
                    <TableCell>
                      <Tooltip title={promptContent} enterDelay={500}>
                        <Typography variant="body2">
                          {truncateText(promptContent, 150)}
                        </Typography>
                      </Tooltip>
                    </TableCell>

                    {/* Result Column */}
                    <TableCell align="center">
                      <Chip
                        label={status.label}
                        size="small"
                        sx={{
                          backgroundColor: status.hasExecutionError
                            ? alpha(theme.palette.warning.main, 0.1)
                            : status.passed
                              ? alpha(theme.palette.success.main, 0.1)
                              : alpha(theme.palette.error.main, 0.1),
                          color: status.hasExecutionError
                            ? 'warning.main'
                            : status.passed
                              ? 'success.main'
                              : 'error.main',
                          fontWeight: 600,
                          minWidth: 70,
                        }}
                      />
                    </TableCell>

                    {/* Response Column */}
                    <TableCell>
                      <Tooltip title={responseContent} enterDelay={500}>
                        <Typography variant="body2" color="text.secondary">
                          {truncateText(responseContent, 150)}
                        </Typography>
                      </Tooltip>
                    </TableCell>

                    {/* Review Column */}
                    <TableCell align="center">
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: 1.5,
                        }}
                      >
                        {/* Machine Evaluation Icon */}
                        <Tooltip
                          title={
                            status.hasExecutionError
                              ? 'Execution Error: Test could not be executed'
                              : `Automated: ${
                                  status.automatedPassed ? 'Passed' : 'Failed'
                                } (${status.count})${
                                  failedMetrics.length > 0
                                    ? ` - Failed: ${failedMetrics.join(', ')}`
                                    : ''
                                }`
                          }
                        >
                          <Box sx={{ display: 'flex', alignItems: 'center' }}>
                            {status.hasExecutionError ? (
                              <ErrorOutlineIcon
                                sx={{
                                  fontSize: 20,
                                  color: 'warning.main',
                                }}
                              />
                            ) : status.automatedPassed ? (
                              <CheckIcon
                                sx={{
                                  fontSize: 20,
                                  color: status.hasConflict
                                    ? 'warning.main'
                                    : 'success.main',
                                }}
                              />
                            ) : (
                              <CloseIcon
                                sx={{
                                  fontSize: 20,
                                  color: status.hasConflict
                                    ? 'warning.main'
                                    : 'error.main',
                                }}
                              />
                            )}
                          </Box>
                        </Tooltip>

                        {/* Human Review Icon */}
                        {status.isOverruled ? (
                          <Tooltip
                            title={
                              'reviewData' in status && status.reviewData
                                ? `Human review by ${status.reviewData.reviewer}: ${
                                    status.reviewData.newStatus === 'passed'
                                      ? 'Passed'
                                      : 'Failed'
                                  } - ${status.reviewData.comments}`
                                : 'Manually reviewed'
                            }
                          >
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              {'reviewData' in status &&
                              status.reviewData?.newStatus === 'passed' ? (
                                <CheckIcon
                                  sx={{
                                    fontSize: 20,
                                    color: status.hasConflict
                                      ? 'warning.main'
                                      : 'success.main',
                                  }}
                                />
                              ) : (
                                <CloseIcon
                                  sx={{
                                    fontSize: 20,
                                    color: status.hasConflict
                                      ? 'warning.main'
                                      : 'error.main',
                                  }}
                                />
                              )}
                            </Box>
                          </Tooltip>
                        ) : (
                          <Tooltip title="No manual review yet">
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              <CircleOutlinedIcon
                                sx={{
                                  fontSize: 20,
                                  color: 'action.disabled',
                                  opacity: 0.3,
                                }}
                              />
                            </Box>
                          </Tooltip>
                        )}
                      </Box>
                    </TableCell>

                    {/* Activity Column */}
                    <TableCell align="center">
                      <Box
                        sx={{
                          display: 'flex',
                          gap: 1,
                          justifyContent: 'center',
                          alignItems: 'center',
                        }}
                      >
                        {/* Comments Count */}
                        {test.counts && test.counts.comments > 0 && (
                          <Tooltip
                            title={`${test.counts.comments} comment(s) - Click to view`}
                          >
                            <Box
                              onClick={e => {
                                e.stopPropagation();
                                handleRowClick(test, index, 4); // Tab index 4 is Tasks & Comments
                              }}
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 0.5,
                                cursor: 'pointer',
                                padding: theme.spacing(0.25, 0.5),
                                borderRadius: theme.shape.borderRadius / 8,
                                '&:hover': {
                                  backgroundColor: theme.palette.action.hover,
                                },
                              }}
                            >
                              <CommentOutlinedIcon
                                sx={{ fontSize: 18, color: 'action.active' }}
                              />
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {test.counts.comments}
                              </Typography>
                            </Box>
                          </Tooltip>
                        )}

                        {/* Tasks Count */}
                        {test.counts && test.counts.tasks > 0 && (
                          <Tooltip
                            title={`${test.counts.tasks} task(s) - Click to view`}
                          >
                            <Box
                              onClick={e => {
                                e.stopPropagation();
                                handleRowClick(test, index, 4); // Tab index 4 is Tasks & Comments
                              }}
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 0.5,
                                cursor: 'pointer',
                                padding: theme.spacing(0.25, 0.5),
                                borderRadius: theme.shape.borderRadius / 8,
                                '&:hover': {
                                  backgroundColor: theme.palette.action.hover,
                                },
                              }}
                            >
                              <TaskAltOutlinedIcon
                                sx={{ fontSize: 18, color: 'action.active' }}
                              />
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {test.counts.tasks}
                              </Typography>
                            </Box>
                          </Tooltip>
                        )}

                        {/* Show dash if no activity */}
                        {(!test.counts ||
                          (test.counts.comments === 0 &&
                            test.counts.tasks === 0)) && (
                          <Typography variant="caption" color="text.disabled">
                            —
                          </Typography>
                        )}
                      </Box>
                    </TableCell>

                    {/* Actions Column */}
                    <TableCell align="center">
                      <Box
                        sx={{
                          display: 'flex',
                          gap: 0.5,
                          justifyContent: 'center',
                          alignItems: 'center',
                        }}
                      >
                        {/* Show Confirm Review button only if not already reviewed */}
                        {!test.last_review && (
                          <Tooltip title="Confirm Review">
                            <span>
                              <IconButton
                                size="small"
                                onClick={e => handleConfirmReview(e, test)}
                                disabled={isConfirmingReview}
                                sx={{
                                  '&:hover': {
                                    backgroundColor: alpha(
                                      theme.palette.success.main,
                                      0.1
                                    ),
                                  },
                                  '&:disabled': {
                                    color: 'action.disabled',
                                  },
                                }}
                              >
                                <CheckIcon
                                  sx={{ fontSize: 18, color: 'action.active' }}
                                />
                              </IconButton>
                            </span>
                          </Tooltip>
                        )}

                        <Tooltip title="Provide Review">
                          <IconButton
                            size="small"
                            onClick={e => handleOverruleJudgement(e, test)}
                            sx={{
                              '&:hover': {
                                backgroundColor: alpha(
                                  theme.palette.primary.main,
                                  0.1
                                ),
                              },
                            }}
                          >
                            <RateReviewOutlinedIcon
                              sx={{ fontSize: 18, color: 'action.active' }}
                            />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      <TablePagination
        rowsPerPageOptions={[10, 25, 50, 100]}
        component="div"
        count={mergedTests.length}
        rowsPerPage={rowsPerPage}
        page={page}
        onPageChange={handleChangePage}
        onRowsPerPageChange={handleChangeRowsPerPage}
        sx={{
          borderTop: 1,
          borderColor: 'divider',
          backgroundColor: theme.palette.background.paper,
        }}
      />

      {/* Test Result Drawer */}
      <TestResultDrawer
        open={drawerOpen}
        onClose={handleCloseDrawer}
        test={selectedTest}
        loading={false}
        prompts={prompts}
        behaviors={behaviors}
        testRunId={testRunId}
        sessionToken={sessionToken}
        onTestResultUpdate={handleTestResultUpdateInDrawer}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        currentUserPicture={currentUserPicture}
        initialTab={initialTab}
        testSetType={testSetType}
        project={project}
        projectName={projectName}
      />

      {/* Review Judgement Drawer */}
      <ReviewJudgementDrawer
        open={overruleDrawerOpen}
        onClose={() => setOverruleDrawerOpen(false)}
        test={testToOverrule}
        currentUserName={currentUserName}
        sessionToken={sessionToken}
        onSave={handleOverruleSave}
      />
    </Box>
  );
}
