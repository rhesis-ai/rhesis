'use client';

import { useState, useCallback } from 'react';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { EditIcon } from '@/components/icons';
import { Project } from '@/utils/api-client/interfaces/project';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';
import {
  PageLayout,
  type BreadcrumbItem,
} from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import { Fab, FabGroup } from '@/components/common/Fab';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import { Can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import ProjectEditDrawer from './edit-drawer';
import ProjectDetailTabs from './components/ProjectDetailTabs';
import { format } from 'date-fns';

interface ClientWrapperProps {
  project: Project;
  projectId: string;
}

export default function ClientWrapper({
  project,
  projectId,
}: ClientWrapperProps) {
  const router = useRouter();
  const params = useParams<{ identifier: string }>();
  const searchParams = useSearchParams();
  const tourId = searchParams.get('tour');
  useOnboardingTour(tourId === 'endpoint' ? 'endpoint' : undefined);

  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [currentProject, setCurrentProject] = useState<Project>(project);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const notifications = useNotifications();
  const { syncProject } = useActiveProject();

  const title = currentProject.name || `Project ${params.identifier}`;
  const breadcrumbs: BreadcrumbItem[] = [
    { label: 'Projects', href: '/projects' },
    { label: title },
  ];

  const createdAt = currentProject.created_at ?? currentProject.createdAt;
  const metadataStrip = (
    <DetailMetadataStrip
      items={[
        {
          label: 'created by:',
          value:
            currentProject.owner?.name || currentProject.owner?.email || '—',
        },
        {
          label: 'created on:',
          value: createdAt ? format(new Date(createdAt), 'dd/MM/yyyy') : '—',
        },
      ]}
    />
  );

  const handleUpdateProject = useCallback(
    async (updatedProject: Partial<Project>): Promise<boolean> => {
      setIsUpdating(true);
      try {
        const apiFactory = new ApiClientFactory();
        const projectsClient = apiFactory.getProjectsClient();
        const response = await projectsClient.updateProject(
          projectId,
          updatedProject
        );

        const updatedProjectWithOwner = {
          ...response,
          owner: response.owner || currentProject.owner,
          owner_id: response.owner_id || currentProject.owner_id,
        };

        setCurrentProject(updatedProjectWithOwner);
        syncProject(updatedProjectWithOwner);
        notifications.show('Project updated successfully', {
          severity: 'success',
        });
        return true;
      } catch (error) {
        notifications.show(
          error instanceof Error ? error.message : 'Failed to update project',
          { severity: 'error' }
        );
        return false;
      } finally {
        setIsUpdating(false);
      }
    },
    [projectId, notifications, currentProject, syncProject]
  );

  const handleDeleteConfirm = async () => {
    setIsDeleting(true);
    try {
      const apiFactory = new ApiClientFactory();
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
    } finally {
      setDeleteConfirmOpen(false);
      setIsDeleting(false);
    }
  };

  const pageActions = (
    <FabGroup>
      <Can capability={Capability.Project.UPDATE}>
        <Fab
          icon={<EditIcon sx={{ fontSize: 28 }} />}
          tooltip="Edit project"
          onClick={() => setIsDrawerOpen(true)}
          disabled={isUpdating || isDeleting}
        />
      </Can>
      <Can capability={Capability.Project.UPDATE}>
        <Fab
          icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
          tooltip="Delete project"
          onClick={() => setDeleteConfirmOpen(true)}
          loading={isDeleting}
          disabled={isUpdating}
        />
      </Can>
    </FabGroup>
  );

  return (
    <PageLayout
      title={title}
      breadcrumbs={breadcrumbs}
      metadata={metadataStrip}
      actions={pageActions}
    >
      <ProjectDetailTabs
        project={currentProject}
        projectId={projectId}
        onProjectUpdate={handleUpdateProject}
      />

      <ProjectEditDrawer
        project={currentProject}
        open={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onSave={handleUpdateProject}
      />

      <DeleteModal
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        itemType="project"
        itemName={currentProject.name}
        title="Delete Project"
      />
    </PageLayout>
  );
}
