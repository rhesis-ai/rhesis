export const dynamic = 'force-dynamic';

import * as React from 'react';
import { Alert, Paper } from '@mui/material';
import { auth } from '@/auth';
import ExperimentDetailClient from './components/ExperimentDetailClient';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function ExperimentDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session || session.error) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">
          Authentication required. Please sign in to view this experiment.
        </Alert>
      </Paper>
    );
  }

  const { identifier } = await params;
  return (
    <ExperimentDetailClient
      experimentId={identifier}
      sessionToken={session.session_token ?? ''}
    />
  );
}
