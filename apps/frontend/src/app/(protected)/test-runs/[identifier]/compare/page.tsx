import { Box } from '@mui/material';
import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type { UUID } from 'crypto';
import ComparePageClient from './ComparePageClient';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ identifier: string }>;
}): Promise<Metadata> {
  const { identifier } = await params;
  return {
    title: 'Compare Test Runs',
    description: `Compare test run ${identifier} against a baseline`,
  };
}

export default async function TestRunComparePage({
  params,
  searchParams,
}: {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { identifier } = await params;
  const resolvedSearchParams = await searchParams;
  const baselineParam = resolvedSearchParams?.baseline;
  const initialBaselineId =
    typeof baselineParam === 'string' ? baselineParam : undefined;

  const session = await auth();
  if (!session?.session_token) {
    throw new Error('Authentication required');
  }

  const apiFactory = new ApiClientFactory(session.session_token);
  const testRunsClient = apiFactory.getTestRunsClient();
  const testResultsClient = apiFactory.getTestResultsClient();
  const behaviorClient = apiFactory.getBehaviorClient();

  const testRun = await testRunsClient
    .getTestRun(identifier)
    .catch(() => notFound());

  let testResults: TestResultDetail[] = [];
  let skip = 0;
  const batchSize = 100;
  let hasMore = true;

  while (hasMore) {
    const testResultsResponse = await testResultsClient.getTestResults({
      filter: `test_run_id eq '${identifier}'`,
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

  const promptsMap = testResults.reduce(
    (acc, testResult) => {
      if (testResult.test?.prompt) {
        acc[testResult.test.prompt.id] = {
          id: testResult.test.prompt.id,
          content: testResult.test.prompt.content,
          expected_response: testResult.test.prompt.expected_response,
          nano_id: testResult.test.prompt.nano_id,
          counts: testResult.test.prompt.counts,
        };
      }
      return acc;
    },
    {} as Record<
      string,
      {
        id: string;
        content: string;
        expected_response?: string;
        nano_id?: string;
        counts?: unknown;
      }
    >
  );

  const testSetId = testRun.test_configuration?.test_set?.id;
  let availableTestRuns: Array<{
    id: string;
    name?: string;
    created_at: string;
    pass_rate?: number;
    experiment_id?: string;
    parameter_version?: string;
    experiment_name?: string;
  }> = [];

  if (testSetId) {
    try {
      const response = await testRunsClient.getTestRuns({
        limit: 50,
        skip: 0,
        sort_by: 'created_at',
        sort_order: 'desc',
        filter: `test_configuration/test_set/id eq '${testSetId}'`,
      });
      availableTestRuns = response.data
        .filter(run => run.id !== identifier)
        .map(run => ({
          id: run.id,
          name: run.name,
          created_at:
            (typeof run.attributes?.started_at === 'string'
              ? run.attributes.started_at
              : null) ||
            (typeof run.created_at === 'string' ? run.created_at : '') ||
            '',
          experiment_id: run.experiment_id ?? undefined,
          parameter_version:
            typeof run.attributes?.parameter_version === 'string'
              ? (run.attributes.parameter_version as string)
              : undefined,
          experiment_name:
            typeof run.attributes?.parameter_experiment_name === 'string'
              ? (run.attributes.parameter_experiment_name as string)
              : undefined,
        }));
    } catch {
      availableTestRuns = [];
    }
  }

  let behaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }> = [];

  try {
    const behaviorsData = await testRunsClient.getTestRunBehaviors(identifier);
    behaviors = await Promise.all(
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
  } catch {
    behaviors = [];
  }

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', p: 3 }}>
      <ComparePageClient
        currentTestRun={{
          id: testRun.id,
          name: testRun.name,
          created_at:
            (typeof testRun.attributes?.started_at === 'string'
              ? testRun.attributes.started_at
              : null) ||
            testRun.created_at ||
            '',
          experiment_id: testRun.experiment_id ?? undefined,
          parameter_version:
            typeof testRun.attributes?.parameter_version === 'string'
              ? (testRun.attributes.parameter_version as string)
              : undefined,
          experiment_name:
            typeof testRun.attributes?.parameter_experiment_name === 'string'
              ? (testRun.attributes.parameter_experiment_name as string)
              : undefined,
        }}
        currentTestResults={testResults}
        availableTestRuns={availableTestRuns}
        prompts={promptsMap}
        behaviors={behaviors}
        sessionToken={session.session_token}
        initialBaselineId={initialBaselineId}
        testSetType={
          testRun.test_configuration?.test_set?.test_set_type?.type_value
        }
        project={testRun.test_configuration?.endpoint?.project}
        projectName={testRun.test_configuration?.endpoint?.project?.name}
      />
    </Box>
  );
}
