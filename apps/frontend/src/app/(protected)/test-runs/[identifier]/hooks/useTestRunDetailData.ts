import { useCallback, useEffect, useState } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { Prompt } from '@/utils/api-client/interfaces/prompt';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';

export interface RequirementWithMetrics {
  id: string;
  name: string;
  description?: string;
  metrics: Array<{ name: string; description?: string }>;
}

interface UseTestRunDetailDataOptions {
  testRunId: string;
  enabled?: boolean;
}

interface UseTestRunDetailDataReturn {
  testResults: TestResultDetail[];
  prompts: Record<string, Prompt>;
  requirements: RequirementWithMetrics[];
  availableMetrics: string[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

async function fetchAllTestResults(
  testRunId: string
): Promise<TestResultDetail[]> {
  const testResultsClient = new ApiClientFactory().getTestResultsClient();

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
          language_code: '',
        } as Prompt;
      }
      return acc;
    },
    {} as Record<string, Prompt>
  );
}

function extractRequirementsWithMetrics(results: TestResultDetail[]): {
  requirements: RequirementWithMetrics[];
  availableMetrics: string[];
} {
  const requirementMap = new Map<string, RequirementWithMetrics>();

  for (const result of results) {
    const requirement = result.test?.requirement;
    const metrics = result.test_metrics?.metrics ?? {};

    if (requirement && !requirementMap.has(requirement.id as string)) {
      requirementMap.set(requirement.id as string, {
        id: requirement.id as string,
        name: requirement.name,
        description: requirement.description || undefined,
        metrics: [],
      });
    }

    if (requirement) {
      const entry = requirementMap.get(requirement.id as string)!;
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

  const requirements = Array.from(requirementMap.values())
    .map(requirement => ({
      ...requirement,
      metrics: [...requirement.metrics].sort((a, b) =>
        a.name.localeCompare(b.name)
      ),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));

  const availableMetrics = [
    ...new Set(
      results.flatMap(r => Object.keys(r.test_metrics?.metrics ?? {}))
    ),
  ].sort();

  return { requirements, availableMetrics };
}

export function useTestRunDetailData({
  testRunId,
  enabled = true,
}: UseTestRunDetailDataOptions): UseTestRunDetailDataReturn {
  const isAuthenticated = useIsAuthenticated();
  const [testResults, setTestResults] = useState<TestResultDetail[]>([]);
  const [prompts, setPrompts] = useState<Record<string, Prompt>>({});
  const [requirements, setRequirements] = useState<RequirementWithMetrics[]>(
    []
  );
  const [availableMetrics, setAvailableMetrics] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const refetch = useCallback(async () => {
    setReloadToken(token => token + 1);
  }, []);

  useEffect(() => {
    if (!enabled || !isAuthenticated || !testRunId) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        const results = await fetchAllTestResults(testRunId);

        if (cancelled) return;

        const { requirements, availableMetrics } =
          extractRequirementsWithMetrics(results);

        setTestResults(results);
        setPrompts(buildPromptsMap(results));
        setRequirements(requirements);
        setAvailableMetrics(availableMetrics);
      } catch {
        if (!cancelled) {
          setError('Failed to load test run data');
          setTestResults([]);
          setPrompts({});
          setRequirements([]);
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
  }, [testRunId, enabled, reloadToken, isAuthenticated]);

  return {
    testResults,
    prompts,
    requirements,
    availableMetrics,
    loading,
    error,
    refetch,
  };
}
