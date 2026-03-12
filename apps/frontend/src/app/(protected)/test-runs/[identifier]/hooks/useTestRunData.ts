import { useEffect, useState, useCallback } from 'react';
import { GridPaginationModel } from '@mui/x-data-grid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { Prompt } from '@/utils/api-client/interfaces/prompt';
import { Behavior } from '@/utils/api-client/interfaces/behavior';

interface UseTestRunDataProps {
  testRunId: string;
  sessionToken: string;
  paginationModel: GridPaginationModel;
  enabled?: boolean;
}

interface UseTestRunDataReturn {
  testResults: TestResultDetail[];
  prompts: Record<string, Prompt>;
  behaviors: Behavior[];
  availableMetrics: string[];
  loading: boolean;
  totalCount: number;
  error: string | null;
}

export function useTestRunData({
  testRunId,
  sessionToken,
  paginationModel,
  enabled = true,
}: UseTestRunDataProps): UseTestRunDataReturn {
  const [testResults, setTestResults] = useState<TestResultDetail[]>([]);
  const [prompts, setPrompts] = useState<Record<string, Prompt>>({});
  const [behaviors, setBehaviors] = useState<Behavior[]>([]);
  const [availableMetrics, setAvailableMetrics] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  const fetchTestRunData = useCallback(async () => {
    if (!enabled || !sessionToken || !testRunId) return;

    try {
      setLoading(true);
      setError(null);

      const apiFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = apiFactory.getTestResultsClient();
      const testRunsClient = apiFactory.getTestRunsClient();

      // Calculate skip based on pagination model
      const skip = paginationModel.page * paginationModel.pageSize;

      // Fetch test results, behaviors, and metrics used in this run in parallel
      const [response, behaviorsData, metricsData] = await Promise.all([
        testResultsClient.getTestResults({
          filter: `test_run_id eq '${testRunId}'`,
          skip: skip,
          limit: paginationModel.pageSize,
          sort_by: 'created_at',
          sort_order: 'desc',
        }),
        testRunsClient.getTestRunBehaviors(testRunId),
        testRunsClient.getTestRunMetrics(testRunId),
      ]);

      const results = response.data;
      setTotalCount(response.pagination.totalCount);

      // Build prompts map from nested data in test results (optimized - no separate API calls needed!)
      const promptsMap = results.reduce(
        (acc, testResult: TestResultDetail) => {
          // Use nested prompt data if available
          if (testResult.test?.prompt) {
            acc[testResult.test.prompt.id] = {
              id: testResult.test.prompt.id,
              content: testResult.test.prompt.content,
              expected_response: testResult.test.prompt.expected_response,
              nano_id: testResult.test.prompt.nano_id,
              counts: testResult.test.prompt.counts,
            } as Prompt;
          }
          // Fallback: if prompt_id exists but nested data is not available (backward compatibility)
          else if (testResult.prompt_id && !acc[testResult.prompt_id]) {
          }
          return acc;
        },
        {} as Record<string, Prompt>
      );

      setBehaviors(behaviorsData);
      setAvailableMetrics(metricsData);
      setPrompts(promptsMap);
      setTestResults(results);
    } catch (_error) {
      setError('Failed to load test run data');
      setTestResults([]);
      setPrompts({});
      setBehaviors([]);
      setAvailableMetrics([]);
    } finally {
      setLoading(false);
    }
  }, [testRunId, sessionToken, paginationModel, enabled]);

  useEffect(() => {
    fetchTestRunData();
  }, [fetchTestRunData]);

  return {
    testResults,
    prompts,
    behaviors,
    availableMetrics,
    loading,
    totalCount,
    error,
  };
}
