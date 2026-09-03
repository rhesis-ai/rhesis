export const dynamic = 'force-dynamic';

import * as React from 'react';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import ExperimentDetailClient, {
  type ExperimentDetailData,
} from './components/ExperimentDetailClient';
import { prefetch } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';
import { fetchExperimentRuns } from './components/experiment-data';
import { requireSession } from '@/utils/require-session';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function ExperimentDetailPage({ params }: PageProps) {
  await requireSession();

  const { identifier } = await params;
  const apiFactory = await createServerApiFactory();
  const client = apiFactory.getParametersClient();

  // Runs only needs `identifier`, not the experiment itself.
  const runsPromise = prefetch(Capability.Experiment.READ, () =>
    fetchExperimentRuns(apiFactory, identifier)
  );

  let initialExperiment: ExperimentDetailData;
  try {
    const experiment = await client.getExperiment(identifier);
    const [schema, environments] = await Promise.all([
      client.getSchema(experiment.project_id),
      client.getEnvironments(experiment.project_id),
    ]);
    initialExperiment = { experiment, schema, environments };
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  const runs = await runsPromise;

  return (
    <ExperimentDetailClient
      experimentId={identifier}
      initialExperiment={JSON.parse(JSON.stringify(initialExperiment))}
      initialRuns={runs}
    />
  );
}
