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
import GavelIcon from '@mui/icons-material/Gavel';
import VisibilityIcon from '@mui/icons-material/Visibility';
import CommentOutlinedIcon from '@mui/icons-material/CommentOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
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
  const [overruledTests, setOverruledTests] = useState<
    Map<string, OverruleData>
  >(new Map());

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

  const handleOverruleSave = (testId: string, overruleData: OverruleData) => {
    // Mock implementation - store overrule data in local state
    setOverruledTests(prev => {
      const newMap = new Map(prev);
      newMap.set(testId, overruleData);
      return newMap;
    });

    console.log('Mock overrule saved:', { testId, overruleData });
    // TODO: Replace with actual API call when backend is ready
    // await apiClient.overruleTestJudgement(testId, overruleData);
  };

  const handleViewDetails = (event: React.MouseEvent, test: TestResultDetail, index: number) => {
    event.stopPropagation();
    handleRowClick(test, index);
  };

  // Calculate test result status (considering overrules)
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
      };
    }

    const originalPassed = passedMetrics === totalMetrics;
    const overruleData = overruledTests.get(test.id);

    // If overruled, use the overruled status
    if (overruleData) {
      return {
        passed: overruleData.newStatus === 'passed',
        label:
          overruleData.newStatus === 'passed' ? 'Passed' : 'Failed',
        count: `${passedMetrics}/${totalMetrics}`,
        isOverruled: true,
        overruleData,
      };
    }

    return {
      passed: originalPassed,
      label: originalPassed ? 'Passed' : 'Failed',
      count: `${passedMetrics}/${totalMetrics}`,
      isOverruled: false,
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
        const newIndex = selectedRowIndex === null 
          ? 0 
          : Math.min(selectedRowIndex + 1, paginatedTests.length - 1);
        setSelectedRowIndex(newIndex);
        setSelectedTest(paginatedTests[newIndex]);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        const newIndex = selectedRowIndex === null 
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
                Evaluation
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
                  <Typography color="text.secondary">Loading tests...</Typography>
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
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
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
                            title={`Overruled by ${status.overruleData?.overruledBy} - ${status.overruleData?.reason}`}
                          >
                            <Chip
                              icon={<GavelIcon sx={{ fontSize: 14 }} />}
                              label="Overruled"
                              size="small"
                              color="warning"
                              variant="filled"
                              sx={{
                                height: 20,
                                fontWeight: 600,
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
                              <Typography variant="caption" color="text.secondary">
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
                              <Typography variant="caption" color="text.secondary">
                                {test.counts.tasks}
                              </Typography>
                            </Box>
                          </Tooltip>
                        )}

                        {/* Show dash if no activity */}
                        {(!test.counts ||
                          (test.counts.comments === 0 && test.counts.tasks === 0)) && (
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
                            <VisibilityIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        
                        <Tooltip title="Overrule Judgement">
                          <IconButton
                            size="small"
                            onClick={e => handleOverruleJudgement(e, test)}
                            sx={{
                              '&:hover': {
                                backgroundColor: alpha(
                                  theme.palette.warning.main,
                                  0.1
                                ),
                              },
                            }}
                          >
                            <GavelIcon fontSize="small" />
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
        onSave={handleOverruleSave}
      />
    </Box>
  );
}

