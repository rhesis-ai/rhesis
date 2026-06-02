'use client';

import React, { useCallback, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useRouter } from 'next/navigation';
import ComparisonView from '../components/ComparisonView';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { formatDate } from '@/utils/date';
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
  sessionToken: string;
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
  sessionToken,
  initialBaselineId,
  testSetType,
  project,
  projectName,
}: ComparePageClientProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const [selectedBaselineId, setSelectedBaselineId] = useState<
    string | undefined
  >(
    initialBaselineId && availableTestRuns.some(r => r.id === initialBaselineId)
      ? initialBaselineId
      : undefined
  );

  const handleClose = useCallback(() => {
    if (window.opener) {
      window.close();
    } else {
      router.push(`/test-runs/${currentTestRun.id}`);
    }
  }, [router, currentTestRun.id]);

  const handleLoadBaseline = useCallback(
    async (baselineTestRunId: string): Promise<TestResultDetail[]> => {
      try {
        const testResultsClient = new ApiClientFactory(
          sessionToken
        ).getTestResultsClient();
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
    [sessionToken, notifications]
  );

  const handleSelectBaseline = (runId: string) => {
    setSelectedBaselineId(runId);
    const url = new URL(window.location.href);
    url.searchParams.set('baseline', runId);
    window.history.replaceState({}, '', url.toString());
  };

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

        <Typography variant="h6" sx={{ mb: 2 }}>
          Select a baseline run
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Choose a previous test run on the same test set to compare against the
          current run.
        </Typography>

        {availableTestRuns.length === 0 ? (
          <Typography color="text.secondary">
            No other test runs are available for comparison on this test set.
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {availableTestRuns.map(run => (
              <Card key={run.id} variant="outlined">
                <CardActionArea onClick={() => handleSelectBaseline(run.id)}>
                  <CardContent>
                    <Typography variant="subtitle1" fontWeight={600}>
                      {run.name || `Run ${run.id.slice(0, 8)}`}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {formatDate(run.created_at)}
                    </Typography>
                  </CardContent>
                </CardActionArea>
              </Card>
            ))}
          </Box>
        )}
      </Box>
    );
  }

  const filteredRuns = availableTestRuns.filter(
    r => r.id === selectedBaselineId
  );

  return (
    <ComparisonView
      currentTestRun={currentTestRun}
      currentTestResults={currentTestResults}
      availableTestRuns={
        filteredRuns.length > 0 ? filteredRuns : availableTestRuns
      }
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
