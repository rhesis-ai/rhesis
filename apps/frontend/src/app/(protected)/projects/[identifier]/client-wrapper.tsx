'use client';

import { useState, useCallback } from 'react';
import { Box, Button, Typography } from '@mui/material';
import Link from 'next/link';
import { EditIcon, DeleteIcon } from '@/components/icons';
import ProjectContent from '../components/ProjectContent';
import ProjectEditDrawer from './edit-drawer';
import ProjectEndpoints from './components/ProjectEndpoints';
import { Project } from '@/utils/api-client/interfaces/project';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { useActivePage } from '@toolpad/core/useActivePage';
import { PageContainer, Breadcrumb } from '@toolpad/core/PageContainer';
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
  const activePage = useActivePage();

  // Enable onboarding tour if tour parameter is present
  const tourId = searchParams.get('tour');
  useOnboardingTour(tourId === 'endpoint' ? 'endpoint' : undefined);

  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [currentProject, setCurrentProject] = useState<Project>(project);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const notifications = useNotifications();

  // Create dynamic breadcrumbs based on the current project (reactive to currentProject changes)
  const title = currentProject.name || `Project ${params.identifier}`;

  // Create fallback breadcrumbs when activePage is null (reactive to currentProject changes)
  let breadcrumbs: Breadcrumb[] = [];
  if (activePage) {
    const path = `${activePage.path}/${params.identifier}`;
    breadcrumbs = [...activePage.breadcrumbs, { title, path }];
  } else {
    // Fallback breadcrumbs
    breadcrumbs = [
      { title: 'Projects', path: '/projects' },
      { title, path: `/projects/${params.identifier}` },
    ];
  }

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
    <PageContainer title={title} breadcrumbs={breadcrumbs}>
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
    </PageContainer>
  );
}
