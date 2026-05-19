'use client';

import { useState, useCallback } from 'react';
import { Box, Button, Typography, Paper } from '@mui/material';
import { EditIcon, DeleteIcon } from '@/components/icons';
import ProjectContent from '../components/ProjectContent';
import ProjectEditDrawer from './edit-drawer';
import ProjectEndpoints from './components/ProjectEndpoints';
import ProjectTraceMetrics from './components/ProjectTraceMetrics';
import { Project } from '@/utils/api-client/interfaces/project';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import {
  PageLayout,
  type BreadcrumbItem,
} from '@/components/layout/PageLayout';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';

interface ClientWrapperProps {
  project: Project;
  sessionToken: string;
  projectId: string;
}

export default function ClientWrapper({
  project,
  sessionToken,
  projectId,
}: ClientWrapperProps) {
  const router = useRouter();
  const params = useParams<{ identifier: string }>();
  const searchParams = useSearchParams();

  // Enable onboarding tour if tour parameter is present
  const tourId = searchParams.get('tour');
  useOnboardingTour(tourId === 'endpoint' ? 'endpoint' : undefined);

  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [currentProject, setCurrentProject] = useState<Project>(project);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const notifications = useNotifications();

  const title = currentProject.name || `Project ${params.identifier}`;
  const breadcrumbs: BreadcrumbItem[] = [
    { label: 'Projects', href: '/projects' },
    { label: title },
  ];

  const handleUpdateProject = useCallback(
    async (updatedProject: Partial<Project>) => {
      setIsUpdating(true);
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const projectsClient = apiFactory.getProjectsClient();
        const response = await projectsClient.updateProject(
          projectId,
          updatedProject
        );

        // Preserve the owner object from currentProject if response doesn't include it
        const updatedProjectWithOwner = {
          ...response,
          owner: response.owner || currentProject.owner,
          owner_id: response.owner_id || currentProject.owner_id,
        };

        setCurrentProject(updatedProjectWithOwner);
        setIsDrawerOpen(false);
        notifications.show('Project updated successfully', {
          severity: 'success',
        });
      } catch (error) {
        notifications.show(
          error instanceof Error ? error.message : 'Failed to update project',
          { severity: 'error' }
        );
      } finally {
        setIsUpdating(false);
      }
    },
    [projectId, sessionToken, notifications, currentProject]
  );

  const handleDeleteClick = () => {
    setDeleteConfirmOpen(true);
  };

  const handleDeleteCancel = () => {
    setDeleteConfirmOpen(false);
  };

  const handleDeleteConfirm = async () => {
    setIsDeleting(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const projectsClient = apiFactory.getProjectsClient();
      await projectsClient.deleteProject(projectId);
      notifications.show('Project deleted successfully', {
        severity: 'success',
      });
      router.push('/projects');
    } catch (error) {
      notifications.show(
        error instanceof Error ? error.message : 'Failed to delete project',
        { severity: 'error' }
      );
      setDeleteConfirmOpen(false);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <PageLayout title={title} breadcrumbs={breadcrumbs}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          mb: 3,
        }}
      >
        <Button
          variant="contained"
          startIcon={<EditIcon />}
          onClick={() => setIsDrawerOpen(true)}
          disabled={isUpdating || isDeleting}
          sx={{ mr: 2 }}
        >
          Edit Project
        </Button>
        <Button
          variant="outlined"
          color="error"
          startIcon={<DeleteIcon />}
          onClick={handleDeleteClick}
          disabled={isUpdating || isDeleting}
        >
          Delete
        </Button>
      </Box>

      {/* Project Overview */}
      <ProjectContent project={currentProject} />

      {/* Endpoints Section */}
      <Box sx={{ mt: 3 }}>
        <Typography
          variant="h6"
          sx={{
            mb: 2,
            fontWeight: 600,
            color: 'text.primary',
          }}
        >
          Endpoints
        </Typography>
        <ProjectEndpoints projectId={projectId} sessionToken={sessionToken} />
      </Box>

      {/* Trace Metrics Section */}
      <Box sx={{ mt: 3 }}>
        <Typography
          variant="h6"
          sx={{
            mb: 2,
            fontWeight: 600,
            color: 'text.primary',
          }}
        >
          Trace Metrics
        </Typography>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <ProjectTraceMetrics
            project={currentProject}
            sessionToken={sessionToken}
            onProjectUpdate={handleUpdateProject}
          />
        </Paper>
      </Box>

      {/* Edit Drawer */}
      <ProjectEditDrawer
        project={currentProject}
        sessionToken={sessionToken}
        open={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onSave={handleUpdateProject}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteModal
        open={deleteConfirmOpen}
        onClose={handleDeleteCancel}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        itemType="project"
        itemName={currentProject.name}
        title="Delete Project"
      />
    </PageLayout>
  );
}
