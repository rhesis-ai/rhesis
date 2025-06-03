'use client';

import { useState, useCallback } from 'react';
import { Box, Button, Breadcrumbs, Typography, Alert, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material';
import Link from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import ProjectContent from '../components/ProjectContent';
import ProjectEditDrawer from './edit-drawer';
import { Project } from '@/utils/api-client/interfaces/project';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter, useParams } from 'next/navigation';
import { useActivePage } from '@toolpad/core/useActivePage';
import { PageContainer, Breadcrumb } from '@toolpad/core/PageContainer';
import invariant from 'invariant';
import { useNotifications } from '@/components/common/NotificationContext';

interface ClientWrapperProps {
  project: Project;
  sessionToken: string;
  projectId: string;
}

export default function ClientWrapper({ project, sessionToken, projectId }: ClientWrapperProps) {
  const router = useRouter();
  const params = useParams<{ identifier: string }>();
  const activePage = useActivePage();
  
  // Create dynamic breadcrumbs based on the current project
  const title = project.name || `Project ${params.identifier}`;
  
  // Create fallback breadcrumbs when activePage is null
  let breadcrumbs: Breadcrumb[] = [];
  if (activePage) {
    const path = `${activePage.path}/${params.identifier}`;
    breadcrumbs = [...activePage.breadcrumbs, { title, path }];
  } else {
    // Fallback breadcrumbs
    breadcrumbs = [
      { title: 'Projects', path: '/projects' },
      { title, path: `/projects/${params.identifier}` }
    ];
  }

  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [currentProject, setCurrentProject] = useState<Project>(project);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const notifications = useNotifications();

  const handleUpdateProject = useCallback(async (updatedProject: Partial<Project>) => {
    setIsUpdating(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const projectsClient = apiFactory.getProjectsClient();
      const response = await projectsClient.updateProject(projectId, updatedProject);
      setCurrentProject(response);
      setIsDrawerOpen(false);
      notifications.show('Project updated successfully', { severity: 'success' });
    } catch (error) {
      notifications.show(error instanceof Error ? error.message : 'Failed to update project', { severity: 'error' });
    } finally {
      setIsUpdating(false);
    }
  }, [projectId, sessionToken, notifications]);

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
      notifications.show('Project deleted successfully', { severity: 'success' });
      router.push('/projects');
    } catch (error) {
      notifications.show(error instanceof Error ? error.message : 'Failed to delete project', { severity: 'error' });
      setDeleteConfirmOpen(false);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <PageContainer title={title} breadcrumbs={breadcrumbs}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', mb: 3 }}>
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

      {/* Project Content */}
      <ProjectContent project={currentProject} />

      {/* Edit Drawer */}
      <ProjectEditDrawer 
        project={currentProject} 
        sessionToken={sessionToken}
        open={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onSave={handleUpdateProject}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteConfirmOpen}
        onClose={handleDeleteCancel}
      >
        <DialogTitle>Delete Project</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete the project &quot;{currentProject.name}&quot;? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel} disabled={isDeleting}>Cancel</Button>
          <Button 
            onClick={handleDeleteConfirm} 
            color="error" 
            autoFocus
            disabled={isDeleting}
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
} 