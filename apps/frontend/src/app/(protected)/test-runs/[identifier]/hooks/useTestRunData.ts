import { useEffect, useState, useCallback } from 'react';
import { GridPaginationModel } from '@mui/x-data-grid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { Prompt } from '@/utils/api-client/interfaces/prompt';
import { Behavior } from '@/utils/api-client/interfaces/behavior';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import { UUID } from 'crypto';

interface BehaviorWithMetrics extends Behavior {
  metrics: MetricDetail[];
}

interface UseTestRunDataProps {
  testRunId: string;
  sessionToken: string;
  paginationModel: GridPaginationModel;
  enabled?: boolean;
}

interface UseTestRunDataReturn {
  testResults: TestResultDetail[];
  prompts: Record<string, Prompt>;
  behaviors: BehaviorWithMetrics[];
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
  const [behaviors, setBehaviors] = useState<BehaviorWithMetrics[]>([]);
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
      const promptsClient = apiFactory.getPromptsClient();
      const testRunsClient = apiFactory.getTestRunsClient();

      // Calculate skip based on pagination model
      const skip = paginationModel.page * paginationModel.pageSize;

      // Fetch test results with pagination parameters
      const response = await testResultsClient.getTestResults({
        filter: `test_run_id eq '${testRunId}'`,
        skip: skip,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      const results = response.data;
      setTotalCount(response.pagination.totalCount);

      // Get unique prompt IDs
      const promptIds = [
        ...new Set(
          results
            .filter((r: TestResultDetail) => r.prompt_id)
            .map((r: TestResultDetail) => r.prompt_id!)
        ),
      ];

      // Fetch all prompts in parallel
      const promptsData = await Promise.all(
        promptIds.map((id: string) => promptsClient.getPrompt(id))
      );

      // Create a map of prompt ID to prompt data
      const promptsMap = promptsData.reduce(
        (acc, prompt) => {
          acc[prompt.id] = prompt;
          return acc;
        },
        {} as Record<string, Prompt>
      );

      // Fetch only behaviors that have test results for this test run
      const behaviorsData = await testRunsClient.getTestRunBehaviors(testRunId);

      // Fetch metrics for each behavior
      const behaviorClient = apiFactory.getBehaviorClient();
      const behaviorsWithMetrics = await Promise.all(
        behaviorsData.map(async behavior => {
          try {
            // Type assertion needed due to type definition mismatch
            const behaviorMetrics = await (
              behaviorClient as any
            ).getBehaviorMetrics(behavior.id as UUID);
            return {
              ...behavior,
              metrics: behaviorMetrics,
            };
          } catch (error) {
            console.error(
              `Error fetching metrics for behavior ${behavior.id}:`,
              error
            );
            return {
              ...behavior,
              metrics: [],
            };
          }
        })
      );

      // Filter out behaviors that have no metrics (though this should be rare now)
      const behaviorsWithMetricsFiltered = behaviorsWithMetrics.filter(
        behavior => behavior.metrics.length > 0
      );

      setBehaviors(behaviorsWithMetricsFiltered);
      setPrompts(promptsMap);
      setTestResults(results);
    } catch (error) {
      console.error('Error fetching test run data:', error);
      setError('Failed to load test run data');
      setTestResults([]);
      setPrompts({});
      setBehaviors([]);
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
    loading,
    totalCount,
    error,
  };
}

export type { BehaviorWithMetrics };
