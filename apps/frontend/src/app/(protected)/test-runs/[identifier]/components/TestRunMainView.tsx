'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { Box, Grid, Paper, useTheme } from '@mui/material';
import TestRunFilterBar, { FilterState } from './TestRunFilterBar';
import TestsList from './TestsList';
import TestDetailPanel from './TestDetailPanel';
import ComparisonView from './ComparisonView';
import TestRunHeader from './TestRunHeader';
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
}: TestRunMainViewProps) {
  const theme = useTheme();
  const notifications = useNotifications();
  const [selectedTestId, setSelectedTestId] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isComparisonMode, setIsComparisonMode] = useState(false);
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
    } catch (error) {
      console.error('Error downloading test run:', error);
      notifications.show('Failed to download test run results', {
        severity: 'error',
      });
    } finally {
      setIsDownloading(false);
    }
  }, [testRunId, sessionToken, notifications]);

  // Fetch available test runs for comparison
  React.useEffect(() => {
    const fetchTestRuns = async () => {
      try {
        const testRunsClient = new ApiClientFactory(
          sessionToken
        ).getTestRunsClient();

        const params: any = {
          limit: 50,
          skip: 0,
          sort_by: 'created_at',
          sort_order: 'desc',
        };

        // Only add test_configuration_id filter if it exists
        if (testRunData.test_configuration_id) {
          params.test_configuration_id = testRunData.test_configuration_id;
        }

        const response = await testRunsClient.getTestRuns(params);

        // Filter out current test run
        const runs = response.data
          .filter(run => run.id !== testRunId)
          .map(run => ({
            id: run.id,
            name: run.name,
            created_at: run.attributes?.started_at || run.created_at || '',
            pass_rate: undefined, // Will be calculated from test results if needed
          }));

        setAvailableTestRuns(runs);
      } catch (error) {
        console.error('Error fetching test runs:', error);
      }
    };

    fetchTestRuns();
  }, [testRunId, sessionToken, testRunData.test_configuration_id ?? '']);

  // Handle compare
  const handleCompare = useCallback(() => {
    if (availableTestRuns.length === 0) {
      notifications.show('No other test runs available for comparison', {
        severity: 'info',
      });
      return;
    }
    setIsComparisonMode(true);
  }, [availableTestRuns, notifications]);

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
      } catch (error) {
        console.error('Error loading baseline test results:', error);
        notifications.show('Failed to load baseline test results', {
          severity: 'error',
        });
        return [];
      }
    },
    [sessionToken, notifications]
  );

  // Auto-select first test if none selected and tests are available
  React.useEffect(() => {
    if (!selectedTestId && filteredTests.length > 0) {
      setSelectedTestId(filteredTests[0].id);
    }
  }, [selectedTestId, filteredTests]);

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
            onDownload={handleDownload}
            onCompare={handleCompare}
            isDownloading={isDownloading}
            totalTests={testResults.length}
            filteredTests={filteredTests.length}
          />

          {/* Split Panel Layout */}
          <Grid container spacing={3}>
            {/* Left: Tests List (33%) */}
            <Grid item xs={12} md={4}>
              <Paper
                sx={{
                  height: { xs: 400, md: 'calc(100vh - 420px)' },
                  minHeight: 400,
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                }}
              >
                <TestsList
                  tests={filteredTests}
                  selectedTestId={selectedTestId}
                  onTestSelect={handleTestSelect}
                  loading={loading}
                  prompts={prompts}
                />
              </Paper>
            </Grid>

            {/* Right: Test Detail Panel (67%) */}
            <Grid item xs={12} md={8}>
              <Paper
                sx={{
                  height: { xs: 600, md: 'calc(100vh - 420px)' },
                  minHeight: 600,
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
                />
              </Paper>
            </Grid>
          </Grid>
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
        />
      )}
    </Box>
  );
}
