import { useCallback, useEffect, useRef, useState } from 'react';
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
  /** Server-prefetched results (whole run); when present the mount fetch is skipped. */
  initialTestResults?: TestResultDetail[];
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

export async function fetchAllTestResults(
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

/**
 * Server-side prefetch: the run's results when one page holds them all,
 * otherwise `undefined`. Rendering the page shouldn't wait on tens of
 * sequential requests for a big run; the client loads those as before.
 */
export async function fetchSmallTestRunResults(
  factory: ApiClientFactory,
  testRunId: string
): Promise<TestResultDetail[] | undefined> {
  const response = await factory.getTestResultsClient().getTestResults({
    filter: `test_run_id eq '${testRunId}'`,
    limit: 100,
    skip: 0,
    sort_by: 'created_at',
    sort_order: 'desc',
  });
  const totalCount = response.pagination?.totalCount || 0;
  return response.data.length < totalCount ? undefined : response.data;
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
  initialTestResults,
}: UseTestRunDetailDataOptions): UseTestRunDetailDataReturn {
  const isAuthenticated = useIsAuthenticated();
  const [seed] = useState(() =>
    initialTestResults
      ? {
          ...extractRequirementsWithMetrics(initialTestResults),
          prompts: buildPromptsMap(initialTestResults),
        }
      : null
  );
  const [testResults, setTestResults] = useState<TestResultDetail[]>(
    initialTestResults ?? []
  );
  const [prompts, setPrompts] = useState<Record<string, Prompt>>(
    seed?.prompts ?? {}
  );
  const [requirements, setRequirements] = useState<RequirementWithMetrics[]>(
    seed?.requirements ?? []
  );
  const [availableMetrics, setAvailableMetrics] = useState<string[]>(
    seed?.availableMetrics ?? []
  );
  const [loading, setLoading] = useState(!initialTestResults);
  // The run the server-rendered results belong to: no mount fetch for it.
  const seededRunIdRef = useRef(initialTestResults ? testRunId : null);
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
    if (seededRunIdRef.current === testRunId && reloadToken === 0) {
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
