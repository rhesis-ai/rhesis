export const dynamic = 'force-dynamic';

import { auth } from '@/auth';
import TracesClientWrapper from './components/TracesClientWrapper';
import { Alert, Paper } from '@mui/material';

/**
 * Server component for the Traces page.
 *
 * Deliberately NOT `prefetchList`-prefetched, unlike the other list pages:
 * traces are scoped to the active project, which lives in client state
 * (`useActiveProject`), so the server can't know which project's first page
 * to fetch. The grid falls back to its client fetch once the scope resolves.
 */
export default async function TracesPage() {
  try {
    const session = await auth();

    if (!session || session.error) {
      return (
        <Paper sx={{ p: 3 }}>
          <Alert severity="error">
            Authentication required. Please sign in to view traces.
          </Alert>
        </Paper>
      );
    }

    return (
      <TracesClientWrapper
        currentUserId={session.user?.id || ''}
        currentUserName={session.user?.name || ''}
        currentUserPicture={session.user?.picture || undefined}
      />
    );
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
