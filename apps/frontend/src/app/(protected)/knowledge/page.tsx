export const dynamic = 'force-dynamic';

import { auth } from '@/auth';
import KnowledgeClientWrapper from './components/KnowledgeClientWrapper';
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

    return <KnowledgeClientWrapper />;
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
