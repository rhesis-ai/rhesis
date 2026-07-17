export const dynamic = 'force-dynamic';

import { auth } from '@/auth';
import ProjectsClientWrapper from './components/ProjectsClientWrapper';
import { Alert, Paper } from '@mui/material';

/**
 * Server component for the Projects page.
 * Delegates all data fetching to the client wrapper so pagination and
 * filtering work without a full page reload.
 */
export default async function ProjectsPage() {
  const session = await auth();

  if (!session || session.error) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">
          Authentication required. Please sign in to view projects.
        </Alert>
      </Paper>
    );
  }

  return <ProjectsClientWrapper />;
}
