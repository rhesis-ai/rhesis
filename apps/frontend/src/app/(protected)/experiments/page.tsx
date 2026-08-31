export const dynamic = 'force-dynamic';

import * as React from 'react';
import { Alert, Paper } from '@mui/material';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { firstPageParams } from '@/utils/list';
import { Capability } from '@/constants/capabilities';
import ExperimentsClientWrapper from './components/ExperimentsClientWrapper';
import { experimentsList } from './components/list';

/**
 * Server-rendered shell for the Experiments index page.
 *
 * The page is project-scoped (an experiment lives inside one
 * project), but the index intentionally lists experiments across
 * every project the user can see. The client wrapper renders a
 * project filter so the user can narrow down without paying for a
 * separate route per project.
 *
 * Visibility filtering happens server-side: the backend list
 * endpoint never returns another user's private experiments.
 */
export default async function ExperimentsPage() {
  const session = await auth();

  if (!session || session.error) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">
          Authentication required. Please sign in to view experiments.
        </Alert>
      </Paper>
    );
  }

  const factory = await createServerApiFactory();

  const { initialData, initialTotalCount } = await prefetchList(
    Capability.Experiment.READ,
    () =>
      experimentsList.list(factory, firstPageParams(experimentsList))
  );

  return (
    <ExperimentsClientWrapper
      initialData={initialData}
      initialTotalCount={initialTotalCount}
    />
  );
}
