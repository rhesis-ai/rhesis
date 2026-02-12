'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { Box, Paper, useTheme, TablePagination } from '@mui/material';
import { useRouter } from 'next/navigation';
import TestRunFilterBar, { FilterState } from './TestRunFilterBar';
import TestsList from './TestsList';
import TestDetailPanel from './TestDetailPanel';
import TestsTableView from './TestsTableView';
import ComparisonView from './ComparisonView';
import TestRunHeader from './TestRunHeader';
import TestRunTags from './TestRunTags';
import RerunTestRunDrawer from './RerunTestRunDrawer';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

interface TestRunMainViewProps {
  testRunId: string;
  testRunData: {
    id: string;
    name?: string;
    created_at: string;
    test_configuration_id?: string;
  };
  testRun: TestRunDetail;
  sessionToken: string;
  testResults: TestResultDetail[];
  prompts: Record<string, { content: string; name?: string }>;
  behaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }>;
  loading?: boolean;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
  initialSelectedTestId?: string;
}

export default function TestRunMainView({
  testRunId,
  testRunData,
  testRun,
  sessionToken,
  testResults: initialTestResults,
  prompts,
  behaviors,
  loading = false,
  currentUserId,
  currentUserName,
  currentUserPicture,
  initialSelectedTestId,
}: TestRunMainViewProps) {
  const theme = useTheme();
  const notifications = useNotifications();
  const router = useRouter();
  const [selectedTestId, setSelectedTestId] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isRerunDrawerOpen, setIsRerunDrawerOpen] = useState(false);
  const [isComparisonMode, setIsComparisonMode] = useState(false);
  const [viewMode, setViewMode] = useState<'split' | 'table'>('split');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [hasInitialSelection, setHasInitialSelection] = useState(false);
  const [availableTestRuns, setAvailableTestRuns] = useState<
    Array<{
      id: string;
      name?: string;
      created_at: string;
      pass_rate?: number;
    }>
  >([]);

  // Track only updates to test results (not all test results)
  const [testResultUpdates, setTestResultUpdates] = useState<
    Map<string, TestResultDetail>
  >(new Map());

  // Filter state
  const [filter, setFilter] = useState<FilterState>({
    searchQuery: '',
    statusFilter: 'all',
    selectedBehaviors: [],
    overruleFilter: 'all',
    selectedFailedMetrics: [],
    commentFilter: 'all',
    commentCountRange: { min: 0, max: 20 },
    taskFilter: 'all',
    taskCountRange: { min: 0, max: 10 },
  });

  // Merge prop data with any updates
  const testResults = useMemo(() => {
    if (testResultUpdates.size === 0) {
      return initialTestResults;
    }
    return initialTestResults.map(
      test => testResultUpdates.get(test.id) || test
    );
  }, [initialTestResults, testResultUpdates]);

  // Get selected test
  const selectedTest = useMemo(() => {
    return testResults.find(t => t.id === selectedTestId) || null;
  }, [testResults, selectedTestId]);

  // Filter tests based on current filter state
  const filteredTests = useMemo(() => {
    let filtered = [...testResults];

    // Apply search filter
    if (filter.searchQuery) {
      const query = filter.searchQuery.toLowerCase();
      filtered = filtered.filter(test => {
        const promptContent =
          test.prompt_id && prompts[test.prompt_id]
            ? prompts[test.prompt_id].content.toLowerCase()
            : '';
        const responseContent = test.test_output?.output?.toLowerCase() || '';
        return promptContent.includes(query) || responseContent.includes(query);
      });
    }

    // Apply status filter
    if (filter.statusFilter !== 'all') {
      filtered = filtered.filter(test => {
        const metrics = test.test_metrics?.metrics || {};
        const metricValues = Object.values(metrics);
        const totalMetrics = metricValues.length;
        const passedMetrics = metricValues.filter(m => m.is_successful).length;
        const isPassed = totalMetrics > 0 && passedMetrics === totalMetrics;

        return filter.statusFilter === 'passed' ? isPassed : !isPassed;
      });
    }

    // Apply behavior filter
    if (filter.selectedBehaviors.length > 0) {
      filtered = filtered.filter(test => {
        const metrics = test.test_metrics?.metrics || {};

        // Check if test has at least one metric from selected behaviors
        return filter.selectedBehaviors.some(behaviorId => {
          const behavior = behaviors.find(b => b.id === behaviorId);
          if (!behavior) return false;

          return behavior.metrics.some(metric => metrics[metric.name]);
        });
      });
    }

    // Apply review status filter
    if (filter.overruleFilter !== 'all') {
      filtered = filtered.filter(test => {
        const hasReview = !!test.last_review;
        const hasConflict = !test.matches_review;

        if (filter.overruleFilter === 'overruled') {
          return hasReview;
        } else if (filter.overruleFilter === 'original') {
          return !hasReview;
        } else if (filter.overruleFilter === 'conflicting') {
          return hasReview && hasConflict;
        }
        return true;
      });
    }

    // Apply comment filter
    if (filter.commentFilter !== 'all') {
      filtered = filtered.filter(test => {
        const commentCount = test.counts?.comments || 0;

        if (filter.commentFilter === 'with_comments') {
          return commentCount > 0;
        } else if (filter.commentFilter === 'without_comments') {
          return commentCount === 0;
        } else if (filter.commentFilter === 'range') {
          return (
            commentCount >= filter.commentCountRange.min &&
            commentCount <= filter.commentCountRange.max
          );
        }
        return true;
      });
    }

    // Apply task filter
    if (filter.taskFilter !== 'all') {
      filtered = filtered.filter(test => {
        const taskCount = test.counts?.tasks || 0;

        if (filter.taskFilter === 'with_tasks') {
          return taskCount > 0;
        } else if (filter.taskFilter === 'without_tasks') {
          return taskCount === 0;
        } else if (filter.taskFilter === 'range') {
          return (
            taskCount >= filter.taskCountRange.min &&
            taskCount <= filter.taskCountRange.max
          );
        }
        return true;
      });
    }

    return filtered;
  }, [testResults, filter, prompts, behaviors]);

  // Handle test selection
  const handleTestSelect = useCallback((testId: string) => {
    setSelectedTestId(testId);
  }, []);

  // Handle filter changes
  const handleFilterChange = useCallback(
    (newFilter: FilterState) => {
      setFilter(newFilter);
      // If current selected test is not in filtered list, clear selection
      const testStillVisible = testResults.some(t => t.id === selectedTestId);
      if (!testStillVisible) {
        setSelectedTestId(null);
      }
    },
    [testResults, selectedTestId]
  );

  // Handle test result updates (e.g., when tags change)
  const handleTestResultUpdate = useCallback(
    (updatedTest: TestResultDetail) => {
      setTestResultUpdates(prev => {
        const newMap = new Map(prev);
        newMap.set(updatedTest.id, updatedTest);
        return newMap;
      });
    },
    []
  );

  // Handle pagination
  const handleChangePage = useCallback((_event: unknown, newPage: number) => {
    setPage(newPage);
  }, []);

  const handleChangeRowsPerPage = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setRowsPerPage(parseInt(event.target.value, 10));
      setPage(0);
    },
    []
  );

  // Paginated tests for split view
  const paginatedTests = useMemo(() => {
    return filteredTests.slice(
      page * rowsPerPage,
      page * rowsPerPage + rowsPerPage
    );
  }, [filteredTests, page, rowsPerPage]);

  // Handle download
  const handleDownload = useCallback(async () => {
    setIsDownloading(true);
    try {
      const testRunsClient = new ApiClientFactory(
        sessionToken
      ).getTestRunsClient();
      const blob = await testRunsClient.downloadTestRun(testRunId);

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `test_run_${testRunId}_results.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      notifications.show('Test run results downloaded successfully', {
        severity: 'success',
      });
    } catch (_error) {
      notifications.show('Failed to download test run results', {
        severity: 'error',
      });
    } finally {
      setIsDownloading(false);
    }
  }, [testRunId, sessionToken, notifications]);

  // Handle re-run button click - opens the rerun drawer
  const handleRerun = useCallback(() => {
    if (!testRun.test_configuration_id) {
      notifications.show('Cannot re-run: No test configuration found', {
        severity: 'error',
      });
      return;
    }

    // Check if we have the required data for re-run
    const testSet = testRun.test_configuration?.test_set;
    const endpoint = testRun.test_configuration?.endpoint;

    if (!testSet?.id || !endpoint?.id) {
      notifications.show('Cannot re-run: Missing test set or endpoint data', {
        severity: 'error',
      });
      return;
    }

    setIsRerunDrawerOpen(true);
  }, [
    testRun.test_configuration_id,
    testRun.test_configuration,
    notifications,
  ]);

  // Handle rerun drawer success
  const handleRerunSuccess = useCallback(() => {
    // Navigate to the test runs page to see the new test run
    router.push('/test-runs');
  }, [router]);

  // Fetch available test runs for comparison (lazy-loaded when compare is clicked)
  const fetchTestRuns = useCallback(async () => {
    try {
      // Get test_set_id from the nested test_set object
      const testSetId = testRun.test_configuration?.test_set?.id;

      if (!testSetId) {
        setAvailableTestRuns([]);
        return [];
      }

      const testRunsClient = new ApiClientFactory(
        sessionToken
      ).getTestRunsClient();

      // Use OData filter to get all test runs for the same test set
      const params: any = {
        limit: 50,
        skip: 0,
        sort_by: 'created_at',
        sort_order: 'desc',
        filter: `test_configuration/test_set/id eq '${testSetId}'`,
      };

      const response = await testRunsClient.getTestRuns(params);

      // Filter out current test run
      const runs = response.data
        .filter(run => run.id !== testRunId)
        .map(run => ({
          id: run.id,
          name: run.name,
          created_at:
            (typeof run.attributes?.started_at === 'string'
              ? run.attributes.started_at
              : null) ||
            (typeof run.created_at === 'string' ? run.created_at : '') ||
            '',
          pass_rate: undefined, // Will be calculated from test results if needed
        }));

      setAvailableTestRuns(runs);
      return runs;
    } catch (_error) {
      setAvailableTestRuns([]);
      return [];
    }
  }, [testRunId, sessionToken, testRun.test_configuration?.test_set?.id]);

  // Handle compare
  const handleCompare = useCallback(async () => {
    // Fetch test runs only when compare is clicked
    const runs = await fetchTestRuns();

    if (runs.length === 0) {
      notifications.show('No other test runs available for comparison', {
        severity: 'info',
      });
      return;
    }
    setIsComparisonMode(true);
  }, [fetchTestRuns, notifications]);

  // Handle load baseline test results
  const handleLoadBaseline = useCallback(
    async (baselineTestRunId: string): Promise<TestResultDetail[]> => {
      try {
        const testResultsClient = new ApiClientFactory(
          sessionToken
        ).getTestResultsClient();

        // Fetch all test results for baseline test run
        let testResults: TestResultDetail[] = [];
        let skip = 0;
        const batchSize = 100;
        let hasMore = true;

        while (hasMore) {
          const testResultsResponse = await testResultsClient.getTestResults({
            filter: `test_run_id eq '${baselineTestRunId}'`,
            limit: batchSize,
            skip: skip,
            sort_by: 'created_at',
            sort_order: 'desc',
          });

          testResults = [...testResults, ...testResultsResponse.data];

          const totalCount = testResultsResponse.pagination?.totalCount || 0;
          hasMore = testResults.length < totalCount;
          skip += batchSize;

          if (skip > 10000) break;
        }

        return testResults;
      } catch (_error) {
        notifications.show('Failed to load baseline test results', {
          severity: 'error',
        });
        return [];
      }
    },
    [sessionToken, notifications]
  );

  // Handle initial selection and pagination when initialSelectedTestId is provided
  React.useEffect(() => {
    if (
      initialSelectedTestId &&
      filteredTests.length > 0 &&
      !hasInitialSelection
    ) {
      // First try to match by test result ID (direct match)
      let testIndex = filteredTests.findIndex(
        t => t.id === initialSelectedTestId
      );

      // If not found, try to match by test_id (for cross-run navigation)
      if (testIndex === -1) {
        testIndex = filteredTests.findIndex(
          t => t.test_id === initialSelectedTestId
        );
        if (testIndex !== -1) {
        }
      }

      if (testIndex !== -1) {
        // Calculate which page the test is on
        const testPage = Math.floor(testIndex / rowsPerPage);
        setPage(testPage);
        setSelectedTestId(filteredTests[testIndex].id);
        setHasInitialSelection(true);
      } else {
      }
    }
  }, [initialSelectedTestId, filteredTests, rowsPerPage, hasInitialSelection]);

  // Auto-select first test if none selected and tests are available
  // But DON'T auto-select if we have an initialSelectedTestId that hasn't loaded yet
  React.useEffect(() => {
    // Skip auto-selection if we're waiting for initial selection
    if (initialSelectedTestId && !hasInitialSelection) {
      return;
    }

    if (!selectedTestId && filteredTests.length > 0) {
      setSelectedTestId(filteredTests[0].id);
    } else if (
      selectedTestId &&
      !filteredTests.some(t => t.id === selectedTestId)
    ) {
      // If selected test is not in filtered list, select first available or clear selection
      if (filteredTests.length > 0) {
        setSelectedTestId(filteredTests[0].id);
      } else {
        setSelectedTestId(null);
      }
    }
  }, [
    selectedTestId,
    filteredTests,
    initialSelectedTestId,
    hasInitialSelection,
  ]);

  return (
    <Box>
      {/* Header with Summary Cards - only show when not in comparison mode */}
      {!isComparisonMode && (
        <TestRunHeader
          testRun={testRun}
          testResults={testResults}
          loading={loading}
        />
      )}

      {!isComparisonMode ? (
        <>
          {/* Filter Bar */}
          <TestRunFilterBar
            filter={filter}
            onFilterChange={handleFilterChange}
            availableBehaviors={behaviors}
            availableMetrics={behaviors?.flatMap(b => b.metrics) || []}
            onDownload={handleDownload}
            onCompare={handleCompare}
            isDownloading={isDownloading}
            totalTests={testResults.length}
            filteredTests={filteredTests.length}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            onRerun={handleRerun}
            isRerunning={isRerunDrawerOpen}
            canRerun={!!testRun.test_configuration_id}
          />

          {/* Conditional Layout based on viewMode */}
          {viewMode === 'split' ? (
            <Paper
              elevation={2}
              sx={{
                height: { xs: 900, md: 'calc(100vh - 240px)' },
                minHeight: 900,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }}
            >
              {/* Content Area with Split View */}
              <Box
                sx={{
                  flex: 1,
                  display: 'flex',
                  overflow: 'hidden',
                }}
              >
                {/* Left: Tests List (33%) */}
                <Box
                  sx={{
                    width: { xs: '100%', md: '33.33%' },
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                  }}
                >
                  <TestsList
                    tests={paginatedTests}
                    selectedTestId={selectedTestId}
                    onTestSelect={handleTestSelect}
                    loading={loading}
                    prompts={prompts}
                    testSetType={
                      testRun.test_configuration?.test_set?.test_set_type
                        ?.type_value
                    }
                  />
                </Box>

                {/* Right: Test Detail Panel (67%) */}
                <Box
                  sx={{
                    width: { xs: '100%', md: '66.67%' },
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                  }}
                >
                  <TestDetailPanel
                    test={selectedTest}
                    loading={loading}
                    prompts={prompts}
                    behaviors={behaviors}
                    testRunId={testRunId}
                    sessionToken={sessionToken}
                    onTestResultUpdate={handleTestResultUpdate}
                    currentUserId={currentUserId}
                    currentUserName={currentUserName}
                    currentUserPicture={currentUserPicture}
                    testSetType={
                      testRun.test_configuration?.test_set?.test_set_type
                        ?.type_value
                    }
                    project={testRun.test_configuration?.endpoint?.project}
                    projectName={
                      testRun.test_configuration?.endpoint?.project?.name
                    }
                    metricsSource={
                      testRun.test_configuration?.attributes?.metrics_source
                    }
                  />
                </Box>
              </Box>

              {/* Shared Pagination at Bottom */}
              <TablePagination
                rowsPerPageOptions={[10, 25, 50, 100]}
                component="div"
                count={filteredTests.length}
                rowsPerPage={rowsPerPage}
                page={page}
                onPageChange={handleChangePage}
                onRowsPerPageChange={handleChangeRowsPerPage}
                sx={{
                  borderTop: 1,
                  borderColor: 'divider',
                  backgroundColor: theme.palette.background.paper,
                  flexShrink: 0,
                }}
              />
            </Paper>
          ) : (
            <TestsTableView
              tests={filteredTests}
              prompts={prompts}
              behaviors={behaviors}
              testRunId={testRunId}
              sessionToken={sessionToken}
              loading={loading}
              onTestResultUpdate={handleTestResultUpdate}
              currentUserId={currentUserId}
              currentUserName={currentUserName}
              currentUserPicture={currentUserPicture}
              initialSelectedTestId={initialSelectedTestId}
              testSetType={
                testRun.test_configuration?.test_set?.test_set_type?.type_value
              }
              project={testRun.test_configuration?.endpoint?.project}
              projectName={testRun.test_configuration?.endpoint?.project?.name}
              metricsSource={
                testRun.test_configuration?.attributes?.metrics_source
              }
            />
          )}

          {/* Test Run Tags - moved to bottom */}
          <Paper elevation={2} sx={{ mt: 3, p: 2 }}>
            <TestRunTags sessionToken={sessionToken} testRun={testRun} />
          </Paper>
        </>
      ) : (
        <ComparisonView
          currentTestRun={testRunData}
          currentTestResults={testResults}
          availableTestRuns={availableTestRuns}
          onClose={() => setIsComparisonMode(false)}
          onLoadBaseline={handleLoadBaseline}
          prompts={prompts}
          behaviors={behaviors}
          testSetType={
            testRun.test_configuration?.test_set?.test_set_type?.type_value
          }
          project={testRun.test_configuration?.endpoint?.project}
          projectName={testRun.test_configuration?.endpoint?.project?.name}
        />
      )}

      {/* Re-run Test Run Drawer */}
      <RerunTestRunDrawer
        open={isRerunDrawerOpen}
        onClose={() => setIsRerunDrawerOpen(false)}
        rerunConfig={{
          testSetId: testRun.test_configuration?.test_set?.id || '',
          testSetName: testRun.test_configuration?.test_set?.name || 'Unknown',
          testSetType:
            testRun.test_configuration?.test_set?.test_set_type?.type_value,
          endpointId: testRun.test_configuration?.endpoint?.id || '',
          endpointName: testRun.test_configuration?.endpoint?.name || 'Unknown',
          projectName:
            testRun.test_configuration?.endpoint?.project?.name || 'Unknown',
          testRunId: testRun.id,
          originalAttributes: testRun.test_configuration?.attributes,
        }}
        sessionToken={sessionToken}
        onSuccess={handleRerunSuccess}
      />
    </Box>
  );
}
