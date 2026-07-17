'use client';

import React, {
  useState,
  useMemo,
  useRef,
  useCallback,
  useEffect,
} from 'react';
import {
  Box,
  Typography,
  IconButton,
  Tooltip,
  useTheme,
  alpha,
} from '@mui/material';
import {
  GridColDef,
  GridPaginationModel,
  GridRowParams,
} from '@mui/x-data-grid';
import CloseIcon from '@mui/icons-material/Close';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import CommentOutlinedIcon from '@mui/icons-material/CommentOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import CheckIcon from '@mui/icons-material/Check';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import CircleOutlinedIcon from '@mui/icons-material/CircleOutlined';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import GridBadge from '@/components/common/GridBadge';
import {
  TestResultDetail,
  REVIEW_TARGET_TYPES,
} from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import TestResultDrawer, { TEST_RESULT_DRAWER_TAB } from './TestResultDrawer';
import ReviewJudgementDrawer from './ReviewJudgementDrawer';
import { findStatusByCategory } from '@/utils/test-result-status';
import {
  getEvaluationContent,
  getFailedMetricNames,
  getGoalContent,
  getTestResultDisplayStatus,
  truncateText,
} from './test-run-results-grid-utils';
import { resultHasAnyHumanReview } from './test-run-summary-utils';
import { EntityType } from '@/types/entity-type';

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
  /** Drawer tab key when opening via deep-link (e.g. "reviews"). */
  initialDetailTab?: string;
  testSetType?: string;
  project?: { icon?: string; useCase?: string; name?: string };
  projectName?: string;
  metricsSource?: string;
  /** When true, grid renders inside a parent card without its own Paper shell */
  embedded?: boolean;
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
  initialDetailTab,
  testSetType,
  project,
  projectName,
  metricsSource,
  embedded = false,
}: TestsTableViewProps) {
  const isMultiTurn =
    testSetType?.toLowerCase().includes('multi-turn') || false;
  const theme = useTheme();
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });
  const [selectedTest, setSelectedTest] = useState<TestResultDetail | null>(
    null
  );
  const [drawerOpen, setDrawerOpen] = useState(false);
  const resolvedInitialTab =
    initialDetailTab &&
    initialDetailTab in TEST_RESULT_DRAWER_TAB
      ? TEST_RESULT_DRAWER_TAB[
          initialDetailTab as keyof typeof TEST_RESULT_DRAWER_TAB
        ]
      : 0;
  const [initialTab, setInitialTab] = useState<number>(resolvedInitialTab);
  const [overruleDrawerOpen, setOverruleDrawerOpen] = useState(false);
  const [testToOverrule, setTestToOverrule] = useState<TestResultDetail | null>(
    null
  );
  const [hasInitialSelection, setHasInitialSelection] = useState(false);
  const [isConfirmingReview, setIsConfirmingReview] = useState(false);
  const isConfirmingRef = useRef(false);
  const [localTestUpdates, setLocalTestUpdates] = useState<
    Record<string, TestResultDetail>
  >({});

  const mergedTests = useMemo(() => {
    if (Object.keys(localTestUpdates).length === 0) {
      return tests;
    }
    return tests.map(test => localTestUpdates[test.id] || test);
  }, [tests, localTestUpdates]);

  useEffect(() => {
    if (Object.keys(localTestUpdates).length === 0) return;

    const allUpdatesIncluded = Object.keys(localTestUpdates).every(testId => {
      const propTest = tests.find(t => t.id === testId);
      const localTest = localTestUpdates[testId];
      return (
        propTest?.last_review?.review_id === localTest?.last_review?.review_id
      );
    });

    if (allUpdatesIncluded) {
      setLocalTestUpdates({});
    }
  }, [tests, localTestUpdates]);

  useEffect(() => {
    if (
      !initialSelectedTestId ||
      mergedTests.length === 0 ||
      hasInitialSelection
    ) {
      return;
    }

    const testIndex = mergedTests.findIndex(
      t => t.id === initialSelectedTestId
    );
    if (testIndex === -1) return;

    const page = Math.floor(testIndex / paginationModel.pageSize);
    setPaginationModel(prev => ({ ...prev, page }));
    setSelectedTest(mergedTests[testIndex]);
    setInitialTab(resolvedInitialTab);
    setDrawerOpen(true);
    setHasInitialSelection(true);
  }, [
    initialSelectedTestId,
    mergedTests,
    paginationModel.pageSize,
    hasInitialSelection,
    resolvedInitialTab,
  ]);

  useEffect(() => {
    setSelectedTest(prev => {
      if (!prev) return prev;
      const updated = mergedTests.find(t => t.id === prev.id);
      return updated && updated !== prev ? updated : prev;
    });
  }, [mergedTests]);

  useEffect(() => {
    const maxPage = Math.max(
      0,
      Math.ceil(mergedTests.length / paginationModel.pageSize) - 1
    );
    if (paginationModel.page > maxPage) {
      setPaginationModel(prev => ({ ...prev, page: 0 }));
    }
  }, [mergedTests.length, paginationModel.page, paginationModel.pageSize]);

  const handleCloseDrawer = () => {
    setDrawerOpen(false);
  };

  const handleTestResultUpdateInDrawer = (updatedTest: TestResultDetail) => {
    if (selectedTest && selectedTest.id === updatedTest.id) {
      setSelectedTest(updatedTest);
    }
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

  const handleOverruleSave = async (testId: string) => {
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();
      const updatedTest = await testResultsClient.getTestResult(testId);
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
    if (isConfirmingRef.current) return;
    isConfirmingRef.current = true;

    try {
      setIsConfirmingReview(true);

      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();
      const statusClient = clientFactory.getStatusClient();
      const statuses = await statusClient.getStatuses({
        entity_type: EntityType.TEST_RESULT,
      });

      const metrics = test.test_metrics?.metrics || {};
      const metricValues = Object.values(metrics);
      const totalMetrics = metricValues.length;
      let automatedPassed = false;
      if (totalMetrics > 0) {
        const passedMetrics = metricValues.filter(m => m.is_successful).length;
        automatedPassed = passedMetrics === totalMetrics;
      } else if (isMultiTurn && test.test_output?.goal_evaluation) {
        automatedPassed =
          test.test_output.goal_evaluation.all_criteria_met || false;
      }

      const targetStatus = findStatusByCategory(
        statuses,
        automatedPassed ? 'passed' : 'failed'
      );
      if (!targetStatus) return;

      await testResultsClient.createReview(
        test.id,
        targetStatus.id,
        `Confirmed automated ${automatedPassed ? 'pass' : 'fail'} result.`,
        { type: REVIEW_TARGET_TYPES.TEST_RESULT, reference: null }
      );

      let updatedTest: TestResultDetail | null = null;
      const delays = [100, 200, 400, 800];

      for (const delay of delays) {
        await new Promise(resolve => setTimeout(resolve, delay));
        const fetchedTest = await testResultsClient.getTestResult(test.id);
        if (fetchedTest.last_review) {
          updatedTest = fetchedTest;
          break;
        }
      }

      updatedTest = await testResultsClient.getTestResult(test.id);

      setLocalTestUpdates(prev => ({
        ...prev,
        [updatedTest.id]: updatedTest,
      }));

      if (selectedTest && selectedTest.id === test.id) {
        setSelectedTest(updatedTest);
      }

      onTestResultUpdate(updatedTest);
    } catch (error) {
      console.error('Failed to confirm review:', error);
    } finally {
      setIsConfirmingReview(false);
      isConfirmingRef.current = false;
    }
  };

  const openTestDrawer = useCallback((test: TestResultDetail, tabIndex = 0) => {
    setSelectedTest(test);
    setInitialTab(tabIndex);
    setDrawerOpen(true);
  }, []);

  const columns = useMemo<GridColDef<TestResultDetail>[]>(() => {
    const cellTextSx = {
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      display: '-webkit-box',
      WebkitLineClamp: 2,
      WebkitBoxOrient: 'vertical' as const,
    };

    return [
      {
        field: 'goal',
        headerName: isMultiTurn ? 'Goal' : 'Prompt',
        flex: 1,
        minWidth: 240,
        sortable: false,
        disableColumnMenu: true,
        valueGetter: (_, row) => getGoalContent(row, prompts, isMultiTurn),
        renderCell: params => (
          <Tooltip title={String(params.value ?? '')} enterDelay={500}>
            <Typography variant="body2" sx={cellTextSx}>
              {truncateText(String(params.value ?? ''), 150)}
            </Typography>
          </Tooltip>
        ),
      },
      {
        field: 'result',
        headerName: 'Result',
        width: 110,
        sortable: false,
        disableColumnMenu: true,
        align: 'center',
        headerAlign: 'center',
        valueGetter: (_, row) =>
          getTestResultDisplayStatus(row, isMultiTurn).label,
        renderCell: params => {
          const status = getTestResultDisplayStatus(params.row, isMultiTurn);
          return (
            <GridBadge
              label={status.label}
              sx={{
                bgcolor: status.hasExecutionError
                  ? alpha(theme.palette.warning.main, 0.12)
                  : status.passed
                    ? alpha(theme.palette.success.main, 0.12)
                    : alpha(theme.palette.error.main, 0.12),
                color: status.hasExecutionError
                  ? 'warning.dark'
                  : status.passed
                    ? 'success.dark'
                    : 'error.dark',
              }}
            />
          );
        },
      },
      {
        field: 'evaluation',
        headerName: 'Evaluation',
        flex: 1,
        minWidth: 260,
        sortable: false,
        disableColumnMenu: true,
        valueGetter: (_, row) => getEvaluationContent(row),
        renderCell: params => (
          <Tooltip title={String(params.value ?? '')} enterDelay={500}>
            <Typography variant="body2" sx={cellTextSx}>
              {truncateText(String(params.value ?? ''), 150)}
            </Typography>
          </Tooltip>
        ),
      },
      {
        field: 'review',
        headerName: 'Review',
        width: 120,
        sortable: false,
        disableColumnMenu: true,
        align: 'center',
        headerAlign: 'center',
        renderHeader: () => (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 0.5,
              width: '100%',
            }}
          >
            Review
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
              <SmartToyOutlinedIcon sx={{ fontSize: 16 }} />
              <Typography variant="caption" color="text.secondary">
                /
              </Typography>
              <PersonOutlineIcon sx={{ fontSize: 16 }} />
            </Box>
          </Box>
        ),
        renderCell: params => {
          const test = params.row;
          const status = getTestResultDisplayStatus(test, isMultiTurn);
          const failedMetrics = getFailedMetricNames(test);

          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 1.5,
                width: '100%',
              }}
            >
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
                      sx={{ fontSize: 20, color: 'warning.main' }}
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

              {status.isOverruled ? (
                <Tooltip
                  title={
                    status.reviewData
                      ? `Human review by ${status.reviewData.reviewer}: ${
                          status.reviewData.newStatus === 'passed'
                            ? 'Passed'
                            : 'Failed'
                        } - ${status.reviewData.comments}`
                      : 'Manually reviewed'
                  }
                >
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {status.reviewData?.newStatus === 'passed' ? (
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
          );
        },
      },
      {
        field: 'activity',
        headerName: 'Activity',
        width: 100,
        sortable: false,
        disableColumnMenu: true,
        align: 'center',
        headerAlign: 'center',
        renderCell: params => {
          const test = params.row;

          return (
            <Box
              sx={{
                display: 'flex',
                gap: 1,
                justifyContent: 'center',
                alignItems: 'center',
                width: '100%',
              }}
            >
              {test.counts && test.counts.comments > 0 && (
                <Tooltip
                  title={`${test.counts.comments} comment(s) - Click to view`}
                >
                  <Box
                    onClick={e => {
                      e.stopPropagation();
                      openTestDrawer(test, TEST_RESULT_DRAWER_TAB.tasks);
                    }}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      cursor: 'pointer',
                      px: 0.5,
                      borderRadius: 1,
                      '&:hover': { bgcolor: 'action.hover' },
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

              {test.counts && test.counts.tasks > 0 && (
                <Tooltip title={`${test.counts.tasks} task(s) - Click to view`}>
                  <Box
                    onClick={e => {
                      e.stopPropagation();
                      openTestDrawer(test, TEST_RESULT_DRAWER_TAB.tasks);
                    }}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      cursor: 'pointer',
                      px: 0.5,
                      borderRadius: 1,
                      '&:hover': { bgcolor: 'action.hover' },
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

              {(!test.counts ||
                (test.counts.comments === 0 && test.counts.tasks === 0)) && (
                <Typography variant="caption" color="text.disabled">
                  —
                </Typography>
              )}
            </Box>
          );
        },
      },
      {
        field: 'actions',
        headerName: '',
        width: 96,
        sortable: false,
        disableColumnMenu: true,
        align: 'center',
        headerAlign: 'center',
        renderCell: params => {
          const test = params.row;

          return (
            <Box
              className="test-row-actions"
              sx={{
                display: 'flex',
                gap: '10px',
                justifyContent: 'center',
                alignItems: 'center',
                width: '100%',
              }}
            >
              {!resultHasAnyHumanReview(test) && (
                <Tooltip title="Confirm Review">
                  <span>
                    <IconButton
                      size="small"
                      onClick={e => handleConfirmReview(e, test)}
                      disabled={isConfirmingReview}
                      sx={{
                        p: 0.5,
                        color: 'primary.main',
                        '&:hover': {
                          bgcolor: alpha(theme.palette.primary.main, 0.08),
                        },
                      }}
                    >
                      <CheckIcon sx={{ fontSize: 20 }} />
                    </IconButton>
                  </span>
                </Tooltip>
              )}

              <Tooltip title="Provide Review">
                <IconButton
                  size="small"
                  onClick={e => handleOverruleJudgement(e, test)}
                  sx={{
                    p: 0.5,
                    color: 'primary.main',
                    '&:hover': {
                      bgcolor: alpha(theme.palette.primary.main, 0.08),
                    },
                  }}
                >
                  <RateReviewOutlinedIcon sx={{ fontSize: 20 }} />
                </IconButton>
              </Tooltip>
            </Box>
          );
        },
      },
    ];
  }, [isMultiTurn, prompts, theme, isConfirmingReview, openTestDrawer]);

  return (
    <Box sx={{ width: '100%', minWidth: 0 }}>
      <BaseDataGrid
        rows={mergedTests}
        columns={columns}
        loading={loading}
        getRowId={row => row.id}
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        pageSizeOptions={[10, 25, 50, 100]}
        onRowClick={(params: GridRowParams<TestResultDetail>) => {
          openTestDrawer(params.row);
        }}
        disablePaperWrapper={embedded}
        showToolbar={false}
        sx={{
          '& .test-row-actions': {
            opacity: 0,
            pointerEvents: 'none',
            transition: 'opacity 0.15s ease',
          },
          '& .MuiDataGrid-row:hover .test-row-actions': {
            opacity: 1,
            pointerEvents: 'auto',
          },
        }}
      />

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
        metricsSource={metricsSource}
      />

      <ReviewJudgementDrawer
        open={overruleDrawerOpen}
        onClose={() => setOverruleDrawerOpen(false)}
        test={testToOverrule}
        sessionToken={sessionToken}
        onSave={handleOverruleSave}
      />
    </Box>
  );
}
