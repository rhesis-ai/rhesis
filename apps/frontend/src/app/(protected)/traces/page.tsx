export const dynamic = 'force-dynamic';

import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import TracesClientWrapper from './components/TracesClientWrapper';
import { Alert, Paper } from '@mui/material';

/**
 * Server component for the Traces page
 * Fetches initial data and renders the client wrapper component
 */
export default async function TracesPage() {
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

    return <TracesClientWrapper sessionToken={session.session_token} />;
  } catch (error) {
    // Show error state instead of empty traces
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">
          {error instanceof Error
            ? error.message
            : 'Failed to load traces. Please try again.'}
        </Alert>
      </Paper>
    );
  }
}
