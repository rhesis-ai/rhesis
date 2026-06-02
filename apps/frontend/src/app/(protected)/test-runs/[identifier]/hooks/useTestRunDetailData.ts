import { useEffect, useState } from 'react';
import { UUID } from 'crypto';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { Prompt } from '@/utils/api-client/interfaces/prompt';

export interface BehaviorWithMetrics {
  id: string;
  name: string;
  description?: string;
  metrics: Array<{ name: string; description?: string }>;
}

interface UseTestRunDetailDataOptions {
  testRunId: string;
  sessionToken: string;
  enabled?: boolean;
}

interface UseTestRunDetailDataReturn {
  testResults: TestResultDetail[];
  prompts: Record<string, Prompt>;
  behaviors: BehaviorWithMetrics[];
  availableMetrics: string[];
  loading: boolean;
  error: string | null;
}

async function fetchAllTestResults(
  testRunId: string,
  sessionToken: string
): Promise<TestResultDetail[]> {
  const testResultsClient = new ApiClientFactory(
    sessionToken
  ).getTestResultsClient();

  let testResults: TestResultDetail[] = [];
  let skip = 0;
  const batchSize = 100;
  let hasMore = true;

  while (hasMore) {
    const response = await testResultsClient.getTestResults({
      filter: `test_run_id eq '${testRunId}'`,
      limit: batchSize,
      skip,
      sort_by: 'created_at',
      sort_order: 'desc',
    });

    testResults = [...testResults, ...response.data];
    const totalCount = response.pagination?.totalCount || 0;
    hasMore = testResults.length < totalCount;
    skip += batchSize;

    if (skip > 10000) break;
  }

  return testResults;
}

function buildPromptsMap(
  testResults: TestResultDetail[]
): Record<string, Prompt> {
  return testResults.reduce(
    (acc, testResult) => {
      if (testResult.test?.prompt) {
        acc[testResult.test.prompt.id] = {
          id: testResult.test.prompt.id,
          content: testResult.test.prompt.content,
          expected_response: testResult.test.prompt.expected_response,
          nano_id: testResult.test.prompt.nano_id,
          counts: testResult.test.prompt.counts,
        } as Prompt;
      }
      return acc;
    },
    {} as Record<string, Prompt>
  );
}

async function fetchBehaviorsWithMetrics(
  testRunId: string,
  sessionToken: string
): Promise<{
  behaviors: BehaviorWithMetrics[];
  availableMetrics: string[];
}> {
  const apiFactory = new ApiClientFactory(sessionToken);
  const testRunsClient = apiFactory.getTestRunsClient();
  const behaviorClient = apiFactory.getBehaviorClient();

  const [behaviorsData, metricsData] = await Promise.all([
    testRunsClient.getTestRunBehaviors(testRunId),
    testRunsClient.getTestRunMetrics(testRunId),
  ]);

  const behaviorsWithMetrics = await Promise.all(
    behaviorsData.map(async behavior => {
      try {
        const behaviorMetrics = await behaviorClient.getBehaviorMetrics(
          behavior.id as UUID
        );
        return {
          id: behavior.id as string,
          name: behavior.name,
          description: behavior.description ?? undefined,
          metrics: behaviorMetrics.map(m => ({
            name: m.name,
            description: m.description ?? undefined,
          })),
        };
      } catch {
        return {
          id: behavior.id as string,
          name: behavior.name,
          description: behavior.description ?? undefined,
          metrics: [] as Array<{ name: string; description?: string }>,
        };
      }
    })
  );

  return {
    behaviors: behaviorsWithMetrics,
    availableMetrics: metricsData,
  };
}

export function useTestRunDetailData({
  testRunId,
  sessionToken,
  enabled = true,
}: UseTestRunDetailDataOptions): UseTestRunDetailDataReturn {
  const [testResults, setTestResults] = useState<TestResultDetail[]>([]);
  const [prompts, setPrompts] = useState<Record<string, Prompt>>({});
  const [behaviors, setBehaviors] = useState<BehaviorWithMetrics[]>([]);
  const [availableMetrics, setAvailableMetrics] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !sessionToken || !testRunId) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        const [results, behaviorData] = await Promise.all([
          fetchAllTestResults(testRunId, sessionToken),
          fetchBehaviorsWithMetrics(testRunId, sessionToken),
        ]);

        if (cancelled) return;

        setTestResults(results);
        setPrompts(buildPromptsMap(results));
        setBehaviors(behaviorData.behaviors);
        setAvailableMetrics(behaviorData.availableMetrics);
      } catch {
        if (!cancelled) {
          setError('Failed to load test run data');
          setTestResults([]);
          setPrompts({});
          setBehaviors([]);
          setAvailableMetrics([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [testRunId, sessionToken, enabled]);

  return {
    testResults,
    prompts,
    behaviors,
    availableMetrics,
    loading,
    error,
  };
}
