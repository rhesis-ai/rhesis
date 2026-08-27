import type { ApiClientFactory } from '@/utils/api-client/client-factory';

/** Results grouped by run (the Runs tab). Shared by server prefetch and client. */
export function fetchExperimentRuns(
  factory: ApiClientFactory,
  experimentId: string
) {
  return factory.getParametersClient().getExperimentResultsByRun(experimentId);
}

export type ExperimentRunsData = Awaited<
  ReturnType<typeof fetchExperimentRuns>
>;
