export const dynamic = 'force-dynamic';

import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import KnowledgeClientWrapper from './components/KnowledgeClientWrapper';
import { Alert, Paper } from '@mui/material';
import styles from '@/styles/Knowledge.module.css';

/**
 * Server component for the Knowledge page
 * Fetches sources data and renders the client wrapper component
 */
export default async function KnowledgePage() {
  try {
    const session = await auth();

    if (!session?.session_token) {
      return (
        <Paper className={styles.errorContainer}>
          <Alert severity="error">
            Authentication required. Please sign in to view knowledge sources.
          </Alert>
        </Paper>
      );
    }

    const apiFactory = new ApiClientFactory(session.session_token);
    const sourcesClient = apiFactory.getSourcesClient();
    const response = await sourcesClient.getSources({
      skip: 0,
      limit: 50,
      sort_by: 'created_at',
      sort_order: 'desc',
    });

    // Handle both array and paginated response formats
    const sources = Array.isArray(response) ? response : response?.data || [];

    return (
      <KnowledgeClientWrapper
        initialSources={sources}
        sessionToken={session.session_token}
      />
    );
  } catch (error) {
    // Show error state instead of empty sources
    return (
      <Paper className={styles.errorContainer}>
        <Alert severity="error">
          {error instanceof Error
            ? error.message
            : 'Failed to load knowledge sources. Please try again.'}
        </Alert>
      </Paper>
    );
  }
}
