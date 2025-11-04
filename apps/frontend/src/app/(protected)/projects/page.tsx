export const dynamic = 'force-dynamic';

import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import ProjectsClientWrapper from './components/ProjectsClientWrapper';
import { Box, Typography, Alert, Paper } from '@mui/material';

/**
 * Server component for the Projects page
 * Fetches projects data and renders the client wrapper component
 */
export default async function ProjectsPage() {
  try {
    const session = await auth();

    if (!session?.session_token) {
      return (
        <Paper sx={{ p: 3 }}>
          <Alert severity="error">
            Authentication required. Please sign in to view projects.
          </Alert>
        </Paper>
      );
    }

    const apiFactory = new ApiClientFactory(session.session_token);
    const projectsClient = apiFactory.getProjectsClient();
    const response = await projectsClient.getProjects();

    // Handle both array and paginated response formats
    const projects = Array.isArray(response) ? response : response?.data || [];

    return (
      <ProjectsClientWrapper
        initialProjects={projects}
        sessionToken={session.session_token}
      />
    );
  } catch (error) {
    // Show error state instead of empty projects
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">
          {error instanceof Error
            ? error.message
            : 'Failed to load projects. Please try again.'}
        </Alert>
      </Paper>
    );
  }
}
