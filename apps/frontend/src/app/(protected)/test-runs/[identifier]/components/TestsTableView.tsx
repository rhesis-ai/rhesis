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
  Drawer,
  useTheme,
  alpha,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import CloseIcon from '@mui/icons-material/Close';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import CommentOutlinedIcon from '@mui/icons-material/CommentOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import CheckIcon from '@mui/icons-material/Check';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import TestDetailPanel from './TestDetailPanel';
import OverruleJudgementDrawer, {
  OverruleData,
} from './OverruleJudgementDrawer';

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
}: TestsTableViewProps) {
  const theme = useTheme();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [selectedTest, setSelectedTest] = useState<TestResultDetail | null>(
    null
  );
  const [selectedRowIndex, setSelectedRowIndex] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [overruleDrawerOpen, setOverruleDrawerOpen] = useState(false);
  const [testToOverrule, setTestToOverrule] = useState<TestResultDetail | null>(
    null
  );

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleRowClick = (test: TestResultDetail, index: number) => {
    setSelectedTest(test);
    setSelectedRowIndex(index);
    setDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setDrawerOpen(false);
  };

  const handleOverruleJudgement = (
    event: React.MouseEvent,
    test: TestResultDetail
  ) => {
    event.stopPropagation();
    setTestToOverrule(test);
    setOverruleDrawerOpen(true);
  };

  const handleOverruleSave = async (
    testId: string,
    overruleData: OverruleData
  ) => {
    try {
      // Fetch the updated test result from the backend
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();
      const updatedTest = await testResultsClient.getTestResult(testId);

      // Update the test in the parent component
      onTestResultUpdate(updatedTest);

      console.log('Review saved successfully:', { testId, overruleData });
    } catch (error) {
      console.error('Failed to refresh test result:', error);
    }
  };

  const handleConfirmReview = async (
    event: React.MouseEvent,
    test: TestResultDetail
  ) => {
    event.stopPropagation();

    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();
      const statusClient = clientFactory.getStatusClient();

      // Get available statuses for TestResult
      const statuses = await statusClient.getStatuses({
        entity_type: 'TestResult',
      });

      // Determine the current automated status
      const metrics = test.test_metrics?.metrics || {};
      const metricValues = Object.values(metrics);
      const totalMetrics = metricValues.length;
      const passedMetrics = metricValues.filter(m => m.is_successful).length;
      const automatedPassed =
        totalMetrics > 0 && passedMetrics === totalMetrics;

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
        console.error('Could not find appropriate status for confirmation');
        return;
      }

      // Create a review that matches the automated result
      await testResultsClient.createReview(
        test.id,
        targetStatus.id,
        `Confirmed automated ${automatedPassed ? 'pass' : 'fail'} result after manual review.`,
        { type: 'test', reference: null }
      );

      // Refresh the test result
      const updatedTest = await testResultsClient.getTestResult(test.id);
      onTestResultUpdate(updatedTest);

      console.log('Review confirmed successfully for test:', test.id);
    } catch (error) {
      console.error('Failed to confirm review:', error);
    }
  };

  const handleViewDetails = (
    event: React.MouseEvent,
    test: TestResultDetail,
    index: number
  ) => {
    event.stopPropagation();
    handleRowClick(test, index);
  };

  // Calculate test result status (considering reviews from backend)
  const getTestStatus = (test: TestResultDetail) => {
    const metrics = test.test_metrics?.metrics || {};
    const metricValues = Object.values(metrics);
    const totalMetrics = metricValues.length;
    const passedMetrics = metricValues.filter(m => m.is_successful).length;

    if (totalMetrics === 0) {
      return {
        passed: false,
        label: 'N/A',
        count: '0/0',
        isOverruled: false,
        hasConflict: false,
      };
    }

    const originalPassed = passedMetrics === totalMetrics;
    const lastReview = test.last_review;

    // If there's a review, use the review status
    if (lastReview) {
      const reviewStatusName = lastReview.status.name.toLowerCase();
      const reviewPassed =
        reviewStatusName.includes('pass') ||
        reviewStatusName.includes('success') ||
        reviewStatusName.includes('completed');

      return {
        passed: reviewPassed,
        label: reviewPassed ? 'Passed' : 'Failed',
        count: `${passedMetrics}/${totalMetrics}`,
        isOverruled: true,
        hasConflict: !test.matches_review,
        reviewData: {
          reviewer: lastReview.user.name,
          comments: lastReview.comments,
          updated_at: lastReview.updated_at,
        },
      };
    }

    return {
      passed: originalPassed,
      label: originalPassed ? 'Passed' : 'Failed',
      count: `${passedMetrics}/${totalMetrics}`,
      isOverruled: false,
      hasConflict: false,
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
    return tests.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);
  }, [tests, page, rowsPerPage]);

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
                  width: '30%',
                }}
              >
                Prompt
              </TableCell>
              <TableCell
                sx={{
                  backgroundColor: theme.palette.background.paper,
                  fontWeight: 600,
                  width: '30%',
                }}
              >
                Response
              </TableCell>
              <TableCell
                sx={{
                  backgroundColor: theme.palette.background.paper,
                  fontWeight: 600,
                  width: '20%',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  Review
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25, ml: 0.5 }}>
                    <SmartToyOutlinedIcon fontSize="small" sx={{ fontSize: 16 }} />
                    <Typography variant="caption" color="text.secondary">/</Typography>
                    <PersonOutlineIcon fontSize="small" sx={{ fontSize: 16 }} />
                  </Box>
                </Box>
              </TableCell>
              <TableCell
                sx={{
                  backgroundColor: theme.palette.background.paper,
                  fontWeight: 600,
                  width: '10%',
                  textAlign: 'center',
                }}
              >
                Activity
              </TableCell>
              <TableCell
                sx={{
                  backgroundColor: theme.palette.background.paper,
                  fontWeight: 600,
                  width: '10%',
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
                <TableCell colSpan={4} align="center" sx={{ py: 8 }}>
                  <Typography color="text.secondary">
                    Loading tests...
                  </Typography>
                </TableCell>
              </TableRow>
            ) : paginatedTests.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} align="center" sx={{ py: 8 }}>
                  <Typography color="text.secondary">
                    No tests to display
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              paginatedTests.map((test, index) => {
                const status = getTestStatus(test);
                const failedMetrics = getFailedMetrics(test);
                const promptContent =
                  test.prompt_id && prompts[test.prompt_id]
                    ? prompts[test.prompt_id].content
                    : 'N/A';
                const responseContent = test.test_output?.output || 'N/A';
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

                    {/* Response Column */}
                    <TableCell>
                      <Tooltip title={responseContent} enterDelay={500}>
                        <Typography variant="body2" color="text.secondary">
                          {truncateText(responseContent, 150)}
                        </Typography>
                      </Tooltip>
                    </TableCell>

                    {/* Evaluation Column */}
                    <TableCell>
                      <Box
                        sx={{
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 1,
                        }}
                      >
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1,
                            flexWrap: 'wrap',
                          }}
                        >
                          {status.passed ? (
                            <CheckCircleOutlineIcon
                              sx={{
                                fontSize: 20,
                                color: 'success.main',
                              }}
                            />
                          ) : (
                            <CancelOutlinedIcon
                              sx={{
                                fontSize: 20,
                                color: 'error.main',
                              }}
                            />
                          )}
                          <Chip
                            label={status.label}
                            size="small"
                            color={status.passed ? 'success' : 'error'}
                            variant="outlined"
                          />
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ ml: 0.5 }}
                          >
                            {status.count}
                          </Typography>
                        </Box>

                        {status.isOverruled && (
                          <Tooltip
                            title={
                              status.reviewData
                                ? `Reviewed by ${status.reviewData.reviewer} - ${status.reviewData.comments}`
                                : 'Manually reviewed'
                            }
                          >
                            <Chip
                              icon={<RateReviewOutlinedIcon sx={{ fontSize: 14 }} />}
                              label="Reviewed"
                              size="small"
                              color={status.hasConflict ? 'warning' : 'info'}
                              variant="outlined"
                              sx={{
                                height: 20,
                                fontWeight: 600,
                              }}
                            />
                          </Tooltip>
                        )}

                        {status.hasConflict && (
                          <Tooltip title="Status mismatch: Review status differs from automated test result">
                            <Chip
                              icon={<WarningAmberIcon sx={{ fontSize: 14 }} />}
                              label="Conflict"
                              size="small"
                              color="warning"
                              variant="outlined"
                              sx={{
                                height: 20,
                                fontWeight: 600,
                                borderWidth: 1.5,
                              }}
                            />
                          </Tooltip>
                        )}

                        {failedMetrics.length > 0 && !status.isOverruled && (
                          <Box>
                            <Typography
                              variant="caption"
                              color="error.main"
                              sx={{
                                display: 'block',
                              }}
                            >
                              Failed: {failedMetrics.slice(0, 2).join(', ')}
                              {failedMetrics.length > 2 &&
                                ` +${failedMetrics.length - 2}`}
                            </Typography>
                          </Box>
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
                          <Tooltip title={`${test.counts.comments} comment(s)`}>
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 0.5,
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
                          <Tooltip title={`${test.counts.tasks} task(s)`}>
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 0.5,
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
                        <Tooltip title="View Details">
                          <IconButton
                            size="small"
                            onClick={e => handleViewDetails(e, test, index)}
                            sx={{
                              '&:hover': {
                                backgroundColor: alpha(
                                  theme.palette.primary.main,
                                  0.1
                                ),
                              },
                            }}
                          >
                            <VisibilityOutlinedIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>

                        {/* Show Confirm Review button only if not already reviewed */}
                        {!test.last_review && (
                          <Tooltip title="Confirm Review">
                            <IconButton
                              size="small"
                              onClick={e => handleConfirmReview(e, test)}
                              sx={{
                                '&:hover': {
                                  backgroundColor: alpha(
                                    theme.palette.success.main,
                                    0.1
                                  ),
                                },
                              }}
                            >
                              <CheckIcon fontSize="small" />
                            </IconButton>
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
                            <RateReviewOutlinedIcon fontSize="small" />
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
        count={tests.length}
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

      {/* Detail Drawer */}
      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={handleCloseDrawer}
        sx={{
          zIndex: theme => theme.zIndex.drawer + 1,
          '& .MuiDrawer-paper': {
            width: { xs: '100%', sm: '80%', md: '60%', lg: '50%' },
            maxWidth: '50vw',
            zIndex: theme => theme.zIndex.drawer + 1,
          },
        }}
      >
        <Box
          sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Drawer Header */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              p: 2,
              borderBottom: 1,
              borderColor: 'divider',
              backgroundColor: theme.palette.background.paper,
            }}
          >
            <Typography variant="h6">Test Details</Typography>
            <IconButton onClick={handleCloseDrawer} size="small">
              <CloseIcon />
            </IconButton>
          </Box>

          {/* Drawer Content */}
          <Box sx={{ flex: 1, overflow: 'hidden' }}>
            {selectedTest && (
              <TestDetailPanel
                test={selectedTest}
                loading={false}
                prompts={prompts}
                behaviors={behaviors}
                testRunId={testRunId}
                sessionToken={sessionToken}
                onTestResultUpdate={onTestResultUpdate}
                currentUserId={currentUserId}
                currentUserName={currentUserName}
                currentUserPicture={currentUserPicture}
              />
            )}
          </Box>
        </Box>
      </Drawer>

      {/* Overrule Judgement Drawer */}
      <OverruleJudgementDrawer
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
