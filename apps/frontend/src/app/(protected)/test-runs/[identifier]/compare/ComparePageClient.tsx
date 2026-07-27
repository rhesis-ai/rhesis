'use client';

import React, { useCallback, useState } from 'react';
import { Box, Button, Typography } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useRouter } from 'next/navigation';
import ComparisonView from '../components/ComparisonView';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';

interface ComparePageClientProps {
  currentTestRun: {
    id: string;
    name?: string;
    created_at: string;
    experiment_id?: string;
    parameter_version?: string;
    experiment_name?: string;
  };
  currentTestResults: TestResultDetail[];
  availableTestRuns: Array<{
    id: string;
    name?: string;
    created_at: string;
    pass_rate?: number;
    experiment_id?: string;
    parameter_version?: string;
    experiment_name?: string;
  }>;
  prompts: Record<string, { content: string; name?: string }>;
  behaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }>;
  initialBaselineId?: string;
  testSetType?: string;
  project?: { icon?: string; useCase?: string; name?: string };
  projectName?: string;
}

export default function ComparePageClient({
  currentTestRun,
  currentTestResults,
  availableTestRuns,
  prompts,
  behaviors,
  initialBaselineId,
  testSetType,
  project,
  projectName,
}: ComparePageClientProps) {
  const router = useRouter();
  const notifications = useNotifications();
  // Always default to a baseline run so the comparison view (with its own
  // baseline selector) renders directly. There is no intermediate "select a
  // baseline" screen — the design (Figma node 1645:25316) goes straight to the
  // comparison layout.
  const [selectedBaselineId] = useState<string | undefined>(
    initialBaselineId && availableTestRuns.some(r => r.id === initialBaselineId)
      ? initialBaselineId
      : availableTestRuns[0]?.id
  );

  const handleClose = useCallback(() => {
    // The comparison view opens in its own tab, so closing it is the expected
    // behaviour. window.close() works for script-opened tabs even when
    // window.opener is null (the tab is opened with `noopener`). If the tab
    // can't be closed programmatically, fall back to navigating back.
    window.close();
    setTimeout(() => {
      router.push(`/test-runs/${currentTestRun.id}`);
    }, 100);
  }, [router, currentTestRun.id]);

  const handleLoadBaseline = useCallback(
    async (baselineTestRunId: string): Promise<TestResultDetail[]> => {
      try {
        const testResultsClient = new ApiClientFactory().getTestResultsClient();
        let testResults: TestResultDetail[] = [];
        let skip = 0;
        const batchSize = 100;
        let hasMore = true;

        while (hasMore) {
          const testResultsResponse = await testResultsClient.getTestResults({
            filter: `test_run_id eq '${baselineTestRunId}'`,
            limit: batchSize,
            skip,
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
      } catch {
        notifications.show('Failed to load baseline test results', {
          severity: 'error',
        });
        return [];
      }
    },
    [notifications]
  );

  // No baseline available to compare against. This should not normally be
  // reachable because the "Compare" action is disabled when no comparison run
  // exists, but guard against direct navigation.
  if (!selectedBaselineId) {
    return (
      <Box sx={{ maxWidth: 720, mx: 'auto' }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 4,
          }}
        >
          <Typography variant="h4" fontWeight={700}>
            Compare: {currentTestRun.name || 'Test Run'}
          </Typography>
          <Button
            startIcon={<CloseIcon />}
            onClick={handleClose}
            variant="outlined"
          >
            Close Comparison
          </Button>
        </Box>
        <Typography color="text.secondary">
          No other test runs are available for comparison on this test set.
        </Typography>
      </Box>
    );
  }

  return (
    <ComparisonView
      currentTestRun={currentTestRun}
      currentTestResults={currentTestResults}
      availableTestRuns={availableTestRuns}
      initialBaselineId={selectedBaselineId}
      onClose={handleClose}
      onLoadBaseline={handleLoadBaseline}
      prompts={prompts}
      behaviors={behaviors}
      testSetType={testSetType}
      project={project}
      projectName={projectName}
      closeButtonLabel="Close Comparison"
    />
  );
}
