export const dynamic = 'force-dynamic';

import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import SourcePreviewClientWrapper from './components/SourcePreviewClientWrapper';
import { Alert, Paper } from '@mui/material';
import styles from '@/styles/Knowledge.module.css';

interface SourcePreviewPageProps {
  params: Promise<{
    identifier: string;
  }>;
}

/**
 * Server component for the Source Preview page
 * Fetches source data and renders the client wrapper component
 */
export default async function SourcePreviewPage({
  params,
}: SourcePreviewPageProps) {
  try {
    const session = await auth();

    if (!session || session.error) {
      return (
        <Paper className={styles.errorContainer}>
          <Alert severity="error">
            Authentication required. Please sign in to view source content.
          </Alert>
        </Paper>
      );
    }

    const apiFactory = await createServerApiFactory();
    const sourcesClient = apiFactory.getSourcesClient();

    // Await params before using its properties (Next.js 15 requirement)
    const resolvedParams = await params;

    // Fetch source details with content field
    const source = await sourcesClient.getSourceWithContent(
      resolvedParams.identifier as `${string}-${string}-${string}-${string}-${string}`
    );

    return (
      <SourcePreviewClientWrapper
        source={source}
        sessionToken={session.session_token ?? ''}
        currentUserId={session.user?.id || ''}
        currentUserName={session.user?.name || ''}
        currentUserPicture={session.user?.picture || undefined}
      />
    );
  } catch (error) {
    notFoundIfEntityMissing(error);

    return (
      <Paper className={styles.errorContainer}>
        <Alert severity="error">
          {error instanceof Error
            ? error.message
            : 'Failed to load source content. Please try again.'}
        </Alert>
      </Paper>
    );
  }
}
