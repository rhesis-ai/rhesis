export const dynamic = 'force-dynamic';

import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetchList } from '@/utils/server-prefetch';
import { emptyFilters, directoryListParams } from '@/utils/directory';
import { Capability } from '@/constants/capabilities';
import KnowledgeClientWrapper from './components/KnowledgeClientWrapper';
import { sourcesDirectory } from './components/directory';
import { Alert, Paper } from '@mui/material';
import styles from '@/styles/Knowledge.module.css';

/**
 * Server component for the Knowledge page
 */
export default async function KnowledgePage() {
  try {
    const session = await auth();

    if (!session || session.error) {
      return (
        <Paper className={styles.errorContainer}>
          <Alert severity="error">
            Authentication required. Please sign in to view knowledge sources.
          </Alert>
        </Paper>
      );
    }

    const factory = await createServerApiFactory();

    const { initialData, initialTotalCount } = await prefetchList(
      Capability.Source.READ,
      () =>
        sourcesDirectory.list(
          factory,
          directoryListParams(sourcesDirectory, {
            page: 1,
            pageSize: sourcesDirectory.defaultPageSize,
            sort: sourcesDirectory.defaultSort,
            filters: emptyFilters(sourcesDirectory),
          })
        )
    );

    return (
      <KnowledgeClientWrapper
        initialData={initialData}
        initialTotalCount={initialTotalCount}
      />
    );
  } catch (error) {
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
