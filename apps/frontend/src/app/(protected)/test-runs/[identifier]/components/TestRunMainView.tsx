'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { Box, Grid, Paper, useTheme } from '@mui/material';
import TestRunFilterBar, { FilterState } from './TestRunFilterBar';
import TestsList from './TestsList';
import TestDetailPanel from './TestDetailPanel';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

interface TestRunMainViewProps {
  testRunId: string;
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

  // Auto-select first test if none selected and tests are available
  React.useEffect(() => {
    if (!selectedTestId && filteredTests.length > 0) {
      setSelectedTestId(filteredTests[0].id);
    }
  }, [selectedTestId, filteredTests]);

  return (
    <Box>
      {/* Filter Bar */}
      <TestRunFilterBar
        filter={filter}
        onFilterChange={handleFilterChange}
        availableBehaviors={behaviors}
        onDownload={handleDownload}
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
    </Box>
  );
}
