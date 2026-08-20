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
import PageLoadingState from '@/components/common/PageLoadingState';
import {
  ACTIVE_PROJECT_DELETE_BLOCKED,
  PROJECT_DELETE_WARNING,
} from '../constants';
import ProjectEditDrawer from './edit-drawer';
import ProjectDetailTabs from './components/ProjectDetailTabs';
import { format } from 'date-fns';
import { useInvalidateUsage } from '@/hooks/useInvalidateUsage';

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
  const [isDeleted, setIsDeleted] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const notifications = useNotifications();
  const {
    activeProject,
    refresh: refreshActiveProjects,
    syncProject,
  } = useActiveProject();

  // Deleting the project that scopes the whole app would leave every other view
  // pointing at something that no longer exists. Switch away from it first.
  const isActiveProject =
    !!activeProject && String(activeProject.id) === String(projectId);

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

  const invalidateUsage = useInvalidateUsage();

  const handleDeleteConfirm = async () => {
    // The FAB is guarded at render time, but activeProject can resolve after this
    // page rendered — a session with no active-project cookie and a single project
    // auto-selects it client-side — so the FAB may have been enabled when the
    // dialog opened. Re-check before the DELETE, as the list page does.
    if (isActiveProject) {
      notifications.show(ACTIVE_PROJECT_DELETE_BLOCKED, {
        severity: 'warning',
      });
      setDeleteConfirmOpen(false);
      return;
    }
    setIsDeleting(true);
    try {
      const apiFactory = new ApiClientFactory();
      const projectsClient = apiFactory.getProjectsClient();
      await projectsClient.deleteProject(projectId);
      invalidateUsage();
      // Unmount the detail body on this same render: the tabs below fire their
      // own project-scoped requests, and the refresh and navigation each take a
      // round trip. Without this the user watches the deleted project's tabs
      // fail one by one.
      setIsDeleted(true);
      setDeleteConfirmOpen(false);
      notifications.show('Project deleted successfully', {
        severity: 'success',
      });
      // The sidebar and switcher read ActiveProjectProvider state seeded by the
      // root layout, which router.refresh() does not re-run — so this is the only
      // way to drop the project from them without a full reload. It also clears
      // the active-project cookie when the deleted project was the active one.
      await refreshActiveProjects();
      // replace, not push: the deleted project's URL must not come back on Back.
      router.replace('/projects');
    } catch (error) {
      notifications.show(
        error instanceof Error ? error.message : 'Failed to delete project',
        { severity: 'error' }
      );
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
          aria-label="Edit project"
          onClick={() => setIsDrawerOpen(true)}
          disabled={isUpdating || isDeleting}
        />
      </Can>
      <Can capability={Capability.Project.UPDATE}>
        <Fab
          icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
          tooltip={
            isActiveProject ? ACTIVE_PROJECT_DELETE_BLOCKED : 'Delete project'
          }
          aria-label="Delete project"
          onClick={() => setDeleteConfirmOpen(true)}
          loading={isDeleting}
          disabled={isUpdating || isActiveProject}
        />
      </Can>
    </FabGroup>
  );

  // The project is gone; hold a neutral state until router.replace() lands rather
  // than rendering a detail page with nothing behind it.
  if (isDeleted) return <PageLoadingState />;

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
        warningMessage={PROJECT_DELETE_WARNING}
        message={
          <>
            Are you sure you want to delete{' '}
            <strong>{currentProject.name}</strong>? This action cannot be
            undone.
          </>
        }
      />
    </PageLayout>
  );
}
