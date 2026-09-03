'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { Prompt } from '@/utils/api-client/interfaces/prompt';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import { fetchAllTestResults } from './test-run-results';

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

    if (requirement) {
      const requirementId = requirement.id as string;
      // Hold the entry rather than re-reading it: the has/set/get round trip
      // is what forced a non-null assertion, since TypeScript cannot know the
      // `set` above guarantees this `get`.
      let entry = requirementMap.get(requirementId);
      if (!entry) {
        entry = {
          id: requirementId,
          name: requirement.name,
          description: requirement.description || undefined,
          metrics: [],
        };
        requirementMap.set(requirementId, entry);
      }

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
