export const dynamic = 'force-dynamic';

import { redirect } from 'next/navigation';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Alert, Paper } from '@mui/material';

interface TraceByIdPageProps {
  params: Promise<{ identifier: string }>;
}

/**
 * Server component that resolves a trace span DB UUID to the traces page
 * with the drawer auto-opened for the correct trace.
 *
 * This enables "Go to Trace" navigation from tasks and comments.
 */
export default async function TraceByIdPage({ params }: TraceByIdPageProps) {
  const { identifier } = await params;

  try {
    const session = await auth();
    if (!session?.session_token) {
      return (
        <Paper sx={{ p: 3 }}>
          <Alert severity="error">
            Authentication required. Please sign in to view traces.
          </Alert>
        </Paper>
      );
    }

    const clientFactory = new ApiClientFactory(session.session_token);
    const client = clientFactory.getTelemetryClient();
    const lookup = await client.lookupSpan(identifier);

    redirect(
      `/traces?open_trace=${encodeURIComponent(lookup.trace_id)}&project_id=${encodeURIComponent(lookup.project_id)}`
    );
  } catch (error) {
    if (
      error &&
      typeof error === 'object' &&
      'digest' in error &&
      typeof (error as { digest: unknown }).digest === 'string' &&
      (error as { digest: string }).digest.startsWith('NEXT_REDIRECT')
    ) {
      throw error;
    }

    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">
          {error instanceof Error
            ? error.message
            : 'Failed to resolve trace. The trace may have been deleted.'}
        </Alert>
      </Paper>
    );
  }
}
