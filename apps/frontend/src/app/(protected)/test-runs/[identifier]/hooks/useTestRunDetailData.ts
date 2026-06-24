import { useEffect, useState } from 'react';
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

function extractBehaviorsWithMetrics(results: TestResultDetail[]): {
  behaviors: BehaviorWithMetrics[];
  availableMetrics: string[];
} {
  const behaviorMap = new Map<string, BehaviorWithMetrics>();

  for (const result of results) {
    const behavior = result.test?.behavior;
    const metrics = result.test_metrics?.metrics ?? {};

    if (behavior && !behaviorMap.has(behavior.id as string)) {
      behaviorMap.set(behavior.id as string, {
        id: behavior.id as string,
        name: behavior.name,
        description: behavior.description || undefined,
        metrics: [],
      });
    }

    if (behavior) {
      const entry = behaviorMap.get(behavior.id as string)!;
      for (const [name, data] of Object.entries(metrics)) {
        if (!entry.metrics.some(m => m.name === name)) {
          entry.metrics.push({
            name,
            description: data.description || undefined,
          });
        }
      }
    }
  }

  const behaviors = Array.from(behaviorMap.values())
    .map(behavior => ({
      ...behavior,
      metrics: [...behavior.metrics].sort((a, b) =>
        a.name.localeCompare(b.name)
      ),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));

  const availableMetrics = [
    ...new Set(
      results.flatMap(r => Object.keys(r.test_metrics?.metrics ?? {}))
    ),
  ].sort();

  return { behaviors, availableMetrics };
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
        const results = await fetchAllTestResults(testRunId, sessionToken);

        if (cancelled) return;

        const { behaviors, availableMetrics } =
          extractBehaviorsWithMetrics(results);

        setTestResults(results);
        setPrompts(buildPromptsMap(results));
        setBehaviors(behaviors);
        setAvailableMetrics(availableMetrics);
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
